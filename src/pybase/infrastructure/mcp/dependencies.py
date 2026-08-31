from fastapi import Request

from pybase.infrastructure.mcp.component import (
    McpEchartsComponent,
)


def get_mcp_echarts_component(
    request: Request,
) -> McpEchartsComponent | None:
    """
    从 ComponentRegistry 获取 MCP 组件。

    MCP 未启用时返回 None，
    而不是让 LookupError 转成 500。
    """

    try:
        return request.app.state.components.get(
            McpEchartsComponent
        )
    except LookupError:
        return None