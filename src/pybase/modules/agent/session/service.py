from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pybase.common.pagination import PageResult
from pybase.core.exceptions import ConflictError

from .models import ConversationStatus, MessageRole
from .repository import SessionRepository
from .schemas import (
    ConversationCreate,
    ConversationQuery,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SessionRepository(session)

    async def create(
        self,
        user_id: int,
        data: ConversationCreate,
    ) -> ConversationRead:
        return await self._repo.create_conversation(user_id, data)

    async def update(
        self,
        user_id: int,
        conversation_no: str,
        data: ConversationUpdate,
    ) -> ConversationRead | None:
        entity = await self._repo.get_owned_conversation(
            user_id=user_id,
            conversation_no=conversation_no,
        )
        if entity is None:
            return None

        status_value = None
        if data.status is not None:
            try:
                status_value = ConversationStatus(data.status)
            except ValueError as exc:
                raise ConflictError("无效的会话状态") from exc

        return await self._repo.update_conversation(
            entity=entity,
            title=data.title,
            status=status_value,
        )

    async def list(
        self,
        user_id: int,
        query: ConversationQuery,
    ) -> PageResult[ConversationRead]:
        if query.status:
            try:
                ConversationStatus(query.status)
            except ValueError as exc:
                raise ConflictError("无效的会话状态") from exc

        return await self._repo.list_conversations(user_id, query)

    async def delete(
        self,
        user_id: int,
        conversation_no: str,
    ) -> bool:
        entity = await self._repo.get_owned_conversation(
            user_id=user_id,
            conversation_no=conversation_no,
        )
        if entity is None:
            return False

        await self._repo.soft_delete_conversation(entity)
        return True

    async def list_messages(
        self,
        user_id: int,
        conversation_no: str,
    ) -> list[MessageRead] | None:
        conversation = await self._repo.get_owned_conversation(
            user_id=user_id,
            conversation_no=conversation_no,
        )
        if conversation is None:
            return None

        return await self._repo.list_messages(conversation.id)

    # async def append_message(
    #     self,
    #     user_id: int,
    #     conversation_no: str,
    #     data: MessageCreate,
    # ) -> MessageRead | None:
    #     conversation = await self._repo.get_owned_conversation(
    #         user_id=user_id,
    #         conversation_no=conversation_no,
    #     )
    #     if conversation is None:
    #         return None
    #
    #     try:
    #         role = MessageRole(data.role)
    #     except ValueError as exc:
    #         raise ConflictError(
    #             "消息角色只能是 user 或 assistant"
    #         ) from exc
    #
    #     return await self._repo.append_message(
    #         conversation=conversation,
    #         role=role,
    #         content=data.content,
    #         duration_s=data.duration_ms,
    #     )