"""Phase 1 deterministic funnel -- UX Flow Steps 1/3/4 (greeting -> time -> ready), per
docs/mvp-request.md and #22/#25. Button clicks alone decide the thema + time range;
`query` at the `ready` step then runs the Big Goal 1/#24 engine and maps its outcome
back into German copy -- the first end-to-end demo path (funnel -> real data).

Per the D5 alignment (2026-07-07), cross-thema selection moved to MVP 2: the #22/#23
scope add-on step (offer a second thema before moving on) is gone. Picking a thema at
greeting goes straight to the time step.

Guard rail: an action that doesn't fit the session's current step, or an unknown
payload, re-sends the current step's prompt -- never a 500, never a corrupted session.
`ready` stays `ready` after every query outcome (success, empty, refusal, or give-up),
so a session can ask a second question without re-walking the funnel.
"""

from modules.chat.schemas import ChatRequest, ChatResponse, ChoiceItem, ResultPayload, SourceItem
from modules.chat.session_store import SessionState, get_or_create, sessions
from modules.query.engine import QueryOutcome, run_query
from modules.query.time_range import resolve_time_range
from modules.schema.domain_tables import DOMAIN_DOC_REF, DOMAIN_TABLES

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
        session.domain = request.payload
        return _enter_time(session)
    return _reprompt(session)


def _handle_time(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "select_time" and request.payload in TIME_RANGE_LABELS:
        session.time_range = request.payload
        return _enter_ready(session)
    return _reprompt(session)


def _handle_ready(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "query" and request.payload:
        return _answer_question(session, request.payload)
    return _reprompt(session)


# --- transitions: mutate the session, then emit the new step's prompt ------------------


def _greet(session: SessionState) -> ChatResponse:
    # (Re)starting the funnel drops any previously accumulated scope, so a restarted
    # session can never leak a stale domain/time into the new run.
    session.step = "greeting"
    session.domain = None
    session.time_range = None
    return _greeting_prompt(session)


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


# --- query execution + outcome mapping (#25) --------------------------------------------


def _answer_question(session: SessionState, question: str) -> ChatResponse:
    thema_label = DOMAIN_LABELS[session.domain]
    tables = DOMAIN_TABLES[session.domain]
    time_range = resolve_time_range(session.time_range)

    outcome = run_query(question, tables, time_range=time_range)
    return _map_outcome(session, outcome, thema_label)


def _map_outcome(session: SessionState, outcome: QueryOutcome, thema_label: str) -> ChatResponse:
    # Every branch here keeps session.step at "ready" (we never touch it) -- a second
    # question on the same session works without re-walking greeting/time.
    if outcome.status == "OUT_OF_SCOPE":
        return ChatResponse(
            session_id=session.session_id,
            bot_message=(
                "Dazu habe ich keine Daten -- ich kann nur Fragen zu Ihren CRM-Daten im "
                f"Bereich {thema_label} beantworten."
            ),
            choices=[],
            show_input=True,
        )

    if outcome.status == "GAVE_UP":
        return ChatResponse(
            session_id=session.session_id,
            bot_message="Ich konnte dazu keine gültige Abfrage erstellen. Bitte formulieren Sie die Frage anders.",
            choices=[],
            show_input=True,
        )

    # SUCCESS: a query that ran fine and found nothing is a distinct, honest outcome (#24)
    # from a query that couldn't be built at all -- never conflate the two in the copy.
    if not outcome.rows:
        return ChatResponse(
            session_id=session.session_id,
            bot_message=(
                f"Dazu habe ich im Bereich {thema_label} keine Daten gefunden. Möglicherweise "
                "gibt es dazu keine Einträge, oder die Frage passt nicht zu den vorhandenen Daten."
            ),
            choices=[],
            show_input=True,
        )

    doc_ref = DOMAIN_DOC_REF[session.domain]
    result = ResultPayload(
        rows=outcome.rows,
        columns=outcome.columns or [],
        sql=outcome.sql,
        sources=[SourceItem(table=table, doc_ref=doc_ref) for table in outcome.tables_used],
    )
    return ChatResponse(
        session_id=session.session_id,
        bot_message=f"Hier ist Ihr Ergebnis ({len(outcome.rows)} Zeilen). Geprüfter Bereich: {thema_label}.",
        choices=[],
        show_input=True,
        result=result,
    )


_STEP_HANDLERS = {
    "greeting": _handle_greeting,
    "time": _handle_time,
    "ready": _handle_ready,
}

_STEP_PROMPTS = {
    "greeting": _greeting_prompt,
    "time": _time_prompt,
    "ready": _ready_prompt,
}
