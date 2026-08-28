import json
import asyncio
import logging
import time
import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from pybase.modules.account.data_access_guard import DataAccessGuard
from pybase.modules.agent.middleware.skill_middleware import SkillMiddleware
from pybase.modules.agent.middleware.tool_logging_middleware import ToolLoggingMiddleware
from pybase.modules.agent.middleware.message_window_middleware import MessageWindowMiddleware
from pybase.infrastructure.redis.checkpoint import RedisCheckpointComponent
from pybase.modules.agent.schemas import ChatResponse
from pybase.modules.agent.session.dependencies import SessionServiceDep
from pybase.modules.agent.session.schemas import ConversationCreate
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
from pybase.modules.agent.emitter import send_text, send_thinking, send_tool_call, send_tool_result, send_done, \
    send_error

logger = logging.getLogger(__name__)
MAX_MESSAGES = 150


class AgentService:
    def __init__(self, chat_model: BaseChatModel, skill_loader: SkillManger, service: SkillsService,
                 schema_provider: SchemaProvider,
                 catalog_service: SchemaCatalogService,
                 sql_safety_guard: SqlSafetyGuard,
                 explain_precheck_service: ExplainPrecheckService,
                 runner: ReadOnlyQueryRunner,
                 data_access_guard: DataAccessGuard,
                 session_service: SessionServiceDep, checkpoint: RedisCheckpointComponent | None = None) -> None:
        self._chat_model = chat_model
        self._skill_loader = skill_loader
        self._skill_service = service
        self._schema_provider = schema_provider
        self._catalog_service = catalog_service
        self._sql_safety_guard = sql_safety_guard
        self._explain_precheck_service = explain_precheck_service
        self._runner = runner
        self._data_access_guard = data_access_guard
        self._session_service = session_service
        self._checkpoint = checkpoint

    # 简单测试，不使用会话
    async def chat(self, message: str, user: UserRead, conversation_id: str | None = None) -> ChatResponse:
        agent = await self._build_agent(user)
        config = {"configurable": {"thread_id": f"{user.id}-{conversation_id or uuid.uuid4()}"}}
        response = await agent.ainvoke({"messages": [{"role": "user", "content": message}]}, config=config)
        return ChatResponse(answer=str(response["messages"][-1].content_blocks))

    async def chat_stream(self, message: str, user: UserRead, conversation_id: str | None = None):

        # 会话标题默认取消息前30个字符
        title = message[:30]
        # 判断是否有会话id，没有则创建新会话并生成
        new_conversation = conversation_id is None
        if new_conversation:
            conversation_id = (await self._session_service.create(
                user.id, ConversationCreate(title=title)
            )).conversation_no
        elif not await self._session_service.exists(user.id, conversation_id):
            yield send_error("会话不存在或无权访问")
            yield send_done()
            return

        # 收集完整回答文本，用于对话结束后写入消息表
        full_answer = ""
        start_time = time.time()
        has_error = False
        cancelled = False
        try:
            config: RunnableConfig = {"configurable": {"thread_id": f"{user.id}-{conversation_id}"}}
            agent = await self._build_agent(user)
            input_data = {"messages": [{"role": "user", "content": message}]}
            stream = await agent.astream_events(input_data, config=config, version="v3")
            queue: asyncio.Queue[tuple[str, object] | None] = asyncio.Queue()

            async def consume_messages() -> None:
                try:
                    async for message_stream in stream.messages:
                        async for reasoning in message_stream.reasoning:
                            await queue.put(("thinking", reasoning))
                        async for text_delta in message_stream.text:
                            await queue.put(("text", text_delta))
                finally:
                    await queue.put(None)

            async def consume_tools() -> None:
                try:
                    async for tool_stream in stream.tool_calls:
                        tool_id = getattr(tool_stream, "tool_call_id", None) or getattr(tool_stream, "id", None) or ""
                        name = getattr(tool_stream, "tool_name", "")
                        args = getattr(tool_stream, "input", {}) or {}
                        if tool_id or name:
                            await queue.put(("tool_call", (tool_id, name, args)))
                        output = getattr(tool_stream, "output", None)
                        if output is not None:
                            await queue.put(("tool_result", (tool_id, output)))
                finally:
                    await queue.put(None)

            tasks = [asyncio.create_task(consume_messages()), asyncio.create_task(consume_tools())]
            finished = 0
            try:
                while finished < len(tasks):
                    item = await queue.get()
                    if item is None:
                        finished += 1
                        continue
                    kind, payload = item
                    if kind == "thinking":
                        yield send_thinking(str(payload))
                    elif kind == "text":
                        full_answer += str(payload)
                        yield send_text(str(payload))
                    elif kind == "tool_call":
                        tool_id, name, args = payload
                        yield send_tool_call(id=str(tool_id), name=str(name),
                                             args=args if isinstance(args, dict) else {})
                    elif kind == "tool_result":
                        tool_id, output = payload
                        yield send_tool_result(id=str(tool_id), content=str(output))
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                        raise result
        except asyncio.CancelledError:
            has_error = True
            cancelled = True
            raise
        except Exception:
            logger.exception("Error in chat_stream")
            has_error = True
            yield send_error("服务内部错误，请稍后重试")
        finally:
            # 对话结束后，将用户问题和最终答案写入消息表
            if not has_error and full_answer:
                duration_s = int(time.time() - start_time)
                try:
                    await self._session_service.save_messages(
                        user_id=user.id, conversation_no=conversation_id,
                        user_content=message, assistant_content=full_answer,
                        duration_s=duration_s,
                    )
                except Exception:
                    logger.exception("Failed to persist chat messages")
            # 仅新建会话时返回 conversation_id，前端已有则无需重复返回
            if not cancelled:
                yield send_done(conversation_id=conversation_id if new_conversation else None)

    async def _build_agent(self, user: UserRead):
        from langchain.agents import create_agent

        agent = create_agent(
            model=self._chat_model,
            system_prompt=await self._build_system_prompt(user),
            tools=await self._build_tools(user),
            middleware=[
                ToolLoggingMiddleware(),
                SkillMiddleware(self._skill_service, self._skill_loader),
                MessageWindowMiddleware(MAX_MESSAGES),
            ],
            checkpointer=self._checkpoint.checkpointer if self._checkpoint else None,
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

        system_prompt = "你是一个有用的助手KK，回答用户问题"

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


