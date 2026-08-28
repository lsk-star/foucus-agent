from __future__ import annotations

from typing import Any

from pybase.contracts.lifecycle import LifecycleComponent, ReadinessStatus
from pybase.core.config import RedisSettings
from pybase.core.exceptions import ConfigurationError


class RedisCheckpointComponent(LifecycleComponent):
    name = "redis-checkpoint"

    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings
        self.checkpointer: Any | None = None

    async def start(self) -> None:
        try:
            from langgraph.checkpoint.redis import AsyncRedisSaver
        except ImportError as exc:
            raise ConfigurationError("Redis checkpoint 已启用，但未安装依赖。请执行: uv sync") from exc
        ttl = {"default_ttl": self._settings.ttl_seconds, "refresh_on_read": True}
        try:
            self.checkpointer = AsyncRedisSaver(redis_url=self._settings.url, ttl=ttl)
        except TypeError:
            self.checkpointer = AsyncRedisSaver(redis_url=self._settings.url)
        setup = getattr(self.checkpointer, "asetup", None)
        if setup is not None:
            await setup()

    async def stop(self) -> None:
        if self.checkpointer is not None:
            close = getattr(self.checkpointer, "aclose", None)
            if close is not None:
                await close()
        self.checkpointer = None

    async def readiness(self) -> ReadinessStatus:
        return ReadinessStatus(self.name, self.checkpointer is not None)
