from langchain_core.tools import tool

from pybase.modules.schema_provider.schema_provider import SchemaProvider

from pydantic import BaseModel, Field


class DescribeTableArgs(BaseModel):
    table_names: list[str] = Field(description="要查看的表的名称列表")


def create_describe_table_tool(schema_provider: SchemaProvider):
    @tool(description="查看指定表的字段详情（字段名/类型/可空/键/注释/外键/示例值）。" +
                      "写 SQL 前必须先调本工具看真实结构，严禁凭记忆写 SQL。" +
                      "建议先调 listTables 挑出相关表，再把表名传给本工具。" +
                      "字段是否当指标/维度/时间，由你（LLM）根据字段注释 + 类型 + 示例值自行判断。"
        , args_schema=DescribeTableArgs)
    async def describe_table_tool(table_names: list[str]) -> str:
        return await schema_provider.describeTables(table_names)

    return describe_table_tool
