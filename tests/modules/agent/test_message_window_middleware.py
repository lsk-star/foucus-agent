import pytest
from langchain_core.messages import HumanMessage
from langchain.agents.middleware.types import ModelRequest

from pybase.modules.agent.middleware.message_window_middleware import MessageWindowMiddleware


@pytest.mark.asyncio
async def test_message_window_keeps_latest_six_messages():
    middleware = MessageWindowMiddleware(6)
    messages = [HumanMessage(content=str(i)) for i in range(8)]
    request = ModelRequest(model=None, system_prompt="", messages=messages)
    seen = {}

    async def handler(req):
        seen["messages"] = req.messages
        return None

    await middleware.awrap_model_call(request, handler)
    assert [m.content for m in seen["messages"]] == ["2", "3", "4", "5", "6", "7"]
