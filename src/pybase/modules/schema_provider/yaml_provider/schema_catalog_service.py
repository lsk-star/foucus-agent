from pathlib import Path

import yaml

from pybase.modules.schema_provider.schemas import (
    Column,
    FkDesc,
    ForeignKey,
    GlossaryTerm,
    SchemaCatalog,
    Table,
    TableEntry, LookupResult,
)

_SCHEMA_DIR = Path(__file__).resolve().parents[4] / "resources" / "schema"
_DEFAULT_CATALOG = _SCHEMA_DIR / "dodo_agentx.yml"


class SchemaCatalogService:
    def __init__(self, catalog_path: Path | None = None):
        self._catalog_path = catalog_path or _DEFAULT_CATALOG
        self.catalog: SchemaCatalog | None = None

    # 项目启动需要调用一次
    async def load(self) -> None:
        with open(self._catalog_path, encoding="utf-8") as f:
            raw: dict = yaml.safe_load(f)

        tables: list[Table] = []
        for table_name, table_def in raw.get("tables", {}).items():
            columns = [
                Column(
                    name=col_name,
                    type=col_attr["type"],
                    comment=col_attr["comment"],
                    key=col_attr.get("key"),
                    nullable=col_attr.get("nullable", True),
                )
                for col_name, col_attr in table_def.get("columns", {}).items()
            ]

            foreign_keys = [
                ForeignKey(**fk) for fk in table_def.get("foreignKeys", [])
            ]

            tables.append(
                Table(
                    name=table_name,
                    description=table_def.get("description", ""),
                    columns=columns,
                    foreignKeys=foreign_keys,
                )
            )

        glossary: list[GlossaryTerm] = [
            GlossaryTerm(**term_def) for term_def in raw.get("glossary", [])
        ]

        self._catalog = SchemaCatalog(tables=tables, glossary=glossary)

    def _ensure_loaded(self) -> None:
        if self._catalog is None:
            raise RuntimeError("catalog not loaded, call load() first")

    def _to_entry(self, table: Table) -> TableEntry:
        self._ensure_loaded()

        # 当前表外键指向的表名
        outgoing = {fk.ref_table for fk in table.foreign_keys}

        # 其他表外键指向当前表的表名
        # incoming = {
        #     other.name
        #     for other in self._catalog.tables
        #     if any(fk.ref_table == table.name for fk in other.foreign_keys)
        # }
        # 去重并排序
        # related = sorted(outgoing | incoming)
        related = sorted(set(outgoing))

        return TableEntry(
            name=table.name,
            description=table.description,
            related_tables=related,
        )

    async def listAll(self) -> list[TableEntry]:
        """列出全部表（含描述 + 关联表）。"""
        if self._catalog is None:
            await self.load()
        return [self._to_entry(t) for t in self._catalog.tables]

    async def find(self, name: str) -> Table | None:
        """按表名查详情；找不到返回 None。"""
        if self._catalog is None:
            await self.load()
        for table in self._catalog.tables:
            if table.name == name:
                return table
        return None

    async def batch_find(self, names: list[str]) -> LookupResult:
        """批量按表名查详情；找不到的对应位置返回 None。"""
        if self._catalog is None:
            await self.load()
        found = []
        missing = []
        for name in names:
            table = await self.find(name)
            if table is not None:
                found.append(table)
            else:
                missing.append(name)
        return LookupResult(found=found, missing=missing)

    async def glossary(self) -> list[GlossaryTerm]:
        """
        获取所有业务术语。
        """
        if self._catalog is None:
            await self.load()
        return self._catalog.glossary
