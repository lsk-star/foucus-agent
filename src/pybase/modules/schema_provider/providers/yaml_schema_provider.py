from pybase.modules.schema_provider.providers.schema_catalog_service import SchemaCatalogService
from pybase.modules.schema_provider.providers.schema_provider import SchemaProvider


class YamlSchemaProvider(SchemaProvider):

    def __init__(self, schema_catalog_service: SchemaCatalogService):
        self._schema_catalog_service = schema_catalog_service


    """YAMLSchemaProvider 模块的提供器。"""

    async def listTables(self) -> str:
        """列出所有表。"""



    async def describeTables(self,tableNames: list[str]) -> str:
        """描述指定表。"""
