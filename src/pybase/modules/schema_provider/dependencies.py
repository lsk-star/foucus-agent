from typing import Annotated
from fastapi import Request
from fastapi import Depends

from pybase.core.config import get_settings
from pybase.core.exceptions import DependencyUnavailableError
from pybase.modules.schema_provider.schema_provider import SchemaProvider
from pybase.modules.schema_provider.yaml_provider.component import SchemaCatalogComponent
from pybase.modules.schema_provider.yaml_provider.schema_catalog_service import SchemaCatalogService
from pybase.modules.schema_provider.yaml_provider.yaml_schema_provider import YamlSchemaProvider

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


schema_provider=Annotated[SchemaProvider, Depends(get_schema_provider)]