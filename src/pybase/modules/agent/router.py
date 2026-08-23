from fastapi import APIRouter

from pybase.modules.agent.dependencies import AgentServiceDep
from pybase.modules.agent.schemas import ChatRequest
from pybase.presentation.responses import success_response

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", tags=["agent"])
async def chat(request: ChatRequest, service: AgentServiceDep):
    chat_response = await service.chat(request.message)
    return success_response(chat_response)