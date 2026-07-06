"""POST /api/chat -- validates the wire format, delegates the actual conversation
step to service.handle_chat (see #17).
"""

from fastapi import APIRouter

from modules.chat.schemas import ChatRequest, ChatResponse
from modules.chat.service import handle_chat

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return handle_chat(request)
