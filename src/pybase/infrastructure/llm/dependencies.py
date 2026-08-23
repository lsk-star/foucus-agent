from fastapi import Request

from pybase.core.exceptions import DependencyUnavailableError
from pybase.infrastructure.llm.component import LlmComponent


async def get_llm_component(request: Request) -> LlmComponent:
    try:
        return request.app.state.components.get(LlmComponent)
    except LookupError as exc:
        raise DependencyUnavailableError("LLM 能力未启用") from exc