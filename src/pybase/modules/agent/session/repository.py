from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.common.pagination import PageResult

from .models import Conversation, ConversationMessage, ConversationStatus, MessageRole
from .schemas import ConversationCreate, ConversationQuery, ConversationRead, MessageRead


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(
        self,
        user_id: int,
        data: ConversationCreate,
    ) -> ConversationRead:
        entity = Conversation(
            conversation_no=str(uuid4()),
            user_id=user_id,
            title=data.title,
            status=ConversationStatus.ACTIVE,
        )
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return ConversationRead.model_validate(entity)

    async def get_owned_conversation(
        self,
        user_id: int,
        conversation_no: str,
    ) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.conversation_no == conversation_no,
            Conversation.user_id == user_id,
            Conversation.status != ConversationStatus.DELETED,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_conversation(
        self,
        entity: Conversation,
        title: str | None,
        status: ConversationStatus | None,
    ) -> ConversationRead:
        if title is not None:
            entity.title = title

        if status is not None:
            entity.status = status

        if entity.status == ConversationStatus.DELETED:
            entity.deleted_at = datetime.now()

        await self._session.flush()
        await self._session.refresh(entity)
        return ConversationRead.model_validate(entity)

    async def list_conversations(
        self,
        user_id: int,
        query: ConversationQuery,
    ) -> PageResult[ConversationRead]:
        conditions = [
            Conversation.user_id == user_id,
            Conversation.status != ConversationStatus.DELETED,
        ]

        if query.status:
            status_value = ConversationStatus(query.status)
            conditions.append(Conversation.status == status_value)

        if query.keyword:
            keyword = f"%{query.keyword.strip()}%"
            conditions.append(Conversation.title.like(keyword))

        total_stmt = (
            select(func.count())
            .select_from(Conversation)
            .where(*conditions)
        )
        total = int((await self._session.execute(total_stmt)).scalar_one())

        stmt = (
            select(Conversation)
            .where(*conditions)
            .order_by(
                Conversation.last_message_at.desc(),
                Conversation.id.desc(),
            )
            .offset(query.offset)
            .limit(query.page_size)
        )

        result = await self._session.execute(stmt)
        items = [
            ConversationRead.model_validate(item)
            for item in result.scalars().all()
        ]

        return PageResult(
            items=items,
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    async def soft_delete_conversation(self, entity: Conversation) -> None:
        entity.status = ConversationStatus.DELETED
        entity.deleted_at = datetime.now()
        await self._session.flush()

    async def list_messages(
        self,
        conversation_id: int,
    ) -> list[MessageRead]:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id
            )
            .order_by(ConversationMessage.message_no.asc())
        )
        result = await self._session.execute(stmt)
        return [
            MessageRead.model_validate(item)
            for item in result.scalars().all()
        ]

    async def append_message(
        self,
        conversation: Conversation,
        role: MessageRole,
        content: str,
        duration_s: int | None = None,
    ) -> MessageRead:
        max_no_stmt = select(
            func.coalesce(
                func.max(ConversationMessage.message_no),
                0,
            )
        ).where(
            ConversationMessage.conversation_id == conversation.id
        )
        max_no = int(
            (await self._session.execute(max_no_stmt)).scalar_one()
        )

        message = ConversationMessage(
            conversation_id=conversation.id,
            message_no=max_no + 1,
            role=role,
            content=content,
            duration_s=duration_s,
        )

        conversation.last_message_at = datetime.now()
        self._session.add(message)

        await self._session.flush()
        await self._session.refresh(message)

        return MessageRead.model_validate(message)

    async def append_messages_pair(
        self,
        conversation: Conversation,
        user_content: str,
        assistant_content: str,
        duration_s: int | None = None,
    ) -> None:
        max_no_stmt = select(
            func.coalesce(
                func.max(ConversationMessage.message_no),
                0,
            )
        ).where(
            ConversationMessage.conversation_id == conversation.id
        )
        max_no = int(
            (await self._session.execute(max_no_stmt)).scalar_one()
        )

        user_msg = ConversationMessage(
            conversation_id=conversation.id,
            message_no=max_no + 1,
            role=MessageRole.USER,
            content=user_content,
        )
        assistant_msg = ConversationMessage(
            conversation_id=conversation.id,
            message_no=max_no + 2,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            duration_s=duration_s,
        )

        conversation.last_message_at = datetime.now()
        self._session.add(user_msg)
        self._session.add(assistant_msg)

        await self._session.flush()