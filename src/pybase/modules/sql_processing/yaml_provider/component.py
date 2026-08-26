import logging

from pybase.contracts.lifecycle import ReadinessStatus, LifecycleComponent
from pybase.modules.sql_processing.yaml_provider.schema_catalog_service import SchemaCatalogService

logger = logging.getLogger(__name__)

class SchemaCatalogComponent(LifecycleComponent):
    name = "schema_catalog"

    def __init__(self) -> None:
        self.service = SchemaCatalogService()

    async def start(self) -> None:
        await self.service.load()
        logger.info("初始化 Schema catalog 组件，加载路径: %s", self.service._catalog_path)

    async def stop(self) -> None:
        self.service.catalog = None

    async def readiness(self) -> ReadinessStatus:
        if self.service.catalog is None:
            return ReadinessStatus(self.name, False, "catalog 尚未加载")
        return ReadinessStatus(self.name, True)