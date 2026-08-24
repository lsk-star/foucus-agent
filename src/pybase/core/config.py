from functools import lru_cache
from typing import Literal

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve configuration from the repository root instead of the process cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class AppSettings(BaseModel):
    name: str = "PyBase"
    environment: Literal["local", "development", "testing", "staging", "production"] = "local"
    debug: bool = False
    api_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: Literal["text", "json"] = "text"
    access_log: bool = True
    max_query_value_length: int = Field(default=200, ge=1, le=4096)


class TracingSettings(BaseModel):
    """分布式追踪配置，默认关闭以避免无意义地生成 trace_id。"""

    enabled: bool = False


class DatabaseSettings(BaseModel):
    enabled: bool = False
    url: str | None = None
    strict_startup: bool = True
    echo: bool = False
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)


class AuthSettings(BaseModel):
    enabled: bool = False


class SkillSettings(BaseModel):
    """技能模块配置。"""

    source: Literal["file", "oss"] = "file"
    dir: Path = Path("skills")


class LlmSettings(BaseModel):
    enabled: bool = False
    provider: str = "openai"               # openai / deepseek / zhipu
    api_key: str | None = None
    api_base: str | None = None            # 自定义 base_url（DeepSeek 等需要）
    model: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)


class Settings(BaseSettings):
    """根配置，由各能力模块各自拥有的配置组合而成。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="PYBASE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppSettings = AppSettings()
    logging: LoggingSettings = LoggingSettings()
    tracing: TracingSettings = TracingSettings()
    database: DatabaseSettings = DatabaseSettings()
    auth: AuthSettings = AuthSettings()
    skill: SkillSettings = SkillSettings()
    llm: LlmSettings = LlmSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
