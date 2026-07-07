"""Wire format for POST /api/chat (frozen in #16, extended additively in #22/#25/#31).

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
# #31 (D5 tree drilling): "select_scope" payload is the FULL dotted node path (e.g.
# "LEAD.SCORING", matching a ChoiceItem.id from the scope step) -- not just the clicked
# node's own key -- so the server can validate it against the *current* level's children
# without guessing what came before. "truncate_scope" payload is just the single segment
# key to cut back to (e.g. "SCORING"), matching a scope_breadcrumb entry's `key`. Both
# forms were frozen in mvp-request.md's API contract before this ticket implemented them.
ChatAction = Literal["start", "select_domain", "select_scope", "truncate_scope", "confirm_domain", "select_time", "query"]


class ChoiceItem(BaseModel):
    id: str  # sent back as ChatRequest.payload when the choice is clicked
    label: str  # button text shown to the user (German)
    action: ChatAction  # sent back as ChatRequest.action when the choice is clicked


class SuggestionItem(BaseModel):
    id: str
    label: str


class BreadcrumbItem(BaseModel):
    key: str  # single path segment (e.g. "SCORING") -- this is truncate_scope's payload
    label: str  # German label for that segment


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
    # Server-truth breadcrumb of the scope-tree path walked so far (#31) -- e.g.
    # [{"key": "LEAD", "label": "Verkauf & Leads"}, {"key": "SCORING", "label": "Bewertung & Scoring"}].
    # Empty at "greeting" (nothing picked yet). The frontend renders this directly rather
    # than reconstructing it client-side, and sends a crumb's `key` back as truncate_scope's payload.
    scope_breadcrumb: list[BreadcrumbItem] = []
