from pydantic import BaseModel, ConfigDict


class AgentSchema(BaseModel):
    """Agent 模块的通用数据模型基类。请按业务增加字段。"""

    model_config = ConfigDict(from_attributes=True)

    # 示例：name: str
    # 生成器不猜测业务字段，避免生成错误的数据契约。


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    answer: str
