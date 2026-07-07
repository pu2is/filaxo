"""Wire format for POST /api/chat (frozen in #16, extended additively in #22/#25).

Every action -- button click or typed question -- goes through this single request/response
shape. #22 adds server-driven UI: each ChoiceItem carries the `action` the client must send
back when it is clicked, so the frontend never hardcodes step logic.
"""

from typing import Literal

from pydantic import BaseModel

# Everything a client can put in ChatRequest.action -- and what a ChoiceItem tells the
# client to send back. "proceed" (the BG3 scope add-on's skip action) is gone as of #25 --
# D5 moved cross-thema selection to MVP 2, so there's no add-on step to skip anymore.
# "confirm_domain" is reserved for the mini-router (D4), nothing sends it yet.
ChatAction = Literal["start", "select_domain", "confirm_domain", "select_time", "query"]


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


class SourceItem(BaseModel):
    table: str
    doc_ref: str


class ResultPayload(BaseModel):
    """Present on ChatResponse.result iff the engine came back SUCCESS with rows (#25) --
    an empty or refused outcome is conveyed through bot_message alone, result stays None."""

    rows: list[dict]
    columns: list[dict]
    chart_type: Literal["table"] = "table"  # chart-type heuristics are Big Goal 5 scope
    sql: str | None = None
    sources: list[SourceItem]


class ChatResponse(BaseModel):
    session_id: str
    bot_message: str
    choices: list[ChoiceItem] = []
    suggestions: list[SuggestionItem] = []
    show_input: bool
    result: ResultPayload | None = None
