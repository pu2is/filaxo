"""Stub POST /api/chat -- proves the wire format from schemas.py, not the behavior.

Ignores `action`/`payload` entirely and always returns the same canned greeting. Real
per-action branching (session store, Phase 1 button flow) lands in #17.
"""

from uuid import uuid4

from fastapi import APIRouter

from modules.chat.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid4())
    return ChatResponse(
        session_id=session_id,
        bot_message="Hallo! Womit kann ich dir heute helfen?",
        choices=[],
        suggestions=[],
        show_input=True,
        result=None,
    )
