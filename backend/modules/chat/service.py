"""Phase 1 canned conversation steps -- UX Flow Step 1 (greeting) -> Step 2 (scope
confirmation), per docs/mvp-request.md. No LLM involved yet.

`select_time` and `query` (Phase 2) aren't wired up here -- see later goals -- so they,
along with any other unhandled action, fall through to a graceful placeholder rather
than crashing.
"""

from modules.chat.schemas import ChatRequest, ChatResponse, ChoiceItem
from modules.chat.session_store import SessionState, get_or_create, sessions

DOMAIN_LABELS = {
    "LEAD": "Verkauf & Leads",
    "CUSTOMER": "Kunden & Adressen",
}

_GREETING_CHOICES = [ChoiceItem(id=domain, label=label) for domain, label in DOMAIN_LABELS.items()]

_SCOPE_CHOICES = [
    ChoiceItem(id="add_customer", label="Kundendaten hinzufügen"),
    ChoiceItem(id="ask_question", label="Frage stellen"),
]


def handle_chat(request: ChatRequest) -> ChatResponse:
    is_new_session = request.session_id is None or request.session_id not in sessions
    session = get_or_create(request.session_id)

    # A session that doesn't exist yet (or an explicit "start") always gets the greeting,
    # regardless of which action the client happened to send -- this is what keeps an
    # unknown/expired session_id from crashing instead of just restarting the funnel.
    if is_new_session or request.action == "start":
        return _greet(session)
    if request.action == "select_domain":
        return _select_domain(session, request.payload)
    return _not_implemented(session)


def _greet(session: SessionState) -> ChatResponse:
    session.step = "greeting"
    return ChatResponse(
        session_id=session.session_id,
        bot_message=(
            "Guten Tag! Ich bin Ihr CRM-Assistent für FilaksOne.\n"
            "Was möchten Sie heute analysieren?"
        ),
        choices=_GREETING_CHOICES,
        suggestions=[],
        show_input=True,
        result=None,
    )


def _select_domain(session: SessionState, payload: str | None) -> ChatResponse:
    domain = payload or ""
    if domain and domain not in session.selected_domains:
        session.selected_domains.append(domain)
    session.step = "scope_confirmation"

    label = DOMAIN_LABELS.get(domain, domain)
    return ChatResponse(
        session_id=session.session_id,
        bot_message=(
            f"Sie haben {label} gewählt.\n"
            "Möchten Sie noch Kundendaten einbeziehen oder direkt eine Frage stellen?"
        ),
        choices=_SCOPE_CHOICES,
        suggestions=[],
        show_input=True,
        result=None,
    )


def _not_implemented(session: SessionState) -> ChatResponse:
    return ChatResponse(
        session_id=session.session_id,
        bot_message="Dieser Schritt ist noch nicht verfügbar.",
        choices=[],
        suggestions=[],
        show_input=True,
        result=None,
    )
