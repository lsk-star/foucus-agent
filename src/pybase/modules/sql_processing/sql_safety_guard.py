"""
SQL 安全校验器 - Python 版本
使用 sqlglot 实现，覆盖：白名单（仅 SELECT/WITH）、防多语句、防危险函数、强制 LIMIT、防 FOR UPDATE / SELECT INTO
"""

import re
import logging
from typing import Optional, Set, Tuple
from dataclasses import dataclass

from sqlglot import exp, parse_one, parse
from sqlglot.errors import ParseError

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """校验结果"""
    valid: bool
    reason: str
    safe_sql: Optional[str] = None


class SqlSafetyGuard:
    """
    SQL 安全校验器。由 validate_sql tool 和 execute_sql tool 共享，形成双保险。
    覆盖：白名单（仅 SELECT/WITH）、防多语句、防危险函数、强制 LIMIT、防 FOR UPDATE / SELECT INTO。
    """

    # 危险函数/模式正则（文本预扫，作为 AST 检查的补充）
    DANGEROUS_PATTERN = re.compile(
        r"(?i)\bLOAD_FILE\s*\("           # 读文件
        r"|\bINTO\s+(OUTFILE|DUMPFILE)\b"  # SELECT 写文件
        r"|\bSYSTEM_USER\s*\("            # 信息泄漏
        r"|\bFILE_READ|\bFILE_WRITE"
    )

    # AST 遍历要拦截的函数名（小写）
    DANGEROUS_FUNCTIONS: Set[str] = {
        "sleep", "benchmark", "get_lock", "release_lock",
        "is_free_lock", "is_used_lock", "master_pos_wait", "source_pos_wait",
        "load_file", "sys_exec", "sys_eval", "sys_get"
    }

    # 禁止的语句类型
    FORBIDDEN_STATEMENT_TYPES = {
        "insert", "update", "delete", "drop", "create", "alter",
        "truncate", "rename", "call", "merge", "replace"
    }

    def __init__(self, max_rows: int = 200, max_joins: int = 3):
        """
        初始化 SQL 安全校验器

        Args:
            max_rows: 最大返回行数
            max_joins: 最大允许的 JOIN 数量
        """
        self.max_rows = max_rows
        self.max_joins = max_joins

    def validate(self, sql: str) -> ValidationResult:
        """
        校验 SQL

        Args:
            sql: 待校验 SQL

        Returns:
            ValidationResult: valid=True 时 safe_sql 为可执行的安全 SQL（已注入 LIMIT）；
                              valid=False 时 reason 为修改建议
        """
        if not sql or not sql.strip():
            return ValidationResult(False, "SQL 为空")

        trimmed = sql.strip()
        # 去掉末尾分号，避免误判
        while trimmed.endswith(";"):
            trimmed = trimmed[:-1].strip()

        try:
            return self._do_validate(trimmed)
        except ParseError as pe:
            msg = str(pe).replace("\n", " ")
            return ValidationResult(False, f"SQL 语法解析失败：{self._truncate(msg, 200)}")
        except Exception as e:
            logger.warning(f"SqlSafetyGuard 意外异常，保守拒绝 sql={self._truncate(trimmed, 120)} err={e}")
            return ValidationResult(False, f"SQL 校验异常：{e.__class__.__name__}")

    def _do_validate(self, sql: str) -> ValidationResult:
        """
        执行实际的校验逻辑

        Args:
            sql: 清理后的 SQL

        Returns:
            ValidationResult
        """
        # 1. 原始文本预扫（防解析盲区）
        match = self.DANGEROUS_PATTERN.search(sql)
        if match:
            return self._reject(f"检测到危险模式：{match.group().strip()}")

        # 2. 解析——sqlglot 默认解析单语句，多语句需要特殊处理
        try:
            # 尝试解析为多语句
            expressions = list(parse(sql, dialect="mysql"))
            if len(expressions) > 1:
                return self._reject(f"仅允许单条语句，检测到 {len(expressions)} 条（禁止用 ; 串联）")
            if not expressions:
                return self._reject("SQL 解析为空")
            expr = expressions[0]
        except ParseError:
            # 如果 parse 失败，尝试 parse_one 作为单语句
            try:
                expr = parse_one(sql, dialect="mysql")
            except ParseError:
                raise

        # 3. 白名单：只允许 SELECT（包括 WITH）
        if not isinstance(expr, exp.Select):
            stmt_type = expr.__class__.__name__
            return self._reject(f"仅允许 SELECT/WITH 查询，禁止 {stmt_type}（INSERT/UPDATE/DELETE/DDL/CALL 等均被拦截）")

        # 4. AST 遍历找危险函数
        bad = self._find_dangerous_functions(expr)
        if bad:
            return self._reject(f"检测到危险函数：{bad}()")

        # 5. 拦截 FOR UPDATE / SELECT INTO / 不稳定分页 / 高风险 JOIN
        shape_result = self._validate_select_shape(expr)
        if not shape_result.valid:
            return shape_result

        # 6. 用户 LIMIT 超阈值则下调
        self._cap_outer_limit(expr)

        # 7. 无 LIMIT 注入一个
        if not expr.args.get("limit"):
            expr = expr.limit(self.max_rows)

        safe_sql = expr.sql(dialect="mysql")
        logger.debug(f"SqlSafetyGuard 通过：{self._truncate(safe_sql, 200)}")
        return ValidationResult(True, "OK", safe_sql)

    def _find_dangerous_functions(self, expr: exp.Expression) -> Optional[str]:
        """
        在 AST 中递归查找危险函数

        Args:
            expr: 表达式节点

        Returns:
            找到的危险函数名，未找到返回 None
        """
        for node in expr.find_all(exp.Func):
            func_name = node.name.lower() if node.name else ""
            if func_name in self.DANGEROUS_FUNCTIONS:
                return func_name
        return None

    def _validate_select_shape(self, select: exp.Select) -> ValidationResult:
        """
        递归校验查询形态，拦截不稳定分页和高风险 JOIN

        Args:
            select: Select 节点

        Returns:
            ValidationResult
        """
        # 处理 WITH 子句
        with_items = select.args.get("with")
        if with_items:
            for item in with_items.expressions if hasattr(with_items, "expressions") else [with_items]:
                if isinstance(item, exp.CTE):
                    cte_result = self._validate_select_shape(item.this)
                    if not cte_result.valid:
                        return cte_result

        # 处理嵌套查询
        return self._validate_plain_select_shape(select)

    def _validate_plain_select_shape(self, select: exp.Select) -> ValidationResult:
        """
        校验单个 SELECT 的形态

        Args:
            select: Select 节点

        Returns:
            ValidationResult
        """
        # 拦截 FOR UPDATE / FOR SHARE
        if select.args.get("locks"):
            return self._reject("禁止 FOR UPDATE / FOR SHARE（只读连接）")

        # 拦截 SELECT ... INTO
        if select.args.get("into"):
            return self._reject("禁止 SELECT ... INTO（写文件/写变量/写表）")

        # 分页查询使用 OFFSET 时必须带稳定 ORDER BY
        if select.args.get("offset") and not select.args.get("order"):
            return self._reject("分页查询使用 OFFSET 时必须带稳定 ORDER BY，建议按主表主键或时间字段 + 主键排序")

        # 校验 FROM 子句
        from_result = self._validate_from_item(select.args.get("from"))
        if not from_result.valid:
            return from_result

        # 校验 WHERE 子句中的子查询
        where = select.args.get("where")
        if where:
            where_result = self._validate_subselects(where)
            if not where_result.valid:
                return where_result

        # 校验 JOIN
        joins = select.args.get("joins")
        if not joins:
            return ValidationResult(True, "OK")

        if len(joins) > self.max_joins:
            return self._reject(
                f"当前 SQL 关联表过多，最多允许 {self.max_joins} 个 JOIN。"
                "请拆成多步查询：先查主表分页，再按主键查询详情；"
                "如果是统计问题，请改为 GROUP BY 聚合查询"
            )

        for join in joins:
            # 禁止 CROSS JOIN
            if join.args.get("kind") == "CROSS":
                return self._reject("禁止 CROSS JOIN。请补充明确的 JOIN ON 条件，避免产生笛卡尔积")

            # 禁止无条件 JOIN（NATURAL JOIN 或没有 ON 条件的 JOIN）
            if not join.args.get("on") and not join.args.get("using"):
                return self._reject("禁止无条件 JOIN。请使用明确的 JOIN ON/USING 条件，避免产生笛卡尔积")

            # 校验 JOIN 右侧的子查询
            right_result = self._validate_from_item(join.args.get("this"))
            if not right_result.valid:
                return right_result

            # 校验 JOIN ON 条件中的子查询
            on_condition = join.args.get("on")
            if on_condition:
                on_result = self._validate_subselects(on_condition)
                if not on_result.valid:
                    return on_result

        return ValidationResult(True, "OK")

    def _validate_from_item(self, from_item) -> ValidationResult:
        """
        校验 FROM 子句中的项

        Args:
            from_item: FROM 子句项

        Returns:
            ValidationResult
        """
        if from_item is None:
            return ValidationResult(True, "OK")

        # 如果是子查询
        if isinstance(from_item, exp.Select):
            return self._validate_select_shape(from_item)

        # 如果是带 JOIN 的派生表 (sqlglot 中可能是 Subquery 或 Select)
        if hasattr(from_item, "this") and isinstance(from_item.this, exp.Select):
            return self._validate_select_shape(from_item.this)

        return ValidationResult(True, "OK")

    def _validate_subselects(self, expr: exp.Expression) -> ValidationResult:
        """
        校验表达式中的子查询

        Args:
            expr: 表达式节点

        Returns:
            ValidationResult
        """
        from sqlglot.expressions import Subquery, Select

        for node in expr.walk():
            if isinstance(node, (Subquery, Select)):
                result = self._validate_select_shape(node.this if isinstance(node, Subquery) else node)
                if not result.valid:
                    return result
        return ValidationResult(True, "OK")

    def _cap_outer_limit(self, select: exp.Select) -> None:
        """
        用户 LIMIT 超阈值则下调到 max_rows

        Args:
            select: Select 节点
        """
        limit = select.args.get("limit")
        if limit and hasattr(limit, "expression"):
            try:
                # 尝试获取 LIMIT 的值
                limit_expr = limit.expression
                if isinstance(limit_expr, exp.Literal):
                    user_val = int(limit_expr.name)
                    if user_val > self.max_rows:
                        # 重新设置 LIMIT
                        select.args["limit"] = exp.Limit(expression=exp.Literal.number(self.max_rows))
                        logger.debug(f"用户 LIMIT {user_val} > 阈值 {self.max_rows}，已下调")
            except (ValueError, AttributeError):
                pass

    @staticmethod
    def _reject(reason: str) -> ValidationResult:
        """返回拒绝结果"""
        return ValidationResult(False, reason)

    @staticmethod
    def _truncate(s: str, max_len: int) -> str:
        """截断字符串"""
        if not s:
            return ""
        return s if len(s) <= max_len else s[:max_len] + "..."


