"""Unit tests for the Phase 1 funnel state machine (#22).

Calls service.handle_chat directly (no HTTP): happy paths in both domain orders,
the skip-add-on path, and the guard cases (wrong action for the step, unknown
payload, unknown session) -- per the ticket's acceptance criteria.
"""

import pytest

from modules.chat.schemas import ChatRequest, ChatResponse
from modules.chat.service import handle_chat
from modules.chat.session_store import sessions


@pytest.fixture(autouse=True)
def clean_sessions():
    # The session store is a module-level dict -- isolate every test.
    sessions.clear()
    yield
    sessions.clear()


def send(session_id: str | None, action: str, payload: str | None = None) -> ChatResponse:
    return handle_chat(ChatRequest(session_id=session_id, action=action, payload=payload))


def start_session() -> ChatResponse:
    return send(None, "start")


def walk_to_time(first_domain: str = "LEAD") -> str:
    """Drive a fresh session up to the time step; returns its session_id."""
    sid = start_session().session_id
    send(sid, "select_domain", first_domain)
    send(sid, "proceed")
    return sid


def walk_to_ready(time_key: str = "THIS_MONTH") -> str:
    sid = walk_to_time()
    send(sid, "select_time", time_key)
    return sid


# --- happy paths ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "first, second", [("LEAD", "CUSTOMER"), ("CUSTOMER", "LEAD")]
)
def test_full_funnel_with_addon(first: str, second: str):
    greeting = start_session()
    sid = greeting.session_id
    assert "Was möchten Sie heute analysieren?" in greeting.bot_message
    assert [c.id for c in greeting.choices] == ["LEAD", "CUSTOMER"]

    scope = send(sid, "select_domain", first)
    assert sessions[sid].step == "scope"
    assert "einbeziehen oder direkt fortfahren" in scope.bot_message
    # Add-on offers exactly the not-yet-selected domain, plus the generic "Weiter".
    assert [(c.id, c.action) for c in scope.choices] == [
        (second, "select_domain"),
        ("proceed", "proceed"),
    ]

    time_prompt = send(sid, "select_domain", second)
    assert sessions[sid].step == "time"
    assert "Für welchen Zeitraum" in time_prompt.bot_message
    assert [c.id for c in time_prompt.choices] == [
        "TODAY", "THIS_WEEK", "THIS_MONTH", "THIS_YEAR", "ALL",
    ]
    assert all(c.action == "select_time" for c in time_prompt.choices)

    ready = send(sid, "select_time", "THIS_MONTH")
    assert "Stellen Sie jetzt Ihre Frage" in ready.bot_message
    assert ready.choices == []
    assert ready.show_input is True

    state = sessions[sid]
    assert state.step == "ready"
    assert state.selected_domains == [first, second]
    assert state.time_range == "THIS_MONTH"


def test_skip_addon_via_proceed():
    sid = start_session().session_id
    send(sid, "select_domain", "CUSTOMER")
    time_prompt = send(sid, "proceed")
    assert "Für welchen Zeitraum" in time_prompt.bot_message

    ready = send(sid, "select_time", "ALL")
    assert "Stellen Sie jetzt Ihre Frage" in ready.bot_message
    assert sessions[sid].selected_domains == ["CUSTOMER"]
    assert sessions[sid].time_range == "ALL"


def test_every_choice_carries_an_action():
    sid = start_session().session_id
    responses = [
        send(sid, "start"),
        send(sid, "select_domain", "LEAD"),
        send(sid, "select_domain", "CUSTOMER"),
    ]
    for response in responses:
        for choice in response.choices:
            assert choice.action in ("select_domain", "select_time", "proceed")


# --- guard rails ------------------------------------------------------------------------


def test_wrong_action_for_step_reprompts_greeting():
    sid = start_session().session_id
    response = send(sid, "select_time", "THIS_MONTH")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert sessions[sid].step == "greeting"
    assert sessions[sid].time_range is None


def test_unknown_domain_payload_reprompts_greeting():
    sid = start_session().session_id
    response = send(sid, "select_domain", "FOO")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert sessions[sid].selected_domains == []


def test_unknown_time_payload_reprompts_time_step():
    sid = walk_to_time()
    response = send(sid, "select_time", "FOO")
    assert "Für welchen Zeitraum" in response.bot_message
    assert sessions[sid].step == "time"
    assert sessions[sid].time_range is None


def test_proceed_at_greeting_reprompts():
    sid = start_session().session_id
    response = send(sid, "proceed")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert sessions[sid].step == "greeting"


def test_duplicate_domain_at_scope_advances_without_duplicating():
    sid = start_session().session_id
    send(sid, "select_domain", "LEAD")
    send(sid, "select_domain", "LEAD")  # hand-crafted duplicate, not offered by the UI
    assert sessions[sid].step == "time"
    assert sessions[sid].selected_domains == ["LEAD"]


def test_unknown_session_id_restarts_funnel():
    response = send("no-such-session", "select_time", "THIS_MONTH")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    # The caller-supplied id is honored as the new session's key (see session_store).
    assert response.session_id == "no-such-session"
    assert sessions["no-such-session"].step == "greeting"


def test_restart_mid_funnel_drops_accumulated_scope():
    sid = walk_to_ready()
    response = send(sid, "start")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    state = sessions[sid]
    assert state.step == "greeting"
    assert state.selected_domains == []
    assert state.time_range is None


def test_query_at_ready_keeps_placeholder():
    sid = walk_to_ready()
    response = send(sid, "query", "Wie viele Leads gibt es?")
    assert "noch nicht verfügbar" in response.bot_message
    # Session survives untouched -- Big Goal 4 will replace this branch.
    assert sessions[sid].step == "ready"
