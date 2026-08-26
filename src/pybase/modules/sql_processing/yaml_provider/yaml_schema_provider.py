from pybase.modules.sql_processing.yaml_provider.schema_catalog_service import SchemaCatalogService
from pybase.modules.sql_processing.schema_provider import SchemaProvider
from pybase.modules.sql_processing.yaml_provider.schemas import Table


class YamlSchemaProvider(SchemaProvider):

    def __init__(self, schema_catalog_service: SchemaCatalogService):
        self._schema_catalog_service = schema_catalog_service

    """YAMLSchemaProvider 模块的提供器。"""

    async def listTables(self) -> str:
        """列出所有表。"""
        all_entries = await self._schema_catalog_service.listAll()

        if not all_entries:
            return "schema 字典为空——可能是配置文件未加载，请联系运维检查 schema/dodo_agentx.yml。"

        lines = [f"当前数据库共 {len(all_entries)} 个表（YAML 静态字典）：", ""]
        for e in all_entries:
            line = f"- {e.name}"
            if e.description:
                line += f"（{e.description}）"
            if e.related_tables:
                line += f" → 关联: {', '.join(e.related_tables)}"
            lines.append(line)

        return "\n".join(lines).strip()

    async def describeTables(self, tableNames: list[str]) -> str:
        """描述指定表。"""
        if not tableNames:
            return "tableNames 为空。请传入具体表名（逗号分隔），或先调 listTables 查看可用的表。"
        result = await self._schema_catalog_service.batch_find(tableNames)
        if not result.found:
            return f"未找到相关表 {', '.join(result.missing)}。请确认表名拼写（建议先调 listTables 看准确表名）。"

        lines = []

        for f in result.found:
            lines.append(self._formatTableLegacy(f))

        if result.missing:
            lines.append(f"⚠ 未找到相关表 {', '.join(result.missing)}。（已跳过；建议调 listTables 核对准确表名）")

        return "\n".join(lines).strip()

    def _formatTableLegacy(self, table: Table) -> str:
        lines = [f"- {table.name}"]
        if table.description:
            lines[0] += (f"({table.description})")
        lines[0] += "："
        lines[0] += "字段："

        for c in table.columns:
            col = f"- {c.name}"
            if c.type:
                col += f"（{c.type}）"
            if c.key:
                col += f"，（{c.key}）"
            if not c.nullable:
                col += f"，not null"
            if c.comment:
                col += f"--{c.comment}"
            lines.append(col)

        if table.foreign_keys:
            lines.append("")
            lines.append("外键：")

            for f in table.foreign_keys:
                lines.append(f"- {f.column} → {f.ref_table}.{f.ref_column}")

        return "\n".join(lines).strip()
