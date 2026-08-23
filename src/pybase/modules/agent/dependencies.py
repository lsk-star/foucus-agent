from typing import Annotated, TYPE_CHECKING

from fastapi import Depends
from langchain_core.language_models import BaseChatModel

from pybase.core.exceptions import DependencyUnavailableError
from pybase.infrastructure.llm.component import LlmComponent
from pybase.infrastructure.llm.dependencies import get_llm_component

if TYPE_CHECKING:
    from pybase.modules.agent.service import AgentService


async def get_chat_model(llm: LlmComponent = Depends(get_llm_component)) -> BaseChatModel:
    if llm.chat_model is None:
        raise DependencyUnavailableError("LLM 尚未就绪")
    return llm.chat_model


async def get_agent_service(chat_model: BaseChatModel = Depends(get_chat_model)):
    from pybase.modules.agent.service import AgentService

    return AgentService(chat_model)


ChatModelDep = Annotated[BaseChatModel, Depends(get_chat_model)]
AgentServiceDep = Annotated["AgentService", Depends(get_agent_service)]