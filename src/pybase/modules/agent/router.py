from fastapi import APIRouter

from pybase.modules.agent.dependencies import AgentServiceDep
from pybase.modules.agent.schemas import ChatRequest
from pybase.modules.auth.dependencies import CurrentUserReadDep
from pybase.presentation.responses import success_response

router = APIRouter(prefix="/agent", tags=["agent"])

@router.post("/chat", tags=["agent"])
async def chat(request: ChatRequest, service: AgentServiceDep, current_user: CurrentUserReadDep):
    chat_response = await service.chat(request.message, current_user)
    return success_response(chat_response)