"""只放置真正需要替换或隔离的外部边界契约。"""
from .lifecycle import LifecycleComponent, ReadinessStatus
from .mcp import McpToolProvider

__all__ = [
    "LifecycleComponent",
    "ReadinessStatus",
    "McpToolProvider",
]