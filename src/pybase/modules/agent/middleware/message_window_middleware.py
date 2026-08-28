from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)


class MessageWindowMiddleware(AgentMiddleware):
    """Keep first message + last N messages, drop orphaned tool results."""

    def __init__(self, max_messages: int = 6) -> None:
        super().__init__()
        self.max_messages = max_messages

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        messages = list(request.messages)

        if len(messages) > self.max_messages:
            messages = [messages[0]] + messages[-self.max_messages + 1:]

        messages = self._clean(messages)
        request = request.override(messages=messages)
        return await handler(request)

    @staticmethod
    def _clean(messages: list) -> list:
        valid_ids = {
            call.get("id")
            for msg in messages
            if isinstance(msg, AIMessage)
            for call in msg.tool_calls
        }

        cleaned = [msg for msg in messages if not (
            isinstance(msg, ToolMessage) and msg.tool_call_id not in valid_ids
        )]

        while cleaned and not isinstance(cleaned[0], HumanMessage):
            cleaned = cleaned[1:]

        return cleaned