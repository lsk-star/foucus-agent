from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from pybase.modules.agent.dependencies import AgentServiceDep
from pybase.modules.agent.emitter import format_sse
from pybase.modules.agent.schemas import ChatRequest
from pybase.modules.agent.session.router import router as session_router
from pybase.modules.auth.dependencies import CurrentUserReadDep
from pybase.presentation.responses import success_response

router = APIRouter(prefix="/agent", tags=["agent"])
router.include_router(session_router)


@router.post("/chat", tags=["agent"])
async def chat(request: ChatRequest, service: AgentServiceDep, current_user: CurrentUserReadDep):
    chat_response = await service.chat(request.message, current_user, request.conversation_id)
    return success_response(chat_response)


@router.post("/chat/stream", tags=["agent"])
async def chat_stream(request: ChatRequest, service: AgentServiceDep, current_user: CurrentUserReadDep):
    async def event_generator():
        async for event in service.chat_stream(request.message, current_user, request.conversation_id):
            yield format_sse(event)

    return StreamingResponse(event_generator(), media_type="text/event-stream")