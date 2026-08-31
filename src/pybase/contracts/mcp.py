from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol


class McpToolProvider(Protocol):
    """
    Agent 所需的 MCP 工具提供能力。

    这里不暴露 MCP Client、Session、Transport 等技术细节，
    只暴露 Agent 真正需要的工具集合。

    好处：
    1. Agent 不依赖第三方 MCP SDK。
    2. 测试时可以注入 FakeMcpToolProvider。
    3. 将来可以替换 MCP 实现。
    """

    @property
    def tools(self) -> Sequence[Any]:
        """
        返回可以传给 LangChain Agent 的工具对象。
        """
        ...