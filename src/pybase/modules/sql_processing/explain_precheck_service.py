"""
SQL 执行计划预检查 - Python 异步版本
使用 ReadOnlyQueryRunner 执行 EXPLAIN，保守拦截大表明细扫描和 JOIN 结果扩张。
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, List, Optional

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from pybase.modules.sql_processing.read_only_runner import ReadOnlyQueryRunner

logger = logging.getLogger(__name__)


@dataclass
class ExplainRow:
    """EXPLAIN 结果行"""

    select_type: Optional[str]
    table: Optional[str]
    access_type: Optional[str]
    key: Optional[str]
    rows: int
    extra: Optional[str]


@dataclass
class PrecheckResult:
    """预检查结果"""

    allowed: bool
    reason: str

    @classmethod
    def allow(cls, reason: str = "OK") -> "PrecheckResult":
        """构造放行结果"""
        return cls(allowed=True, reason=reason)

    @classmethod
    def block(cls, reason: str) -> "PrecheckResult":
        """构造拦截结果"""
        return cls(allowed=False, reason=reason)


class ExplainPrecheckService:
    """
    SQL 执行计划预检查。

    只做保守拦截：小表全表扫描、无索引但数据量小、合理聚合查询都放行；
    只拦截明显高风险的大表明细扫描或 JOIN 结果扩张。
    """

    MAX_PLAN_ROWS = 64

    def __init__(
        self,
        runner: ReadOnlyQueryRunner,
        max_estimated_rows: int = 100000,
    ):
        """
        初始化预检查服务

        Args:
            runner: 只读 SQL 执行器
            max_estimated_rows: 最大估计行数阈值
        """
        self._runner = runner
        self.max_estimated_rows = max_estimated_rows

    async def check(self, final_sql: str) -> PrecheckResult:
        """
        执行 SQL 预检查：先 EXPLAIN 获取执行计划，再分析是否高风险

        Args:
            final_sql: 待检查的 SQL 语句

        Returns:
            预检查结果，超时则拦截，其他异常按 fail-open 放行
        """
        if not final_sql or not final_sql.strip():
            return PrecheckResult.allow()

        t0 = time.time()
        try:
            rows = await self._explain(final_sql)
            result = self._analyze(final_sql, rows)
            logger.debug(
                "[focus-agent] EXPLAIN 预检查 %s | planRows=%d cost=%.2fms | reason=%s",
                "PASS" if result.allowed else "BLOCK",
                len(rows),
                (time.time() - t0) * 1000,
                result.reason,
            )
            return result
        except OperationalError as e:
            if self._is_timeout(e):
                reason = "EXPLAIN 预检查超时，说明数据库生成执行计划也较慢，当前 SQL 可能过重"
                logger.warning("[focus-agent] %s，已拦截 | sql=%s", reason, self._truncate(final_sql, 300))
                return PrecheckResult.block(reason)
            reason = f"EXPLAIN 预检查失败：{self._truncate(str(e), 300)}"
            logger.warning("[focus-agent] %s，按 fail-open 放行", reason)
            return PrecheckResult.allow()
        except SQLAlchemyError as e:
            reason = f"EXPLAIN 预检查失败：{self._truncate(str(e), 300)}"
            logger.warning("[focus-agent] %s，按 fail-open 放行", reason)
            return PrecheckResult.allow()
        except Exception as e:
            reason = f"EXPLAIN 预检查失败：{self._truncate(str(e), 300)}"
            logger.warning("[focus-agent] %s，按 fail-open 放行", reason)
            return PrecheckResult.allow()

    async def _explain(self, final_sql: str) -> List[ExplainRow]:
        """
        通过 runner 执行 EXPLAIN 并返回解析后的结果行列表

        Args:
            final_sql: 待 EXPLAIN 的 SQL 语句

        Returns:
            ExplainRow 列表，最多返回 MAX_PLAN_ROWS 行
        """
        explain_sql = f"EXPLAIN {final_sql}"
        cursor_result = await self._runner.execute_raw(explain_sql)

        rows: list[ExplainRow] = []
        for row in cursor_result:
            rows.append(self._read_explain_row(row))
            if len(rows) >= self.MAX_PLAN_ROWS:
                break

        return rows

    def _read_explain_row(self, row: Any) -> ExplainRow:
        """
        从 EXPLAIN 原始结果行中提取字段，构造 ExplainRow

        Args:
            row: SQLAlchemy 结果行对象

        Returns:
            ExplainRow 实例
        """
        columns = row._mapping if hasattr(row, "_mapping") else row
        return ExplainRow(
            select_type=self._get_value(columns, "select_type"),
            table=self._get_value(columns, "table"),
            access_type=self._get_value(columns, "type"),
            key=self._get_value(columns, "key"),
            rows=self._get_long(columns, "rows"),
            extra=self._get_value(columns, "Extra"),
        )

    def _get_value(self, row: Any, label: str) -> Optional[str]:
        """
        从结果行中安全获取字符串值，异常时返回 None

        Args:
            row: 结果行（支持 _mapping 或属性访问）
            label: 列名

        Returns:
            字符串值或 None
        """
        try:
            if hasattr(row, "_mapping"):
                val = row._mapping.get(label)
            else:
                val = getattr(row, label, None)
            return str(val) if val is not None else None
        except Exception:
            return None

    def _get_long(self, row: Any, label: str) -> int:
        """
        从结果行中安全获取整型值，异常或为空时返回 0

        Args:
            row: 结果行（支持 _mapping 或属性访问）
            label: 列名

        Returns:
            整型值，解析失败返回 0
        """
        try:
            if hasattr(row, "_mapping"):
                val = row._mapping.get(label)
            else:
                val = getattr(row, label, None)

            if val is None:
                return 0
            if isinstance(val, (int, float)):
                return int(val)
            try:
                return int(str(val))
            except (ValueError, TypeError):
                return 0
        except Exception:
            return 0

    def _analyze(self, sql: str, rows: List[ExplainRow]) -> PrecheckResult:
        """
        分析 EXPLAIN 结果，判断是否应拦截

        1、空计划直接放行
        2、聚合查询直接放行（GROUP BY / HAVING / 聚合函数）
        3、筛选有表访问的行，逐表检查是否存在大表明细扫描（风险访问 + 行数超阈值）
        4、多表 JOIN 时检查是否存在结果扩张风险（组合行数超阈值 + 无索引/Join Buffer 信号）

        Args:
            sql: 原始 SQL 语句
            rows: EXPLAIN 结果行列表

        Returns:
            预检查结果
        """
        # 1、空计划直接放行
        if not rows:
            return PrecheckResult.allow()

        # 2、聚合查询直接放行
        if not self._looks_like_detail_query(sql):
            return PrecheckResult.allow()

        # 3、筛选有表访问的行，逐表检查大表明细扫描
        table_rows = [r for r in rows if r.table is not None and r.table.strip()]
        if not table_rows:
            return PrecheckResult.allow()

        for row in table_rows:
            if self._is_risky_access(row.access_type) and row.rows >= self.max_estimated_rows:
                return PrecheckResult.block(
                    f"疑似大表明细扫描，表 {self._table_name(row)} "
                    f"使用 {self._safe(row.access_type)} 访问，预计扫描 {row.rows} 行"
                )

        # 4、多表 JOIN 时检查结果扩张风险
        if len(table_rows) >= 2:
            join_threshold = self._join_expansion_threshold()
            estimated_join_rows = self._estimated_join_rows(table_rows, join_threshold)
            if estimated_join_rows >= join_threshold and self._has_join_risk_signal(table_rows):
                return PrecheckResult.block(
                    f"疑似 JOIN 结果扩张，预计组合行数超过 {join_threshold}，"
                    "且存在无索引访问或 Join Buffer 风险"
                )

        return PrecheckResult.allow()

    def _looks_like_detail_query(self, sql: str) -> bool:
        """
        判断是否为明细查询（非聚合查询）

        Args:
            sql: SQL 语句

        Returns:
            True 表示明细查询，False 表示聚合查询
        """
        normalized = re.sub(r"\s+", " ", sql.lower())
        aggregation_keywords = [
            " group by ", " having ", "count(", "sum(", "avg(", "min(", "max(",
        ]
        return not any(kw in normalized for kw in aggregation_keywords)

    def _has_join_risk_signal(self, rows: List[ExplainRow]) -> bool:
        """
        检查 JOIN 是否存在风险信号：Using join buffer、从表风险访问、多表无索引

        Args:
            rows: 有表名的 EXPLAIN 行列表

        Returns:
            True 表示存在 JOIN 风险信号
        """
        missing_key_count = 0
        for i, row in enumerate(rows):
            extra = self._safe(row.extra).lower()
            if "using join buffer" in extra:
                return True
            if i > 0 and self._is_risky_access(row.access_type):
                return True
            if self._is_blank_key(row.key):
                missing_key_count += 1
        return missing_key_count >= 2

    def _estimated_join_rows(self, rows: List[ExplainRow], threshold: int) -> int:
        """
        估算 JOIN 结果行数（各表 rows 的乘积），超过阈值时提前截断返回

        Args:
            rows: 有表名的 EXPLAIN 行列表
            threshold: 行数上限阈值

        Returns:
            估算的 JOIN 结果行数，不超过 threshold
        """
        product = 1
        for row in rows:
            value = max(1, row.rows)
            if product > threshold // value:
                return threshold
            product *= value
        return product

    def _join_expansion_threshold(self) -> int:
        """
        获取 JOIN 扩张阈值，默认为 max_estimated_rows 的 10 倍

        Returns:
            JOIN 结果行数上限阈值
        """
        return max(self.max_estimated_rows * 10, self.max_estimated_rows)

    def _is_risky_access(self, access_type: Optional[str]) -> bool:
        """
        判断是否为风险访问类型（ALL=全表扫描, INDEX=全索引扫描）

        Args:
            access_type: MySQL EXPLAIN 的 type 字段值

        Returns:
            True 表示风险访问
        """
        if not access_type:
            return False
        return access_type.upper() in ("ALL", "INDEX")

    def _is_timeout(self, error: Exception) -> bool:
        """
        判断是否为数据库超时错误（MySQL 3024 或 timeout 关键字）

        Args:
            error: 异常对象

        Returns:
            True 表示超时错误
        """
        error_msg = str(error).lower()
        return "timeout" in error_msg or "3024" in error_msg

    def _is_blank_key(self, key: Optional[str]) -> bool:
        """
        判断索引键是否为空（None、空白、NULL 字符串）

        Args:
            key: MySQL EXPLAIN 的 key 字段值

        Returns:
            True 表示未使用索引
        """
        return key is None or not key.strip() or key.upper() == "NULL"

    def _table_name(self, row: ExplainRow) -> str:
        """
        安全获取表名，为空时返回 <unknown>

        Args:
            row: ExplainRow 实例

        Returns:
            表名字符串
        """
        return row.table if row.table and row.table.strip() else "<unknown>"

    def _safe(self, value: Optional[str]) -> str:
        """
        安全获取字符串，为空时返回 UNKNOWN

        Args:
            value: 可能为空的字符串

        Returns:
            非空字符串
        """
        return "UNKNOWN" if not value or not value.strip() else value

    @staticmethod
    def _truncate(s: str, max_len: int) -> str:
        """
        截断字符串，超出部分用 ... 替代

        Args:
            s: 原始字符串
            max_len: 最大长度

        Returns:
            截断后的字符串
        """
        if not s:
            return ""
        return s if len(s) <= max_len else s[:max_len] + "..."