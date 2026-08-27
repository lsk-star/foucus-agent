import logging

from langchain_core.language_models import BaseChatModel

from pybase.modules.account.data_access_guard import DataAccessGuard
from pybase.modules.agent.middleware.skill_middleware import SkillMiddleware
from pybase.modules.agent.middleware.tool_logging_middleware import ToolLoggingMiddleware
from pybase.modules.agent.schemas import ChatResponse
from pybase.modules.agent.tools.lookup_glossary_tool import create_lookup_glossary_tool
from pybase.modules.agent.tools.validate_safe_sql_tool import create_sql_safe_sql_tool
from pybase.modules.auth.schemas import UserRead

from pybase.modules.sql_processing.explain_precheck_service import ExplainPrecheckService
from pybase.modules.sql_processing.read_only_runner import ReadOnlyQueryRunner
from pybase.modules.sql_processing.schema_provider import SchemaProvider
from pybase.modules.sql_processing.sql_safety_guard import SqlSafetyGuard
from pybase.modules.sql_processing.yaml_provider.schema_catalog_service import SchemaCatalogService
from pybase.modules.skills.manger import SkillManger
from pybase.modules.skills.service import SkillsService
from pybase.modules.agent.tools.skill_tool import create_skill_content_tool
from pybase.modules.agent.tools.describe_table_tool import create_describe_table_tool
from pybase.modules.agent.tools.list_tables_tool import create_list_tables_tool
from pybase.modules.agent.tools.execute_sql_tool import create_execute_sql_tool

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, chat_model: BaseChatModel, skill_loader: SkillManger, service: SkillsService,
                 schema_provider: SchemaProvider,
                 catalog_service: SchemaCatalogService,
                 sql_safety_guard: SqlSafetyGuard,
                 explain_precheck_service: ExplainPrecheckService,
                 runner: ReadOnlyQueryRunner,
                 data_access_guard: DataAccessGuard) -> None:
        self._chat_model = chat_model
        self._skill_loader = skill_loader
        self._skill_service = service
        self._schema_provider = schema_provider
        self._catalog_service = catalog_service
        self._sql_safety_guard = sql_safety_guard
        self._explain_precheck_service = explain_precheck_service
        self._runner = runner
        self._data_access_guard = data_access_guard

    async def chat(self, message: str, user: UserRead) -> ChatResponse:
        agent = await self._build_agent(user)
        response = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
        return ChatResponse(answer=str(response["messages"][-1].content_blocks))

    async def _build_agent(self, user: UserRead):
        from langchain.agents import create_agent

        agent = create_agent(
            model=self._chat_model,
            system_prompt=await self._build_system_prompt(user),
            tools=await self._build_tools(user),
            middleware=[
                ToolLoggingMiddleware(),
                SkillMiddleware(self._skill_service, self._skill_loader),
            ]
        )
        return agent

    async def _build_tools(self, user: UserRead):
        skill_tool = create_skill_content_tool(self._skill_loader)
        list_tables = create_list_tables_tool(self._schema_provider)
        describe_tables = create_describe_table_tool(self._schema_provider)
        lookup_glossary_tool = create_lookup_glossary_tool(await self._catalog_service.glossary())
        validate_sql_tool = create_sql_safe_sql_tool(self._sql_safety_guard)
        execute_sql_tool = create_execute_sql_tool(
            self._sql_safety_guard, self._explain_precheck_service, self._runner,
            self._data_access_guard, user,
        )
        return [skill_tool, list_tables, describe_tables, lookup_glossary_tool, validate_sql_tool, execute_sql_tool]

    async def _build_system_prompt(self, user: UserRead):

        system_prompt = "你是一个有用的助手回答用户问题"

        # 用户信息
        user_info = f"当前用户姓名: {user.real_name}, 职位: {user.job_title}\n"
        system_prompt += user_info

        # 查询用户的数据权限范围
        scope = await self._data_access_guard.get_data_scope(user.id, user.role == "admin")
        if scope.is_admin:
            # 管理员：无需过滤
            scope_hint = (
                "《DataScope》\n"
                "当前用户是管理员，可访问所有广告账户数据，】\n"
                "《DataScope/》"
            )
        elif scope.has_access:
            # 普通用户：告知可访问的账户ID列表，要求生成SQL时主动加上过滤条件
            account_names = await self._data_access_guard.get_account_names(scope.account_ids)
            scope_hint = (
                "《DataScope》\n"
                f"当前用户可访问的广告账户名称: [{account_names}]\n"
                "《DataScope/》"
            )
        else:
            # 无权限用户：告知 LLM 直接回复用户无权限
            scope_hint = (
                "《DataScope》\n"
                "当前用户没有任何广告账户的数据权限，无法查询业务数据。\n"
                "请直接告知用户：您当前没有数据权限，请联系管理员分配广告账户。\n"
                "《DataScope/》"
            )

        system_prompt += scope_hint
        return system_prompt
