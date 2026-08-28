from __future__ import annotations

import logging
from typing import Any

from pybase.contracts.lifecycle import LifecycleComponent, ReadinessStatus
from pybase.core.config import RedisSettings
from pybase.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class RedisComponent(LifecycleComponent):
    name = "redis"

    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings
        self.client: Any | None = None
        self._startup_error: str | None = None

    async def start(self) -> None:
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise ConfigurationError(
                "Redis 已启用，但未安装 redis checkpoint 依赖。请执行: uv sync"
            ) from exc

        self.client = Redis.from_url(self._settings.url, decode_responses=False)
        try:
            await self.client.ping()
            logger.info("Redis 连接成功")
        except Exception as exc:
            self._startup_error = str(exc)
            await self.stop()
            raise ConfigurationError("Redis 连接失败") from exc

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.client = None

    async def readiness(self) -> ReadinessStatus:
        if self.client is None:
            return ReadinessStatus(self.name, False, self._startup_error or "Redis 尚未初始化")
        try:
            await self.client.ping()
            return ReadinessStatus(self.name, True)
        except Exception:
            return ReadinessStatus(self.name, False, "Redis 暂不可用")
