"""
只读 SQL 执行器 - Python 异步版本
在主数据源上执行只读 SELECT/WITH，返回 SqlResult。
安全措施：只读连接 + 查询超时 + 行数硬限 + 瞬态错误透明重试。
失败时错误信息按 SQLState 分类，给 LLM 修复 SQL 的明确建议。
"""

import asyncio
import enum
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = logging.getLogger(__name__)


@dataclass
class ColumnMeta:
    """列元信息"""
    name: str
    table_name: Optional[str] = None
    column_name: Optional[str] = None


@dataclass
class SqlResult:
    """SQL 执行结果"""
    executed_sql: str
    columns: List[str]
    column_metas: List[ColumnMeta]
    rows: List[Dict[str, Any]]
    row_count: int
    truncated: bool
    duration_ms: int
    error: Optional[str] = None
    success: bool = False

    @classmethod
    def ok(
        cls,
        executed_sql: str,
        columns: List[str],
        column_metas: List[ColumnMeta],
        rows: List[Dict[str, Any]],
        row_count: int,
        truncated: bool,
        duration_ms: int,
        success: bool = True,
    ) -> "SqlResult":
        """构造成功结果"""
        return cls(
            executed_sql=executed_sql,
            columns=columns,
            column_metas=column_metas,
            rows=rows,
            row_count=row_count,
            truncated=truncated,
            duration_ms=duration_ms,
            error=None,
            success=success,
        )

    @classmethod
    def fail(cls, executed_sql: str, error: str, duration_ms: int, success: bool = False) -> "SqlResult":
        """构造失败结果"""
        return cls(
            executed_sql=executed_sql,
            columns=[],
            column_metas=[],
            rows=[],
            row_count=0,
            truncated=False,
            duration_ms=duration_ms,
            error=error,
            success=success,
        )


class SqlErrorType(enum.Enum):
    """SQL 错误分类"""
    TRANSIENT = "TRANSIENT"
    SCHEMA = "SCHEMA"
    SYNTAX = "SYNTAX"
    FATAL = "FATAL"


