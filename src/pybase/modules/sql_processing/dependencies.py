from typing import Annotated
from fastapi import Request
from fastapi import Depends

from pybase.core.config import get_settings
from pybase.core.exceptions import DependencyUnavailableError
from pybase.infrastructure.database.component import DatabaseComponent
from pybase.modules.sql_processing.explain_precheck_service import ExplainPrecheckService
from pybase.modules.sql_processing.read_only_runner import ReadOnlyQueryRunner
from pybase.modules.sql_processing.schema_provider import SchemaProvider
from pybase.modules.sql_processing.sql_safety_guard import SqlSafetyGuard
from pybase.modules.sql_processing.yaml_provider.component import SchemaCatalogComponent
from pybase.modules.sql_processing.yaml_provider.schema_catalog_service import SchemaCatalogService
from pybase.modules.sql_processing.yaml_provider.yaml_schema_provider import YamlSchemaProvider

settings=get_settings()


async def get_schema_catalog_service(request: Request) -> SchemaCatalogService:
    try:
        return request.app.state.components.get(SchemaCatalogComponent).service
    except LookupError as exc:
        raise DependencyUnavailableError("Schema catalog 未启用") from exc


async def get_schema_provider(catalog_service: SchemaCatalogService=Depends(get_schema_catalog_service)) -> SchemaProvider:
    if settings.schema_provider.source=="yaml":
        return YamlSchemaProvider(catalog_service)
    else:
        raise ValueError(f"不支持的 schema_provider.source: {settings.schema_provider.source}")


async def get_sql_safety_guard() -> SqlSafetyGuard:
    return SqlSafetyGuard()


async def get_read_only_runner(request: Request) -> ReadOnlyQueryRunner:
    try:
        database = request.app.state.components.get(DatabaseComponent)
    except LookupError as exc:
        raise DependencyUnavailableError("数据库能力未启用，无法创建 ReadOnlyQueryRunner") from exc
    if database.engine is None:
        raise DependencyUnavailableError("数据库尚未就绪，无法创建 ReadOnlyQueryRunner")
    return ReadOnlyQueryRunner(engine=database.engine)


async def get_explain_precheck_service(runner: ReadOnlyQueryRunner = Depends(get_read_only_runner)) -> ExplainPrecheckService:
    return ExplainPrecheckService(runner=runner)


schema_provider=Annotated[SchemaProvider, Depends(get_schema_provider)]
sql_safety_guard=Annotated[SqlSafetyGuard, Depends(get_sql_safety_guard)]
read_only_runner=Annotated[ReadOnlyQueryRunner, Depends(get_read_only_runner)]
explain_precheck_service=Annotated[ExplainPrecheckService, Depends(get_explain_precheck_service)]