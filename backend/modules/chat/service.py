"""Phase 1 deterministic funnel -- D5 tree-drill (greeting -> scope* -> time? -> ready),
per docs/mvp-request.md and #22/#25/#31/#34/#35. Button clicks alone decide the scope path
(thema then leaf) + time range; `query` at the `ready` step runs the Big Goal 1/#24 engine
with that leaf's tables + leaf-scoped few-shots (#30) and maps the outcome back into German
copy. Every outcome (D7, #35) then lands on `followup`, offering "continue this topic" or
"switch topic" on the very same response -- continuing re-offers the Zeitraum (`time_offer`)
only if the leaf has a date facet, otherwise it goes straight back to `ready`.

Per D5 (2026-07-07 alignment): after picking a thema the user MUST walk down to a leaf --
there's no mid-tree stop, and "Überblick" is itself a selectable leaf for whole-thema
questions. Both LEAD.SCORING tree and CUSTOMER tree are exactly one level deep below their
thema today (#27), so in practice one `select_scope` click always reaches a leaf -- but the
walk is written generically against scope_tree.children()/is_leaf() so a future 3rd level
(sub-sub-thema) needs no funnel change, only new tree data.

The selected path is a breadcrumb (`ChatResponse.scope_breadcrumb`) the user can cut at any
level via `truncate_scope`: that resets the path to everything before the cut node, drops
time_range, and recomputes the current step from scratch -- cutting the thema itself returns
to greeting. `truncate_scope` is handled before the per-step dispatch since it must work from
any step (scope, time, or ready), not just the one it's semantically "closest" to.

Guard rail: an action that doesn't fit the session's current step, an unknown node key, or
an unknown payload re-sends the current step's prompt -- never a 500, never a corrupted
session. Every query outcome (success, empty, refusal, or give-up) moves to `followup`
rather than staying at `ready` -- the follow-up choices are how a session gets back to
`ready` for a second question, per D7.
"""

from modules.chat.schemas import (
    BreadcrumbItem,
    ChatRequest,
    ChatResponse,
    ChoiceItem,
    ResultPayload,
    SourceItem,
)
from modules.chat.session_store import SessionState, get_or_create, sessions
from modules.query.engine import QueryOutcome, run_query
from modules.query.schemas import TimeRange
from modules.query.time_range import parse_time_range
from modules.schema.leaf_question_bank import get_few_shots
from modules.schema.scope_tree import TREES, ScopeTreeError, children, is_leaf, resolve


def handle_chat(request: ChatRequest) -> ChatResponse:
    is_new_session = request.session_id is None or request.session_id not in sessions
    session = get_or_create(request.session_id)

    # A session that doesn't exist yet (or an explicit "start") always gets the greeting,
    # regardless of which action the client happened to send -- an unknown/expired
    # session_id restarts the funnel instead of crashing.
    if is_new_session or request.action == "start":
        return _greet(session)

    # truncate_scope is step-agnostic by design (works from "scope", "time", or "ready"),
    # so it's intercepted before the per-step dispatch rather than living in one handler.
    if request.action == "truncate_scope":
        return _safe(session, lambda: _handle_truncate(session, request))

    handler = _STEP_HANDLERS.get(session.step)
    if handler is None:
        # Unrecognized step value can only mean corrupted state -- reset, don't 500.
        return _greet(session)
    return _safe(session, lambda: handler(session, request))


def _safe(session: SessionState, fn) -> ChatResponse:
    """Belt-and-suspenders (#31): every scope_path mutation below is validated against
    scope_tree's actual children/leaves before use, so a ScopeTreeError here should be
    unreachable -- but if session state ever gets out of sync with the tree data (e.g. a
    tree shrinks across a deploy while a session is mid-walk), reset rather than 500."""
    try:
        return fn()
    except ScopeTreeError:
        return _greet(session)


# --- per-step handlers: decide the transition (or re-prompt) for the current step ------


