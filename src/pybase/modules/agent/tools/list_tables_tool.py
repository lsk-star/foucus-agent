from langchain_core.tools import tool

from pybase.modules.sql_processing.schema_provider import SchemaProvider


def create_list_tables_tool(schema_provider: SchemaProvider):
    @tool(description="列出当前数据库的全部表，含描述、关联表（外键指向的其它表）。" +
                      "回答数据问题的第一步：根据用户问题与表描述，挑出相关的表，" +
                      "再用 describeTables 查看这些表的字段详情。" +
                      "关联表能帮你快速判断要 JOIN 哪些表")
    async def list_tables_tool() -> str:
        return await schema_provider.listTables()

    return list_tables_tool
