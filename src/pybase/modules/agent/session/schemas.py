from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pybase.common.pagination import PageParams, PageResult


class ConversationCreate(BaseModel):
    title: str = Field(default="新会话", min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_no: str
    title: str
    status: str
    last_message_at: datetime | None = None



class ConversationQuery(PageParams):
    keyword: str | None = None
    status: str | None = None


class MessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)
    duration_ms: int | None = Field(default=None, ge=0)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    message_no: int
    role: str
    content: str
    created_at: datetime


ConversationPage = PageResult[ConversationRead]