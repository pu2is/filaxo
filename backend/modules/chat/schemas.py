"""Wire format for POST /api/chat, frozen ahead of any real Phase 1/2 logic (see #16).

Every action -- button click or typed question -- goes through this single request/response
shape, so the frontend can be built against it before the backend does anything beyond echo
a canned reply.
"""

from typing import Literal

from pydantic import BaseModel


class ChoiceItem(BaseModel):
    id: str
    label: str


class SuggestionItem(BaseModel):
    id: str
    label: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    action: Literal["start", "select_domain", "confirm_domain", "select_time", "query"]
    payload: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    bot_message: str
    choices: list[ChoiceItem] = []
    suggestions: list[SuggestionItem] = []
    show_input: bool
    result: dict | None = None
