import logging

from langchain_core.language_models import BaseChatModel

from pybase.modules.agent.middleware.skill_middleware import SkillMiddleware
from pybase.modules.agent.middleware.tool_logging_middleware import ToolLoggingMiddleware
from pybase.modules.agent.schemas import ChatResponse
from pybase.modules.agent.tools import create_skill_content_tool
from pybase.modules.skills.manger import SkillManger
from pybase.modules.skills.service import SkillsService

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, chat_model: BaseChatModel, skill_loader: SkillManger, service: SkillsService) -> None:
        self._chat_model = chat_model
        self._skill_loader = skill_loader
        self._skill_service = service

    async def chat(self, message: str) -> ChatResponse:
        agent = self._build_agent()
        response = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
        return ChatResponse(answer=str(response["messages"][-1].content_blocks))

    def _build_agent(self):
        from langchain.agents import create_agent
        skill_tool = create_skill_content_tool(self._skill_loader)

        agent = create_agent(
            model=self._chat_model,
            system_prompt="你是一个有用的助手回答用户问题",
            tools=[skill_tool],
            middleware=[
                ToolLoggingMiddleware(),
                SkillMiddleware(self._skill_service, self._skill_loader),
            ]
        )
        return agent
