import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from pybase.modules.agent.schemas import ChatResponse

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, chat_model: BaseChatModel) -> None:
        self._chat_model = chat_model

    async def chat(self, message: str) -> ChatResponse:
        agent = self._build_agent()
        response = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
        return ChatResponse(answer=str(response["messages"][-1].content_blocks))

    def _build_agent(self):
        from langchain.agents import create_agent

        agent = create_agent(
            model=self._chat_model,
            system_prompt="你是一个有用的助手，但是你的脾气很大，别人问你问题，你会很愤怒的回答他",
        )
        return agent