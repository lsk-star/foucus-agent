import logging

from langchain_core.language_models import BaseChatModel

from pybase.modules.agent.middleware.skill_middleware import SkillMiddleware
from pybase.modules.agent.middleware.tool_logging_middleware import ToolLoggingMiddleware
from pybase.modules.agent.schemas import ChatResponse
from pybase.modules.agent.tools.lookup_glossary_tool import create_lookup_glossary_tool

from pybase.modules.schema_provider.schema_provider import SchemaProvider
from pybase.modules.schema_provider.yaml_provider.schema_catalog_service import SchemaCatalogService
from pybase.modules.skills.manger import SkillManger
from pybase.modules.skills.service import SkillsService
from pybase.modules.agent.tools.skill_tool import create_skill_content_tool
from pybase.modules.agent.tools.describe_table_tool import create_describe_table_tool
from pybase.modules.agent.tools.list_tables_tool import create_list_tables_tool

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, chat_model: BaseChatModel, skill_loader: SkillManger, service: SkillsService,
                 schema_provider: SchemaProvider,
                 catalog_service: SchemaCatalogService) -> None:
        self._chat_model = chat_model
        self._skill_loader = skill_loader
        self._skill_service = service
        self._schema_provider = schema_provider
        self._catalog_service = catalog_service

    async def chat(self, message: str) -> ChatResponse:
        agent = await self._build_agent()
        response = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
        return ChatResponse(answer=str(response["messages"][-1].content_blocks))

    async def _build_agent(self):
        from langchain.agents import create_agent

        agent = create_agent(
            model=self._chat_model,
            system_prompt="你是一个有用的助手回答用户问题",
            tools=await self._build_tools(),
            middleware=[
                ToolLoggingMiddleware(),
                SkillMiddleware(self._skill_service, self._skill_loader),
            ]
        )
        return agent

    async def _build_tools(self):
        skill_tool = create_skill_content_tool(self._skill_loader)
        list_tables = create_list_tables_tool(self._schema_provider)
        describe_tables = create_describe_table_tool(self._schema_provider)
        lookup_glossary_tool = create_lookup_glossary_tool(await self._catalog_service.glossary())

        return [skill_tool, list_tables, describe_tables, lookup_glossary_tool]
