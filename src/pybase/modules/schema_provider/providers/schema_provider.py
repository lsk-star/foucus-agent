from typing import Protocol


class SchemaProvider(Protocol):
    """SchemaProvider 模块的提供器。"""

    async def listTables(self) -> str:
        """列出所有表。"""

    async def describeTables(self,tableNames: list[str]) -> str:
        """描述指定表。"""
