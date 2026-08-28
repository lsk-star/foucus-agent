from typing import Annotated

from langchain_core.tools import tool
from pydantic import Field

from pybase.modules.account.data_access_guard import DataAccessGuard
from pybase.modules.auth.schemas import UserRead
from pybase.modules.sql_processing.explain_precheck_service import ExplainPrecheckService
from pybase.modules.sql_processing.read_only_runner import ReadOnlyQueryRunner, SqlResult
from pybase.modules.sql_processing.sql_safety_guard import SqlSafetyGuard

PREVIEW_ROWS = 20


def create_execute_sql_tool(
        sql_safety_guard: SqlSafetyGuard,
        explain_precheck_service: ExplainPrecheckService,
        runner: ReadOnlyQueryRunner,
        data_access_guard: DataAccessGuard,
        user: UserRead,
):
    def render_table(columns, rows, preview):
        """渲染Markdown表格"""
        lines = []

        # 表头
        lines.append(f"| {' | '.join(columns)} |")
        lines.append(f"|{'---|' * len(columns)}")

        # 数据行
        n = min(preview, len(rows))
        for i in range(n):
            row = rows[i]
            values = []
            for col in columns:
                values.append(render_cell(row.get(col)))
            lines.append(f"| {' | '.join(values)} |")

        return "\n".join(lines)

    def render_cell(value):
        """渲染单个单元格"""
        if value is None:
            return "NULL"

        s = str(value)
        # 替换Markdown特殊字符
        s = s.replace("|", "\\|").replace("\r", " ").replace("\n", " ").replace("\t", " ")
        return truncate(s, 200)

    def truncate(s, max_len):
        """截断字符串"""
        if s is None:
            return ""
        return s if len(s) <= max_len else s[:max_len] + "..."

    # llm友好输出格式化
    def _format_result(result: SqlResult) -> str:
        res = []
        if not result.success:
            res.append(f"× 执行失败(耗时 {result.duration_ms}ms) {result.error} ")
            res.append(f"执行 SQL 语句：{result.executed_sql} ")
            res.append("请根据上述报错重写 SQL（最多重试3 次）"
                       "常见原因：字段名拼错、表名错、J0IN条件错、类型不兼容。"
                       "建议重新调用 describeTables 确认真实字段名；"
                       "如果 JOIN结果异常放大，请先按主表分页或对子表聚合后再 JOIN。")
            return "\n".join(res)
        s = "截断到 max-rows 上限 \n\n" if result.truncated else ""
        res.append(
            f"√ 执行成功(耗时 {result.duration_ms}ms) 返回{result.row_count} 行数据 {s} 执行的sql 语句：{result.executed_sql}")

        if result.row_count == 0:
            res.append("查询结果为空。")
            res.append(
                "若这不符合预期，可能是WHERE 条件过严或JOIN 关联键错误一议去掉部分条件重查，或先 SELECT COUNT(*) 看真实命中量")
            return "\n".join(res)

        res.append(f"结果：（{result.row_count} 行）")
        if result.row_count > PREVIEW_ROWS:
            res.append(f"预览前 {PREVIEW_ROWS} 行。")
        res.append(f") {render_table(result.columns, result.rows, PREVIEW_ROWS)}")

        if result.row_count > PREVIEW_ROWS:
            remaining = result.row_count - PREVIEW_ROWS
            res.append(
                f"\n\n⚠ 共 {result.row_count} 行，仅展示前 {PREVIEW_ROWS} 行，剩余 {remaining} 行未在上下文中展示——")
            res.append("如需明细请按主表稳定排序分页重查，并注明当前页范围；"
                       "如是一对多关系，请优先对子表聚合成数量/金额/最新时间后再 JOIN，"
                       "用户点名某条主记录时再按主键二次查询明细；"
                       "如是分析/汇总任务，请改写为聚合 SQL（GROUP BY + SUM/COUNT/AVG）后重新查询，"
                       "不要试图从预览行里手算总量或均值。")

        return "\n".join(res)

    @tool(
        description="执行只读 SELECT/WITH 查询并返回结果数据。"
                    "参数名严格为 sql，严谨使用任何其他参数名，"
                    "传错会收到 \"参数名错误\" 提示，必须改用 sql 重新调用。"
                    "内部会强制做 SQL 安全校验（白名单/强制 LIMIT）和保守 EXPLAIN 预检查，"
                    "明显的大表明细扫描或 JOIN 扩张会被拦截。"
                    "若执行失败，会返回 error 字段——请根据错误信息重写 SQL（最多重试 3 次），"
                    "常见错误：字段名拼错（参考 describeTables 输出）、表名错、JOIN 条件错。"
                    "严禁写 INSERT/UPDATE/DELETE/DROP 等。"
    )
    async def execute_sql(sql: Annotated[str, Field(description="执行的SQL 语句")]) -> str:
        if not sql:
            return (
                "❌ 参数错误：sql 为空。本工具参数名严格为 `sql`，禁止用任何其他名字。"
                "请重新调用 execute_sql，把 SQL 语句放在 `sql` 参数中。"
            )

        # 1. 强制校验兜底
        validate_result = sql_safety_guard.validate(sql)

        if not validate_result.valid:
            return (f"❌ 已拦截（EXPLAIN 预检查）。原因：{validate_result.reason} "
                    f" \n 请重写 SQL：统计问题优先用 GROUP BY 聚合；明细问题增加选择性 WHERE，"
                    f" 按主表主键或时间字段稳定分页；一对多关系请先对子表聚合后 JOIN，或先查主键列表再按主键二次钻取。")

        # 2. 数据权限改写 —— 强制注入 account_id 过滤条件
        is_admin = user.role == "admin"
        scope = await data_access_guard.get_data_scope(user.id, is_admin)
        if not scope.is_admin:
            if not scope.has_access:
                return "❌ 您没有任何广告账户的数据权限，无法执行查询。请联系管理员分配广告账户。"
            sql = await data_access_guard.rewrite_sql(sql, scope)

        # 3. 执行预计划检查
        precheck_result = await explain_precheck_service.check(sql)
        if not precheck_result.allowed:
            return (
                f"❌ 预检查未通过：{precheck_result.reason} "
                "请根据上述提示修改 SQL 后重新调用本工具执行。"
            )

        # 4. 执行 SQL 语句
        sql_result: SqlResult = await runner.execute(sql)

        # 5. 数据脱敏

        return _format_result(sql_result)

    return execute_sql
