"""POST /api/chat -- validates the wire format, delegates the actual conversation
step to service.handle_chat (see #17).
"""

from fastapi import APIRouter

from modules.chat.schemas import ChatRequest, ChatResponse
from modules.chat.service import handle_chat

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    # Sync def, not async: handle_chat -> run_query calls asyncio.run() internally
    # (#13), which raises if invoked from inside an already-running event loop. A sync
    # endpoint runs on FastAPI's threadpool instead, where asyncio.run() can start its
    # own loop; it also means the 5-30s LLM call doesn't block the server's event loop.
    return handle_chat(request)