# ============= 单元测试 =============
def test_sql_safety_guard():
    """简单的单元测试"""
    guard = SqlSafetyGuard(max_rows=200, max_joins=3)

    test_cases = [
        # 正常查询
        ("SELECT * FROM users", True),
        ("SELECT id, name FROM users WHERE age > 18 LIMIT 10", True),
        ("WITH t AS (SELECT * FROM orders) SELECT * FROM t", True),
        ("SELECT u.*, o.amount FROM users u JOIN orders o ON u.id = o.user_id", True),

        # 危险函数
        ("SELECT SLEEP(10)", False),
        ("SELECT * FROM files WHERE LOAD_FILE('/etc/passwd')", False),
        ("SELECT BENCHMARK(1000000, MD5('test'))", False),

        # 多语句
        ("SELECT * FROM users; DROP TABLE orders", False),
        ("SELECT * FROM users; SELECT * FROM orders", False),

        # 禁止的语句类型
        ("INSERT INTO users VALUES (1, 'test')", False),
        ("UPDATE users SET name = 'test'", False),
        ("DELETE FROM users", False),
        ("DROP TABLE users", False),
        ("CREATE TABLE users", False),

        # SELECT INTO
        ("SELECT * INTO OUTFILE '/tmp/data.csv' FROM users", False),
        ("SELECT * INTO DUMPFILE '/tmp/data.bin' FROM users", False),

        # FOR UPDATE
        ("SELECT * FROM users FOR UPDATE", False),

        # CROSS JOIN / 无条件的 JOIN
        ("SELECT * FROM users CROSS JOIN orders", False),
        ("SELECT * FROM users JOIN orders", False),

        # 过多的 JOIN
        ("SELECT * FROM a JOIN b ON a.id=b.id JOIN c ON b.id=c.id JOIN d ON c.id=d.id JOIN e ON d.id=e.id", False),

        # 无 ORDER BY 的 OFFSET
        ("SELECT * FROM users OFFSET 10", False),
        ("SELECT * FROM users ORDER BY id OFFSET 10", True),

        # 嵌套子查询
        ("SELECT * FROM (SELECT * FROM users) t", True),
        ("SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)", True),

        # 大 LIMIT 自动下调
        ("SELECT * FROM users LIMIT 1000", True),  # 返回的 safe_sql 中 LIMIT 会被下调到 200
    ]

    for sql, expected_valid in test_cases:
        result = guard.validate(sql)
        status = "✓" if result.valid == expected_valid else "✗"
        print(f"{status} SQL: {sql[:50]}")
        print(f"   valid: {result.valid}, expected: {expected_valid}")
        if result.reason:
            print(f"   reason: {result.reason}")
        if result.safe_sql:
            print(f"   safe_sql: {result.safe_sql}")
        print()

        # 断言
        assert result.valid == expected_valid, f"Failed for SQL: {sql}"

    print("所有测试通过！")


if __name__ == "__main__":
    test_sql_safety_guard()