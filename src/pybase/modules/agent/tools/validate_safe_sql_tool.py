from typing import Annotated

from langchain_core.tools import tool
from pydantic import Field

from pybase.modules.sql_processing.sql_safety_guard import SqlSafetyGuard


def create_sql_safe_sql_tool(sql_safety_guard: SqlSafetyGuard):
    """ 创建 SQL 安全守卫工具。"""

    @tool(description="校验 SQL 是否安全（白名单/防注入/强制 LIMIT）。生成 SQL 后、执行前必须调用。" +
                      "参数名严格为 sql，严禁使用任何其他参数名。" +
                      "传错会收到 \"参数名错误\" 提示，必须改用 sql 重新调用。" +
                      "返回 valid=true 时给出可直接执行的安全 SQL（已注入 LIMIT）；" +
                      "返回 valid=false 时按 reason 修改 SQL 后重新校验。" +
                      "禁止写 INSERT/UPDATE/DELETE/DROP 等非查询语句；禁止多语句拼接；禁止危险函数。")
    def validate_sql(sql: Annotated[str, Field(description="校验的SQL 语句")]) -> str:
        """ 验证 SQL 语句是否安全。"""
        if not sql:
            return "❌ 参数错误：sql 为空。本工具参数名严格为 `sql`，禁止用任何其他名字。请重新调用 validate_sql，把 SQL 语句放在 `sql` 参数中。"

        result = sql_safety_guard.validate(sql)

        if result.valid:
            return f"校验通过。安全 SQL（已注入/截断 LIMIT，可直接交给 executeSql 执行）：\n{result.safe_sql}"
        else:
            return f"校验未通过：{result.reason} 请根据上述提示修改 SQL 后重新调用本工具校验。"

    return validate_sql
