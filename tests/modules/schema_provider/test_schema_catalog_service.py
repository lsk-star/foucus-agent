import asyncio
from pathlib import Path

from pybase.modules.schema_provider.yaml_provider.schema_catalog_service import SchemaCatalogService

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run(coro):
    return asyncio.run(coro)


def print_separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_entry(entry) -> None:
    print(f"  name:            {entry.name}")
    print(f"  description:     {entry.description}")
    print(f"  related_tables:  {entry.related_tables}")


def print_table(table) -> None:
    print(f"  name:        {table.name}")
    print(f"  description: {table.description}")
    print(f"  columns:")
    for col in table.columns:
        print(f"    {col.name:20s} {col.type:20s} {col.comment}")
    print(f"  foreign_keys:")
    for fk in table.foreign_keys:
        print(f"    {fk.column} -> {fk.ref_table}.{fk.ref_column}")


def test_load_simple() -> None:
    print_separator("test_load_simple  —  simple.yml")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "simple.yml")
    run(svc.load())
    catalog = svc._catalog
    print(f"  tables loaded:   {len(catalog.tables)}")
    print(f"  glossary loaded: {len(catalog.glossary)}")
    for t in catalog.tables:
        print(f"    - {t.name} ({len(t.columns)} cols, {len(t.foreign_keys)} fks)")


def test_load_self_ref() -> None:
    print_separator("test_load_self_ref  —  self_ref.yml (自引用外键)")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "self_ref.yml")
    run(svc.load())
    catalog = svc._catalog
    print(f"  tables loaded:   {len(catalog.tables)}")
    for t in catalog.tables:
        print(f"    - {t.name} ({len(t.columns)} cols, {len(t.foreign_keys)} fks)")
        for fk in t.foreign_keys:
            print(f"        {fk.column} -> {fk.ref_table}.{fk.ref_column}")


def test_load_minimal() -> None:
    print_separator("test_load_minimal  —  minimal.yml (单表无外键无术语)")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "minimal.yml")
    run(svc.load())
    catalog = svc._catalog
    print(f"  tables loaded:   {len(catalog.tables)}")
    print(f"  glossary loaded: {len(catalog.glossary)}")


def test_list_all() -> None:
    print_separator("test_listAll  —  simple.yml")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "simple.yml")
    entries = run(svc.listAll())
    print(f"  total entries: {len(entries)}")
    for e in entries:
        print_entry(e)
        print()


def test_find_found() -> None:
    print_separator("test_find  —  找到 order")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "simple.yml")
    result = run(svc.find("order"))
    if result is None:
        print("  result: None")
    else:
        print_table(result)


def test_find_not_found() -> None:
    print_separator("test_find  —  找不到 payment")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "simple.yml")
    result = run(svc.find("payment"))
    print(f"  result: {result}")


def test_batch_find() -> None:
    print_separator("test_batch_find  —  [user, xxx, product, order]")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "simple.yml")
    result = run(svc.batch_find(["user", "xxx", "product", "order"]))
    print(f"  found:   {len(result.found)} tables")
    for t in result.found:
        print(f"    - {t.name}")
    print(f"  missing: {result.missing}")


def test_list_all_self_ref() -> None:
    print_separator("test_listAll  —  self_ref.yml (自引用)")
    svc = SchemaCatalogService(catalog_path=FIXTURES / "self_ref.yml")
    entries = run(svc.listAll())
    for e in entries:
        print_entry(e)
        print()


if __name__ == "__main__":
    test_load_simple()
    test_load_self_ref()
    test_load_minimal()
    test_list_all()
    test_find_found()
    test_find_not_found()
    test_batch_find()
    test_list_all_self_ref()
    print_separator("ALL TESTS DONE")