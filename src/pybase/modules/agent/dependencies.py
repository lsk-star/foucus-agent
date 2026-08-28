from typing import Annotated, TYPE_CHECKING

from fastapi import Depends
from langchain_core.language_models import BaseChatModel

from pybase.core.exceptions import DependencyUnavailableError
from pybase.infrastructure.llm.component import LlmComponent
from pybase.infrastructure.llm.dependencies import get_llm_component
from pybase.infrastructure.redis.checkpoint import RedisCheckpointComponent
from pybase.infrastructure.redis.dependencies import get_checkpoint_component
from pybase.modules.account.data_access_guard import DataAccessGuard
from pybase.modules.account.dependencies import get_data_access_guard
from pybase.modules.agent.session.dependencies import get_session_service
from pybase.modules.agent.session.service import SessionService
from pybase.modules.sql_processing.dependencies import get_schema_provider, get_schema_catalog_service, \
    get_sql_safety_guard, get_explain_precheck_service, get_read_only_runner
from pybase.modules.sql_processing.explain_precheck_service import ExplainPrecheckService
from pybase.modules.sql_processing.read_only_runner import ReadOnlyQueryRunner
from pybase.modules.sql_processing.schema_provider import SchemaProvider
from pybase.modules.sql_processing.sql_safety_guard import SqlSafetyGuard
from pybase.modules.sql_processing.yaml_provider.schema_catalog_service import SchemaCatalogService
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
        guard: SqlSafetyGuard = Depends(get_sql_safety_guard),
        precheck_service: ExplainPrecheckService = Depends(get_explain_precheck_service),
        runner: ReadOnlyQueryRunner = Depends(get_read_only_runner),
        data_access_guard: DataAccessGuard = Depends(get_data_access_guard),
        session_service: SessionService = Depends(get_session_service),
        checkpoint: RedisCheckpointComponent | None = Depends(get_checkpoint_component),
):
    from pybase.modules.agent.service import AgentService

    return AgentService(
        chat_model, skill_loader, service, schema_provider,
        catalog_service, guard, precheck_service, runner, data_access_guard, session_service, checkpoint,
    )


ChatModelDep = Annotated[BaseChatModel, Depends(get_chat_model)]
AgentServiceDep = Annotated["AgentService", Depends(get_agent_service)]
