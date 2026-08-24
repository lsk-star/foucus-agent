import unittest

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from pybase.modules.agent.middleware.tool_logging_middleware import ToolLoggingMiddleware


class ToolLoggingMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.middleware = ToolLoggingMiddleware()
        self.request = ToolCallRequest(
            tool_call={
                "name": "get_skill_content",
                "args": {"skill_name": "example"},
                "id": "call-123",
            },
            tool=None,
            state={},
            runtime=None,
        )

    async def test_logs_before_and_after_successful_tool_call(self) -> None:
        async def handler(_: ToolCallRequest) -> ToolMessage:
            return ToolMessage(content="done", tool_call_id="call-123")

        with self.assertLogs(
            "pybase.modules.agent.middleware.tool_logging_middleware", level="DEBUG"
        ) as logs:
            result = await self.middleware.awrap_tool_call(self.request, handler)

        self.assertEqual(result.content, "done")
        self.assertIn("Tool call started: name=get_skill_content id=call-123", logs.output[0])
        self.assertIn("args={'skill_name': 'example'}", logs.output[0])
        self.assertIn("Tool call completed: name=get_skill_content id=call-123", logs.output[1])
        self.assertIn("result=ToolMessage", logs.output[1])

    async def test_logs_failure_and_reraises_tool_error(self) -> None:
        async def handler(_: ToolCallRequest) -> ToolMessage:
            raise RuntimeError("tool unavailable")

        with self.assertLogs(
            "pybase.modules.agent.middleware.tool_logging_middleware", level="DEBUG"
        ) as logs:
            with self.assertRaisesRegex(RuntimeError, "tool unavailable"):
                await self.middleware.awrap_tool_call(self.request, handler)

        self.assertIn("Tool call started: name=get_skill_content id=call-123", logs.output[0])
        self.assertIn("Tool call failed: name=get_skill_content id=call-123", logs.output[1])