def _handle_greeting(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "select_domain" and request.payload in TREES:
        session.scope_path = [request.payload]
        return _advance_after_scope_change(session)
    return _reprompt(session)


def _handle_scope(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "select_scope":
        valid_ids = {leaf.id for leaf in children(session.scope_path)}
        if request.payload in valid_ids:
            session.scope_path = request.payload.split(".")
            return _advance_after_scope_change(session)
    return _reprompt(session)


def _handle_time(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "set_time_range":
        time_range = parse_time_range(request.date_from, request.date_to)
        if time_range is not None:
            session.date_from = time_range.date_from
            session.date_to = time_range.date_to
            session.step = "ready"
            return _ready_prompt(session)
        # Malformed date, missing field, or date_from > date_to (#34): guard-rail
        # re-prompt with the invalid-input variant, never a 500.
        return _time_prompt(session, invalid=True)
    return _reprompt(session)


def _handle_ready(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "query" and request.payload:
        return _answer_question(session, request.payload)
    return _reprompt(session)


def _handle_followup(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "continue_topic":
        leaf = resolve(session.scope_path)
        if leaf["facets"].get("date_column"):
            session.step = "time_offer"
            return _time_offer_prompt(session)
        session.step = "ready"
        return _ready_prompt(session)
    if request.action == "change_topic":
        return _switch_topic(session)
    return _reprompt(session)


def _handle_time_offer(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.action == "change_time_range":
        session.step = "time"
        return _time_prompt(session)
    if request.action == "keep_time_range":
        # Dates are left untouched -- "keep" means exactly that (#35).
        session.step = "ready"
        return _ready_prompt(session)
    return _reprompt(session)


def _handle_truncate(session: SessionState, request: ChatRequest) -> ChatResponse:
    if request.payload is None or request.payload not in session.scope_path:
        return _reprompt(session)  # invalid node key -> re-prompt the current step, untouched

    cut_at = session.scope_path.index(request.payload)
    session.scope_path = session.scope_path[:cut_at]
    session.date_from = None
    session.date_to = None
    if not session.scope_path:
        return _greet(session)  # cutting the thema itself returns to greeting
    return _advance_after_scope_change(session)


# --- transitions: mutate the session, then emit the new step's prompt ------------------


def _greet(session: SessionState) -> ChatResponse:
    # (Re)starting the funnel drops any previously accumulated scope, so a restarted
    # session can never leak a stale scope/time into the new run.
    session.step = "greeting"
    session.scope_path = []
    session.date_from = None
    session.date_to = None
    return _greeting_prompt(session)


def _switch_topic(session: SessionState) -> ChatResponse:
    """change_topic from the followup step (D7, #35): same reset as _greet, but with the
    lightweight "switch topic" opening instead of the full "Guten Tag" greeting -- this
    isn't a session restart, it's a continuation of the same conversation."""
    session.step = "greeting"
    session.scope_path = []
    session.date_from = None
    session.date_to = None
    return _greeting_prompt(session, is_switch=True)


def _advance_after_scope_change(session: SessionState) -> ChatResponse:
    """Call right after session.scope_path changes (select_domain / select_scope /
    truncate_scope): keep walking while not yet at a leaf, then skip the time step
    entirely if the leaf reached has no date facet (#31)."""
    if not is_leaf(session.scope_path):
        session.step = "scope"
        return _scope_prompt(session)

    leaf = resolve(session.scope_path)
    if leaf["facets"].get("date_column"):
        session.step = "time"
        return _time_prompt(session)
    session.step = "ready"
    return _ready_prompt(session)


# --- prompt builders: pure renderers of a step, safe to re-send any number of times ----


def _reprompt(session: SessionState) -> ChatResponse:
    """Guard rail: repeat the current step's prompt without touching session state."""
    return _STEP_PROMPTS[session.step](session)


def _greeting_prompt(session: SessionState, is_switch: bool = False) -> ChatResponse:
    # is_switch (D7, #35): change_topic lands here via a lighter opening line -- the user
    # is mid-conversation, not starting fresh.
    message = (
        "Kein Problem — welches Thema möchten Sie stattdessen analysieren?"
        if is_switch
        else "Guten Tag! Ich bin Ihr CRM-Assistent für FilaksOne.\nWas möchten Sie heute analysieren?"
    )
    return ChatResponse(
        session_id=session.session_id,
        bot_message=message,
        choices=[
            ChoiceItem(id=key, label=tree.label, action="select_domain")
            for key, tree in TREES.items()
        ],
        show_input=True,
        scope_breadcrumb=[],
    )


def _scope_prompt(session: SessionState) -> ChatResponse:
    crumb = _breadcrumb(session.scope_path)
    picked_label = crumb[-1].label
    node_children = children(session.scope_path)
    return ChatResponse(
        session_id=session.session_id,
        bot_message=f"Sie haben {picked_label} gewählt.\nBitte grenzen Sie das Thema ein:",
        choices=[
            ChoiceItem(id=leaf.id, label=leaf.label, action="select_scope")
            for leaf in node_children
        ],
        show_input=True,
        scope_breadcrumb=crumb,
    )


def _time_prompt(session: SessionState, invalid: bool = False) -> ChatResponse:
    # No choices (D6, #34): the frontend renders a date-range picker off
    # awaiting_time_range instead of buttons -- picker UI itself is #37.
    message = (
        "Das eingegebene Datum war ungültig. Bitte wählen Sie Start- und Enddatum erneut."
        if invalid
        else "Für welchen Zeitraum möchten Sie analysieren?"
    )
    return ChatResponse(
        session_id=session.session_id,
        bot_message=message,
        choices=[],
        show_input=True,
        awaiting_time_range=True,
        scope_breadcrumb=_breadcrumb(session.scope_path),
    )


def _ready_prompt(session: SessionState) -> ChatResponse:
    if session.date_from and session.date_to:
        message = f"Zeitraum: {session.date_from} bis {session.date_to}. Stellen Sie jetzt Ihre Frage."
    else:
        # Facet-skip leaf (#31): no time step was ever offered, so there's no range to name.
        message = "Stellen Sie jetzt Ihre Frage."
    return ChatResponse(
        session_id=session.session_id,
        bot_message=message,
        choices=[],
        show_input=True,
        scope_breadcrumb=_breadcrumb(session.scope_path),
    )


# Follow-up choices (D7, #35) attached to every query outcome -- see _with_followup below.
FOLLOWUP_CHOICES = [
    ChoiceItem(id="continue", label="Weitere Frage zu diesem Thema", action="continue_topic"),
    ChoiceItem(id="switch", label="Anderes Thema wählen", action="change_topic"),
]

TIME_OFFER_CHOICES = [
    ChoiceItem(id="change", label="Ja, Zeitraum ändern", action="change_time_range"),
    ChoiceItem(id="keep", label="Nein, Zeitraum beibehalten", action="keep_time_range"),
]


def _followup_prompt(session: SessionState) -> ChatResponse:
    """Guard-rail reprompt for the "followup" step -- the answer that got us here isn't
    re-shown (it's not retained past that one response), only the follow-up question
    itself, same as every other step's reprompt."""
    return ChatResponse(
        session_id=session.session_id,
        bot_message="Möchten Sie zu diesem Thema weitere Fragen stellen, oder ein anderes Thema auswählen?",
        choices=FOLLOWUP_CHOICES,
        show_input=True,
        scope_breadcrumb=_breadcrumb(session.scope_path),
    )


def _time_offer_prompt(session: SessionState) -> ChatResponse:
    return ChatResponse(
        session_id=session.session_id,
        bot_message="Möchten Sie den Zeitraum ändern?",
        choices=TIME_OFFER_CHOICES,
        show_input=True,
        scope_breadcrumb=_breadcrumb(session.scope_path),
    )


# --- breadcrumb -----------------------------------------------------------------------


def _breadcrumb(scope_path: list[str]) -> list[BreadcrumbItem]:
    """Render scope_path as [{key, label}, ...]. Both trees are exactly thema -> leaf
    today (#27), so this only ever handles depth 1 (thema picked) and depth 2 (leaf
    reached); a future 3rd level would need this extended alongside scope_tree.resolve()."""
    if not scope_path:
        return []
    crumbs = [BreadcrumbItem(key=scope_path[0], label=TREES[scope_path[0]].label)]
    if len(scope_path) >= 2:
        crumbs.append(BreadcrumbItem(key=scope_path[-1], label=resolve(scope_path)["label"]))
    return crumbs


# --- query execution + outcome mapping (#25, extended for leaves in #31) ----------------


def _answer_question(session: SessionState, question: str) -> ChatResponse:
    leaf = resolve(session.scope_path)
    leaf_label = leaf["label"]
    tables = leaf["tables"]
    time_range = (
        TimeRange(date_from=session.date_from, date_to=session.date_to)
        if session.date_from and session.date_to
        else None
    )
    few_shots = get_few_shots(session.scope_path)

    outcome = run_query(question, tables, time_range=time_range, few_shots=few_shots)
    return _map_outcome(session, outcome, leaf_label)


def _with_followup(session: SessionState, bot_message: str, result: ResultPayload | None = None) -> ChatResponse:
    """Shared response builder for all four QueryOutcome branches (D7, #35): every one of
    them lands on "followup" and carries the same continue/switch choices alongside
    whatever bot_message/result is specific to that outcome -- one response, no extra
    round-trip."""
    session.step = "followup"
    return ChatResponse(
        session_id=session.session_id,
        bot_message=bot_message,
        choices=FOLLOWUP_CHOICES,
        show_input=True,
        result=result,
        scope_breadcrumb=_breadcrumb(session.scope_path),
    )


def _map_outcome(session: SessionState, outcome: QueryOutcome, leaf_label: str) -> ChatResponse:
    if outcome.status == "OUT_OF_SCOPE":
        return _with_followup(
            session,
            "Dazu habe ich keine Daten -- ich kann nur Fragen zu Ihren CRM-Daten im "
            f"Bereich {leaf_label} beantworten.",
        )

    if outcome.status == "GAVE_UP":
        return _with_followup(
            session, "Ich konnte dazu keine gültige Abfrage erstellen. Bitte formulieren Sie die Frage anders."
        )

    # SUCCESS: a query that ran fine and found nothing is a distinct, honest outcome (#24)
    # from a query that couldn't be built at all -- never conflate the two in the copy.
    if not outcome.rows:
        return _with_followup(
            session,
            f"Dazu habe ich im Bereich {leaf_label} keine Daten gefunden. Möglicherweise "
            "gibt es dazu keine Einträge, oder die Frage passt nicht zu den vorhandenen Daten.",
        )

    doc_ref = TREES[session.scope_path[0]].doc_ref
    result = ResultPayload(
        rows=outcome.rows,
        columns=outcome.columns or [],
        sql=outcome.sql,
        sources=[SourceItem(table=table, doc_ref=doc_ref) for table in outcome.tables_used],
    )
    return _with_followup(
        session,
        f"Hier ist Ihr Ergebnis ({len(outcome.rows)} Zeilen). Geprüfter Bereich: {leaf_label}.",
        result=result,
    )


_STEP_HANDLERS = {
    "greeting": _handle_greeting,
    "scope": _handle_scope,
    "time": _handle_time,
    "ready": _handle_ready,
    "followup": _handle_followup,
    "time_offer": _handle_time_offer,
}

_STEP_PROMPTS = {
    "greeting": _greeting_prompt,
    "scope": _scope_prompt,
    "time": _time_prompt,
    "ready": _ready_prompt,
    "followup": _followup_prompt,
    "time_offer": _time_offer_prompt,
}
