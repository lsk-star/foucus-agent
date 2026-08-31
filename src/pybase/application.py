import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pybase.contracts.lifecycle import ComponentRegistry
from pybase.core.config import Settings, get_settings
from pybase.core.exceptions import ConfigurationError
from pybase.core.logging import configure_logging
from pybase.presentation.exception_handlers import register_exception_handlers
from pybase.presentation.middleware import register_middlewares
from pybase.presentation.router import build_api_router
from pybase.modules.health.router import router as health_router

logger = logging.getLogger(__name__)


def _build_components(settings: Settings) -> ComponentRegistry:
    registry = ComponentRegistry()

    #
    if settings.schema_provider.source == "yaml":
        from pybase.modules.sql_processing.yaml_provider.component import SchemaCatalogComponent
        registry.add(SchemaCatalogComponent())
    if settings.database.enabled:
        try:
            from pybase.infrastructure.database.component import DatabaseComponent
        except ImportError as exc:
            raise ConfigurationError("...") from exc
        registry.add(DatabaseComponent(settings.database))

    if settings.redis.enabled:
        try:
            from pybase.infrastructure.redis.component import RedisComponent
            from pybase.infrastructure.redis.checkpoint import RedisCheckpointComponent
        except ImportError as exc:
            raise ConfigurationError("Redis 已启用，但未安装 redis checkpoint 依赖。请执行: uv sync") from exc
        registry.add(RedisComponent(settings.redis))
        registry.add(RedisCheckpointComponent(settings.redis))

    if settings.llm.enabled:
        try:
            from pybase.infrastructure.llm.component import LlmComponent
        except ImportError as exc:
            raise ConfigurationError(
                "LLM 已启用，但未安装依赖。请执行: uv sync --extra llm"
            ) from exc
        registry.add(LlmComponent(settings.llm))
    #
    if settings.mcp_echarts.enabled:
        try:
            from pybase.infrastructure.mcp.component import (
                McpEchartsComponent,
            )
        except ImportError as exc:
            raise ConfigurationError(
                "mcp-echarts 已启用，但未安装 MCP 依赖。"
                "请执行: uv sync --extra mcp"
            ) from exc

        registry.add(
            McpEchartsComponent(
                settings.mcp_echarts
            )
        )

    return registry


def create_application(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.logging)
    components = _build_components(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("Starting application: %s", settings.app.name)
        await components.start()
        try:
            yield
        finally:
            await components.stop()
            logger.info("Application stopped: %s", settings.app.name)

    app = FastAPI(
        title=settings.app.name,
        debug=settings.app.debug,
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.components = components
    register_middlewares(app)
    register_exception_handlers(app)

    # 探针不属于业务 API，因此固定在根路径，不放入版本化路由。
    app.include_router(health_router)
    app.include_router(build_api_router(settings), prefix=settings.app.api_prefix)
    return app
