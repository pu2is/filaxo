"""Wire format for POST /api/chat (frozen in #16, extended additively in #22).

Every action -- button click or typed question -- goes through this single request/response
shape. #22 adds server-driven UI: each ChoiceItem carries the `action` the client must send
back when it is clicked, so the frontend never hardcodes step logic.
"""

from typing import Literal

from pydantic import BaseModel

# Everything a client can put in ChatRequest.action -- and what a ChoiceItem tells the
# client to send back. "proceed" is the generic "continue without adding" action (#22);
# "confirm_domain" is reserved for the mini-router (D4), nothing sends it yet.
ChatAction = Literal["start", "select_domain", "confirm_domain", "select_time", "proceed", "query"]


class ChoiceItem(BaseModel):
    id: str  # sent back as ChatRequest.payload when the choice is clicked
    label: str  # button text shown to the user (German)
    action: ChatAction  # sent back as ChatRequest.action when the choice is clicked


class SuggestionItem(BaseModel):
    id: str
    label: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    action: ChatAction
    payload: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    bot_message: str
    choices: list[ChoiceItem] = []
    suggestions: list[SuggestionItem] = []
    show_input: bool
    result: dict | None = None
