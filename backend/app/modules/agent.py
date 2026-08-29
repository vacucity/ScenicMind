"""经营分析 Agent 对话 API。"""

from fastapi import APIRouter

from ..agent_contracts import ChatRequest, ChatResponse
from ..agent_orchestrator import handle_message

router = APIRouter(prefix="/api/v1/agent", tags=["经营分析 Agent"])


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
def chat(request: ChatRequest) -> ChatResponse:
    return handle_message(request.message, request.spot, request.session_id)
