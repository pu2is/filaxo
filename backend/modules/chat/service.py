"""Phase 1 deterministic funnel -- UX Flow Steps 1-4 (greeting -> domain pick ->
scope add-on -> time range -> ready), per docs/mvp-request.md and #22. No LLM involved:
the session accumulates the full query scope (domains + time range) through button
clicks alone, before Big Goal 4 plugs in the query engine.

Guard rail: an action that doesn't fit the session's current step, or an unknown
payload, re-sends the current step's prompt -- never a 500, never a corrupted session.

`query` at the `ready` step stays the "noch nicht verfügbar" placeholder until
Big Goal 4 wires in the engine.
"""

from modules.chat.schemas import ChatRequest, ChatResponse, ChoiceItem
from modules.chat.session_store import SessionState, get_or_create, sessions

DOMAIN_LABELS = {
    "LEAD": "Verkauf & Leads",
    "CUSTOMER": "Kunden & Adressen",
}

TIME_RANGE_LABELS = {
    "TODAY": "Heute",
    "THIS_WEEK": "Diese Woche",
    "THIS_MONTH": "Dieser Monat",
    "THIS_YEAR": "Dieses Jahr",
    "ALL": "Alle",
}


def handle_chat(request: ChatRequest) -> ChatResponse:
    is_new_session = request.session_id is None or request.session_id not in sessions
    session = get_or_create(request.session_id)

    # A session that doesn't exist yet (or an explicit "start") always gets the greeting,
    # regardless of which action the client happened to send -- an unknown/expired
    # session_id restarts the funnel instead of crashing.
    if is_new_session or request.action == "start":
        return _greet(session)

    handler = _STEP_HANDLERS.get(session.step)
    if handler is None:
        # Unrecognized step value can only mean corrupted state -- reset, don't 500.
        return _greet(session)
    return handler(session, request)


# --- per-step handlers: decide the transition (or re-prompt) for the current step ------


def _handle_greeting(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "select_domain" and request.payload in DOMAIN_LABELS:
        return _store_domain_and_advance(session, request.payload)
    return _reprompt(session)


def _handle_scope(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "select_domain" and request.payload in DOMAIN_LABELS:
        _add_domain(session, request.payload)
        return _enter_time(session)
    if request.action == "proceed":
        return _enter_time(session)
    return _reprompt(session)


def _handle_time(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "select_time" and request.payload in TIME_RANGE_LABELS:
        session.time_range = request.payload
        return _enter_ready(session)
    return _reprompt(session)


def _handle_ready(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "query":
        return _not_implemented(session)  # Big Goal 4 wires the query engine here
    return _reprompt(session)


# --- transitions: mutate the session, then emit the new step's prompt ------------------


def _greet(session: SessionState) -> ChatResponse:
    # (Re)starting the funnel drops any previously accumulated scope, so a restarted
    # session can never leak stale domains/time into the new run.
    session.step = "greeting"
    session.selected_domains = []
    session.time_range = None
    return _greeting_prompt(session)


def _store_domain_and_advance(session: SessionState, domain: str) -> ChatResponse:
    _add_domain(session, domain)
    if _remaining_domains(session):
        session.step = "scope"
        return _scope_prompt(session)
    # Nothing left to offer as an add-on -- skip the scope step entirely (#22).
    return _enter_time(session)


def _enter_time(session: SessionState) -> ChatResponse:
    session.step = "time"
    return _time_prompt(session)


def _enter_ready(session: SessionState) -> ChatResponse:
    session.step = "ready"
    return _ready_prompt(session)


# --- prompt builders: pure renderers of a step, safe to re-send any number of times ----


def _reprompt(session: SessionState) -> ChatResponse:
    """Guard rail: repeat the current step's prompt without touching session state."""
    return _STEP_PROMPTS[session.step](session)


def _greeting_prompt(session: SessionState) -> ChatResponse:
    return ChatResponse(
        session_id=session.session_id,
        bot_message=(
            "Guten Tag! Ich bin Ihr CRM-Assistent für FilaksOne.\n"
            "Was möchten Sie heute analysieren?"
        ),
        choices=[
            ChoiceItem(id=domain, label=label, action="select_domain")
            for domain, label in DOMAIN_LABELS.items()
        ],
        show_input=True,
    )


def _scope_prompt(session: SessionState) -> ChatResponse:
    # The scope step is only ever entered right after a domain pick, so the list
    # is never empty here and the remaining offer is never exhausted.
    picked_label = DOMAIN_LABELS[session.selected_domains[-1]]
    remaining = _remaining_domains(session)
    offer_label = " oder ".join(DOMAIN_LABELS[domain] for domain in remaining)
    choices = [
        ChoiceItem(id=domain, label=f"{DOMAIN_LABELS[domain]} hinzufügen", action="select_domain")
        for domain in remaining
    ]
    choices.append(ChoiceItem(id="proceed", label="Weiter", action="proceed"))
    return ChatResponse(
        session_id=session.session_id,
        bot_message=(
            f"Sie haben {picked_label} gewählt.\n"
            f"Möchten Sie noch {offer_label}-Daten einbeziehen oder direkt fortfahren?"
        ),
        choices=choices,
        show_input=True,
    )


def _time_prompt(session: SessionState) -> ChatResponse:
    return ChatResponse(
        session_id=session.session_id,
        bot_message="Für welchen Zeitraum möchten Sie analysieren?",
        choices=[
            ChoiceItem(id=key, label=label, action="select_time")
            for key, label in TIME_RANGE_LABELS.items()
        ],
        show_input=True,
    )


def _ready_prompt(session: SessionState) -> ChatResponse:
    time_label = TIME_RANGE_LABELS[session.time_range]
    return ChatResponse(
        session_id=session.session_id,
        bot_message=f"Zeitraum: {time_label}. Stellen Sie jetzt Ihre Frage.",
        choices=[],
        show_input=True,
    )


def _not_implemented(session: SessionState) -> ChatResponse:
    return ChatResponse(
        session_id=session.session_id,
        bot_message="Dieser Schritt ist noch nicht verfügbar.",
        choices=[],
        show_input=True,
    )


# --- helpers ----------------------------------------------------------------------------


def _add_domain(session: SessionState, domain: str) -> None:
    # Idempotent: a hand-crafted duplicate pick advances the funnel without
    # duplicating the domain in the accumulated scope.
    if domain not in session.selected_domains:
        session.selected_domains.append(domain)


def _remaining_domains(session: SessionState) -> list[str]:
    return [domain for domain in DOMAIN_LABELS if domain not in session.selected_domains]


_STEP_HANDLERS = {
    "greeting": _handle_greeting,
    "scope": _handle_scope,
    "time": _handle_time,
    "ready": _handle_ready,
}

_STEP_PROMPTS = {
    "greeting": _greeting_prompt,
    "scope": _scope_prompt,
    "time": _time_prompt,
    "ready": _ready_prompt,
}
