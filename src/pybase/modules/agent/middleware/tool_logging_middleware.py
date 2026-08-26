"""Debug logging around LangChain tool execution."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)


class ToolLoggingMiddleware(AgentMiddleware):
    """Record each asynchronous tool invocation at debug level."""

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call["name"]
        tool_call_id = request.tool_call["id"]
        started_at = perf_counter()

        logger.info(
            "开始调用工具: name=%s id=%s args=%r",
            tool_name,
            tool_call_id,
            request.tool_call["args"],
        )
        try:
            result = await handler(request)
        except Exception:
            logger.exception(
                "Tool call failed: name=%s id=%s duration_ms=%.2f",
                tool_name,
                tool_call_id,
                (perf_counter() - started_at) * 1_000,
                exc_info=True,

            )
            raise

        logger.info(
            "工具调用完成: name=%s id=%s result=%r duration_ms=%.2f",
            tool_name,
            tool_call_id,
            result,
            (perf_counter() - started_at) * 1_000,
        )
        return result
