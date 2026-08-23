from typing import Protocol


class LlmClient(Protocol):
    """LLM 能力的稳定边界，业务层只依赖这个协议。"""

    @property
    def chat_model(self) -> object:
        """返回 LangChain BaseChatModel 实例，供 Agent 使用。"""
        ...