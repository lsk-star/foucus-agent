from fastapi import Request

from .component import RedisComponent
from .checkpoint import RedisCheckpointComponent


def get_redis_component(request: Request) -> RedisComponent | None:
    try:
        return request.app.state.components.get(RedisComponent)
    except LookupError:
        return None


def get_checkpoint_component(request: Request) -> RedisCheckpointComponent | None:
    try:
        return request.app.state.components.get(RedisCheckpointComponent)
    except LookupError:
        return None
