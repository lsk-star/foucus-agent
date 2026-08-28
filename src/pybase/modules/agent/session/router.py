from fastapi import APIRouter, Depends, HTTPException, status

from pybase.modules.auth.dependencies import CurrentUserReadDep
from pybase.presentation.responses import success_response

from .dependencies import SessionServiceDep
from .schemas import (
    ConversationCreate,
    ConversationQuery,
    ConversationUpdate,
)

router = APIRouter(
    prefix="/conversations",
    tags=["会话"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
        data: ConversationCreate,
        service: SessionServiceDep,
        current_user: CurrentUserReadDep,
):
    result = await service.create(current_user.id, data)
    return success_response(result)


@router.patch("/{conversation_no}")
async def update_conversation(
        conversation_no: str,
        data: ConversationUpdate,
        service: SessionServiceDep,
        current_user: CurrentUserReadDep,
):
    result = await service.update(current_user.id, conversation_no, data)
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return success_response(result)


@router.get("")
async def list_conversations(
        service: SessionServiceDep,
        current_user: CurrentUserReadDep,
        query: ConversationQuery = Depends(),
):
    result = await service.list(current_user.id, query)
    return success_response(result)


@router.delete("/{conversation_no}")
async def delete_conversation(
        conversation_no: str,
        service: SessionServiceDep,
        current_user: CurrentUserReadDep,
):
    deleted = await service.delete(current_user.id, conversation_no)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return success_response(message="会话已删除")


@router.get("/{conversation_no}/messages")
async def list_messages(
        conversation_no: str,
        service: SessionServiceDep,
        current_user: CurrentUserReadDep,
):
    result = await service.list_messages(current_user.id, conversation_no)
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return success_response(result)