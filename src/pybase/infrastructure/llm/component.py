from langchain_core.language_models import BaseChatModel

from pybase.contracts.lifecycle import ReadinessStatus
from pybase.core.config import LlmSettings
from pybase.core.exceptions import ConfigurationError

import logging
logger = logging.getLogger(__name__)

class LlmComponent:
    name = "llm"

    def __init__(self, settings: LlmSettings) -> None:
        if not settings.api_key:
            raise ConfigurationError("LLM 已启用，但未配置 PYBASE_LLM__API_KEY")
        self._settings = settings
        self._chat_model: BaseChatModel | None = None

    async def start(self) -> None:
        # 根据 provider 创建对应的 LangChain ChatModel
        logger.info(f"初始化 LLM 组件，provider: {self._settings.provider}")
        if self._settings.provider == "openai":
            from langchain_openai import ChatOpenAI
            self._chat_model = ChatOpenAI(
                api_key=self._settings.api_key,
                base_url=self._settings.api_base,
                model=self._settings.model,
                temperature=self._settings.temperature,
                max_tokens=self._settings.max_tokens,
            )
        # ...其他 provider

    async def stop(self) -> None:
        self._chat_model = None

    async def readiness(self) -> ReadinessStatus:
        if self._chat_model is None:
            return ReadinessStatus(self.name, False, "LLM 尚未初始化")
        return ReadinessStatus(self.name, True)

    @property
    def chat_model(self) -> BaseChatModel:
        if self._chat_model is None:
            raise RuntimeError("LLM 尚未启动")
        return self._chat_model