class ReadOnlyQueryRunner:
    """
    只读 SQL 执行器。

    在主数据源上执行只读 SELECT/WITH，返回 SqlResult。
    安全措施：只读连接 + 查询超时 + 行数硬限 + 瞬态错误透明重试。
    """

    MAX_TRANSIENT_RETRIES = 2

    def __init__(
        self,
        engine: AsyncEngine,
        max_rows: int = 200,
        timeout_seconds: int = 30,
    ):
        """
        初始化只读执行器

        Args:
            engine: SQLAlchemy 异步数据库引擎
            max_rows: 最大返回行数
            timeout_seconds: 查询超时时间（秒）
        """
        self.engine = engine
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

    async def execute(self, safe_sql: str) -> SqlResult:
        """
        执行只读 SELECT/WITH 查询，含瞬态重试

        Args:
            safe_sql: 已通过安全校验的 SQL

        Returns:
            SqlResult 执行结果
        """
        t0 = time.time()
        for attempt in range(self.MAX_TRANSIENT_RETRIES + 1):
            try:
                async with self.engine.connect() as conn:
                    async with conn.begin():
                        await self._try_set_read_only(conn)
                        try:
                            await conn.execute(
                                text(f"SET SESSION max_execution_time={self.timeout_seconds * 1000}")
                            )
                        except Exception:
                            pass

                        result = await conn.execute(text(safe_sql))
                        return self._read_result(result, safe_sql, t0)
            except (OperationalError, SQLAlchemyError) as e:
                error_type = self._classify_error(e)
                if error_type == SqlErrorType.TRANSIENT and attempt < self.MAX_TRANSIENT_RETRIES:
                    logger.debug(
                        "TRANSIENT 错误，第 %d 次重试: %s",
                        attempt + 1,
                        self._root_message(e),
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                duration_ms = int((time.time() - t0) * 1000)
                return SqlResult.fail(
                    safe_sql,
                    self._build_classified_error(e, error_type),
                    duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - t0) * 1000)
                return SqlResult.fail(
                    safe_sql,
                    f"执行失败：{self._truncate(str(e), 500)}",
                    duration_ms,
                )

        duration_ms = int((time.time() - t0) * 1000)
        msg = (
            f"执行超时：数据库连接或查询超时，已重试 {self.MAX_TRANSIENT_RETRIES} "
            "次仍未成功。可能是数据库负载过高，请稍后重试。"
        )
        return SqlResult.fail(safe_sql, msg, duration_ms)

    async def execute_raw(self, safe_sql: str) -> CursorResult:
        """
        执行只读查询，返回原始 CursorResult（供 EXPLAIN 等需要原始行的场景使用）

        Args:
            safe_sql: 已通过安全校验的 SQL

        Returns:
            SQLAlchemy CursorResult 原始结果

        Raises:
            OperationalError: 数据库操作错误
            SQLAlchemyError: SQLAlchemy 错误
        """
        async with self.engine.connect() as conn:
            async with conn.begin():
                await self._try_set_read_only(conn)
                try:
                    await conn.execute(
                        text(f"SET SESSION max_execution_time={self.timeout_seconds * 1000}")
                    )
                except Exception:
                    pass

                return await conn.execute(text(safe_sql))

    def _read_result(self, cursor_result: CursorResult, safe_sql: str, t0: float) -> SqlResult:
        """
        从 CursorResult 构建 SqlResult

        Args:
            cursor_result: SQLAlchemy 执行结果
            safe_sql: 执行的 SQL
            t0: 开始时间戳

        Returns:
            SqlResult 实例
        """
        columns = list(cursor_result.keys())

        column_metas = [ColumnMeta(name=col, table_name=None, column_name=col) for col in columns]

        all_rows = cursor_result.fetchall()
        truncated = len(all_rows) > self.max_rows
        fetched_rows = all_rows[: self.max_rows]
        row_dicts = [
            {col: self._normalize_value(row[i]) for i, col in enumerate(columns)}
            for row in fetched_rows
        ]

        duration_ms = int((time.time() - t0) * 1000)
        return SqlResult.ok(
            executed_sql=safe_sql,
            columns=columns,
            column_metas=column_metas,
            rows=row_dicts,
            row_count=len(all_rows),
            truncated=truncated,
            duration_ms=duration_ms,
        )

    async def _try_set_read_only(self, conn: AsyncConnection) -> None:
        """
        尝试设置连接为只读事务，失败则静默忽略

        Args:
            conn: 异步数据库连接
        """
        try:
            await conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        except Exception as e:
            logger.debug("setReadOnly 失败，忽略：%s", str(e))

    def _normalize_value(self, v: Any) -> Any:
        """
        规范化值类型，确保序列化安全和可读性

        Args:
            v: 原始值

        Returns:
            规范化后的值
        """
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v.normalize().to_eng_string()
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, date):
            return v.strftime("%Y-%m-%d")
        if isinstance(v, bytes):
            return f"[BLOB {len(v)} bytes]"
        if isinstance(v, float):
            return str(v)
        return v

    def _classify_error(self, e: Exception) -> SqlErrorType:
        """
        按 SQLState 对错误进行分类

        Args:
            e: 数据库异常

        Returns:
            错误分类
        """
        state = getattr(e, "orig", None)
        if state is not None:
            state = getattr(state, "args", None)
            if state and len(state) > 0:
                state = str(state[0])
            else:
                state = None
        else:
            state = None

        if not state:
            msg = str(e).lower()
            if "timeout" in msg or "timed out" in msg or "lost connection" in msg:
                return SqlErrorType.TRANSIENT
            return SqlErrorType.FATAL

        if state.startswith("08"):
            return SqlErrorType.TRANSIENT
        if state == "40001":
            return SqlErrorType.TRANSIENT
        if state in ("42S02", "42S22"):
            return SqlErrorType.SCHEMA
        if state in ("42000", "42601"):
            return SqlErrorType.SYNTAX
        if state.startswith("28"):
            return SqlErrorType.FATAL
        return SqlErrorType.FATAL

    def _build_classified_error(self, e: Exception, error_type: SqlErrorType) -> str:
        """
        按错误分类生成 LLM 友好的错误提示

        Args:
            e: 原始异常
            error_type: 错误分类

        Returns:
            分类后的错误信息（含修复建议）
        """
        raw_msg = self._root_message(e)
        if error_type == SqlErrorType.SCHEMA:
            return (
                f"字段或表不存在：{raw_msg}\n"
                "建议：重新调用 describeTables 确认真实的表名和字段名"
                "（注意拼写和大小写），再修改 SQL。"
            )
        if error_type == SqlErrorType.SYNTAX:
            return (
                f"SQL 语法错误：{raw_msg}\n"
                "建议：检查 SQL 语法，确认关键字、括号、引号是否正确。"
            )
        if error_type == SqlErrorType.FATAL:
            return (
                f"数据库错误（无法重试）：{raw_msg}\n"
                "可能是权限不足或资源问题，请检查数据库状态。"
            )
        return f"执行失败：{raw_msg}"

    def _root_message(self, e: Exception) -> str:
        """
        提取异常的根本错误信息

        Args:
            e: 异常对象

        Returns:
            截断后的错误信息
        """
        orig = getattr(e, "orig", None)
        if orig is not None:
            msg = str(orig)
        else:
            msg = str(e)
        if not msg or not msg.strip():
            msg = type(e).__name__
        return self._truncate(msg, 500)

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