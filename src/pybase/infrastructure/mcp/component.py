from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from pybase.contracts.lifecycle import (
    LifecycleComponent,
    ReadinessStatus,
)
from pybase.contracts.mcp import McpToolProvider
from pybase.core.config import McpEchartsSettings
from pybase.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class McpEchartsComponent(
    LifecycleComponent,
    McpToolProvider,
):
    """
    mcp-echarts 的基础设施适配器。

    负责：
    - 创建 MCP streamable HTTP 客户端
    - 获取远端工具
    - 缓存工具
    - 提供生命周期管理
    - 提供 readiness 状态

    不负责：
    - 生成 ECharts 配置
    - 查询数据库
    - 处理用户权限
    - 生成 Markdown
    """

    name = "mcp-echarts"

    def __init__(
            self,
            settings: McpEchartsSettings,
    ) -> None:
        self._settings = settings

        # 使用 Any 隔离具体 MCP SDK 类型，
        # 避免 contracts 或业务层依赖第三方 SDK。
        self._client: Any | None = None

        # 工具加载完成后转为不可变 tuple，
        # 避免业务层意外修改组件内部状态。
        self._tools: tuple[Any, ...] = ()

        self._startup_error: str | None = None

    async def start(self) -> None:
        """
        启动 MCP 客户端并发现远端工具。
        """

        if not self._settings.enabled:
            logger.info("mcp-echarts 未启用")
            return

        try:
            # 延迟导入可选依赖。
            # 未启用 MCP 时，不会因为缺少 SDK 导致应用导入失败。
            from langchain_mcp_adapters.client import (
                MultiServerMCPClient,
            )
        except ImportError as exc:
            raise ConfigurationError(
                "mcp-echarts 已启用，但未安装 MCP 依赖。"
                "请执行: uv sync --extra mcp"
            ) from exc

        try:
            logger.info(
                "正在连接 mcp-echarts: %s",
                self._settings.url,
            )

            client = MultiServerMCPClient(
                {
                    "echarts": {
                        # 必须使用 streamable_http，
                        # 不使用 stdio。
                        "transport": "streamable_http",
                        "url": self._settings.url,
                    }
                }
            )

            tools = await asyncio.wait_for(
                client.get_tools(),
                timeout=self._settings.connect_timeout_seconds,
            )

            normalized_tools = self._normalize_tools(tools)

            if not normalized_tools:
                raise RuntimeError(
                    "mcp-echarts 未发现任何可用工具"
                )

            self._client = client
            self._tools = tuple(normalized_tools)
            self._startup_error = None

            logger.info(
                "mcp-echarts 连接成功，工具数量=%d，工具=%s",
                len(self._tools),
                [tool.name for tool in self._tools],
            )

        except asyncio.TimeoutError as exc:
            self._startup_error = (
                f"连接 mcp-echarts 超时: {self._settings.url}"
            )

            await self.stop()

            logger.exception(
                "mcp-echarts 连接超时"
            )

            if self._settings.strict_startup:
                raise ConfigurationError(
                    self._startup_error
                ) from exc

        except Exception as exc:
            self._startup_error = str(exc)

            await self.stop()

            logger.exception(
                "mcp-echarts 启动失败: %s",
                self._settings.url,
            )

            if self._settings.strict_startup:
                raise ConfigurationError(
                    f"mcp-echarts 启动失败: {self._settings.url}"
                ) from exc

    async def stop(self) -> None:
        """
        停止 MCP 客户端。

        不同版本的 MCP adapter 可能提供：
        - aclose()
        - close()

        这里兼容两种关闭方式。
        """

        client = self._client

        self._client = None
        self._tools = ()

        if client is None:
            return

        try:
            close_method = getattr(client, "aclose", None)

            if close_method is None:
                close_method = getattr(client, "close", None)

            if close_method is None:
                return

            result = close_method()

            if asyncio.iscoroutine(result):
                await result

        except Exception:
            logger.exception(
                "关闭 mcp-echarts 客户端失败"
            )

    async def readiness(self) -> ReadinessStatus:
        """
        返回 MCP 服务的就绪状态。
        """

        if not self._settings.enabled:
            return ReadinessStatus(
                name=self.name,
                ready=True,
                detail="未启用",
            )

        if self._tools:
            return ReadinessStatus(
                name=self.name,
                ready=True,
                detail=f"已发现 {len(self._tools)} 个工具",
            )

        return ReadinessStatus(
            name=self.name,
            ready=False,
            detail=self._startup_error or "MCP 工具尚未加载",
        )

    @property
    def tools(self) -> Sequence[Any]:
        """
        返回 Agent 可以调用的工具。
        """

        return self._tools

    def _normalize_tools(
            self,
            tools: Sequence[Any],
    ) -> list[Any]:
        """
        对远端工具名称进行统一处理。

        例如：

        bar     -> echarts_bar
        line    -> echarts_line
        pie     -> echarts_pie
        scatter -> echarts_scatter
        """

        prefix = self._settings.tool_name_prefix
        normalized: list[Any] = []

        for tool in tools:
            original_name = getattr(tool, "name", None)

            if not original_name:
                logger.warning(
                    "忽略没有 name 属性的 MCP 工具: %r",
                    tool,
                )
                continue

            target_name = (
                original_name
                if original_name.startswith(prefix)
                else f"{prefix}{original_name}"
            )

            # LangChain MCP 工具通常允许修改 name。
            # 如果某个版本的工具对象不允许修改，
            # 则保留原名称并记录警告。
            try:
                tool.name = target_name
            except Exception:
                logger.warning(
                    "无法修改 MCP 工具名称，保留原名称: %s",
                    original_name,
                )

            normalized.append(tool)

        return normalized
