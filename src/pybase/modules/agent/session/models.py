import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Identity, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pybase.infrastructure.database.base import Base
from sqlalchemy import UniqueConstraint


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = (
        {
            "comment": "会话"
        },
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    conversation_no: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="新会话"
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_message"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_no: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    duration_s: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="本次消息生成耗时，单位秒"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # 会话消息编号唯一索引
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "message_no",
            name="uk_conversation_message_no",
        ),
    )
