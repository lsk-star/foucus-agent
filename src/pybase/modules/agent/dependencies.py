from typing import Annotated, TYPE_CHECKING

from fastapi import Depends
from langchain_core.language_models import BaseChatModel

from pybase.core.exceptions import DependencyUnavailableError
from pybase.infrastructure.llm.component import LlmComponent
from pybase.infrastructure.llm.dependencies import get_llm_component
from pybase.modules.schema_provider.dependencies import get_schema_provider, get_schema_catalog_service
from pybase.modules.schema_provider.schema_provider import SchemaProvider
from pybase.modules.schema_provider.yaml_provider.schema_catalog_service import SchemaCatalogService
from pybase.modules.skills.dependencies import get_file_skill_loader, get_skills_service
from pybase.modules.skills.manger import SkillManger
from pybase.modules.skills.service import SkillsService

if TYPE_CHECKING:
    from pybase.modules.agent.service import AgentService


async def get_chat_model(llm: LlmComponent = Depends(get_llm_component)) -> BaseChatModel:
    if llm.chat_model is None:
        raise DependencyUnavailableError("LLM 尚未就绪")
    return llm.chat_model


async def get_agent_service(
        chat_model: BaseChatModel = Depends(get_chat_model),
        skill_loader: SkillManger = Depends(get_file_skill_loader),
        service: SkillsService = Depends(get_skills_service),
        schema_provider: SchemaProvider = Depends(get_schema_provider),
        catalog_service: SchemaCatalogService = Depends(get_schema_catalog_service),
):
    from pybase.modules.agent.service import AgentService

    return AgentService(chat_model, skill_loader, service, schema_provider, catalog_service)


ChatModelDep = Annotated[BaseChatModel, Depends(get_chat_model)]
AgentServiceDep = Annotated["AgentService", Depends(get_agent_service)]
