"""Unit tests for the Phase 1 funnel state machine (#22, simplified in #25, tree-drill
added in #31).

Calls service.handle_chat directly (no HTTP): full walks to a leaf in both scope trees,
breadcrumb truncation (mid-path and at the root), the facet-skip leaf case, and the
guard cases (wrong action for the step, invalid node key, unknown payload/session) --
per the ticket's acceptance criteria. The #25/#31 query -> engine outcome mapping lives
in test_chat_query.py; this file only covers funnel navigation.
"""

import pytest

from modules.chat.schemas import ChatRequest, ChatResponse
from modules.chat.service import handle_chat
from modules.chat.session_store import sessions
from modules.schema.scope_tree import TREES, ScopeLeaf, ScopeTree


@pytest.fixture(autouse=True)
def clean_sessions():
    # The session store is a module-level dict -- isolate every test.
    sessions.clear()
    yield
    sessions.clear()


def send(
    session_id: str | None,
    action: str,
    payload: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ChatResponse:
    return handle_chat(
        ChatRequest(session_id=session_id, action=action, payload=payload, date_from=date_from, date_to=date_to)
    )


def start_session() -> ChatResponse:
    return send(None, "start")


def walk_to_leaf(thema: str, leaf_id: str) -> str:
    """Drive a fresh session to the given leaf (select_domain -> select_scope); returns
    its session_id. Every real leaf today is exactly one select_scope click below its
    thema (#27's trees are 2 levels deep), so this doesn't need to loop."""
    sid = start_session().session_id
    send(sid, "select_domain", thema)
    send(sid, "select_scope", leaf_id)
    return sid


def walk_to_ready(
    thema: str = "LEAD",
    leaf_id: str = "LEAD.SCORING",
    date_from: str = "2025-10-01",
    date_to: str = "2025-12-31",
) -> str:
    sid = walk_to_leaf(thema, leaf_id)
    send(sid, "set_time_range", date_from=date_from, date_to=date_to)
    return sid


ALL_LEAVES = [(tree.thema, leaf.id, leaf.label) for tree in TREES.values() for leaf in tree.leaves]


# --- happy path: full walk in every leaf of both trees ----------------------------------


def test_greeting_offers_every_thema():
    greeting = start_session()
    assert "Was möchten Sie heute analysieren?" in greeting.bot_message
    assert {c.id for c in greeting.choices} == set(TREES.keys())
    assert all(c.action == "select_domain" for c in greeting.choices)
    assert greeting.scope_breadcrumb == []


@pytest.mark.parametrize("thema,leaf_id,leaf_label", ALL_LEAVES)
def test_full_walk_to_ready_for_every_leaf(thema: str, leaf_id: str, leaf_label: str):
    sid = start_session().session_id

    scope_prompt = send(sid, "select_domain", thema)
    assert sessions[sid].step == "scope"
    assert sessions[sid].scope_path == [thema]
    assert {c.id for c in scope_prompt.choices} == {leaf.id for leaf in TREES[thema].leaves}
    assert all(c.action == "select_scope" for c in scope_prompt.choices)
    assert [b.key for b in scope_prompt.scope_breadcrumb] == [thema]
    assert [b.label for b in scope_prompt.scope_breadcrumb] == [TREES[thema].label]

    time_prompt = send(sid, "select_scope", leaf_id)
    # Every real leaf has a date facet today (#27) -- the facet-skip path is covered
    # separately below with a synthetic leaf.
    assert sessions[sid].step == "time"
    assert sessions[sid].scope_path == leaf_id.split(".")
    assert "Für welchen Zeitraum" in time_prompt.bot_message
    assert time_prompt.choices == []
    assert time_prompt.awaiting_time_range is True
    assert [b.key for b in time_prompt.scope_breadcrumb] == [thema, leaf_id.split(".")[-1]]
    assert [b.label for b in time_prompt.scope_breadcrumb] == [TREES[thema].label, leaf_label]

    ready = send(sid, "set_time_range", date_from="2025-10-01", date_to="2025-12-31")
    assert sessions[sid].step == "ready"
    assert sessions[sid].date_from == "2025-10-01"
    assert sessions[sid].date_to == "2025-12-31"
    assert "Zeitraum: 2025-10-01 bis 2025-12-31" in ready.bot_message
    assert "Stellen Sie jetzt Ihre Frage" in ready.bot_message
    assert ready.choices == []


def test_facet_skip_leaf_goes_straight_to_ready(monkeypatch):
    # No real leaf lacks a date facet today (#27) -- exercise the branch with a synthetic
    # one. monkeypatch.setitem mutates the TREES dict in place (not a reassignment), so
    # both scope_tree.py's own functions and chat.service's imported TREES name see it,
    # and pytest reverts it automatically after the test.
    fake_leaf = ScopeLeaf(
        id="NOFACET.OVERVIEW", label="Testbereich", tables=["cobra.CrmLead"],
        join_snippet=None, date_facet=None,
    )
    fake_tree = ScopeTree(thema="NOFACET", label="Testthema", doc_ref="docs/test.md", leaves=[fake_leaf])
    monkeypatch.setitem(TREES, "NOFACET", fake_tree)

    sid = start_session().session_id
    send(sid, "select_domain", "NOFACET")
    assert sessions[sid].step == "scope"

    ready = send(sid, "select_scope", "NOFACET.OVERVIEW")
    assert sessions[sid].step == "ready"
    assert sessions[sid].date_from is None
    assert sessions[sid].date_to is None
    assert "Stellen Sie jetzt Ihre Frage" in ready.bot_message
    assert [b.key for b in ready.scope_breadcrumb] == ["NOFACET", "OVERVIEW"]


# --- breadcrumb truncation ---------------------------------------------------------------


def test_truncate_at_leaf_returns_to_scope_step_with_shrunk_breadcrumb():
    sid = walk_to_ready("LEAD", "LEAD.SCORING")

    response = send(sid, "truncate_scope", "SCORING")

    state = sessions[sid]
    assert state.step == "scope"
    assert state.scope_path == ["LEAD"]
    assert state.date_from is None  # reset, per the ticket
    assert state.date_to is None
    assert [b.key for b in response.scope_breadcrumb] == ["LEAD"]
    assert {c.id for c in response.choices} == {leaf.id for leaf in TREES["LEAD"].leaves}


def test_truncate_at_thema_returns_to_greeting():
    sid = walk_to_ready("LEAD", "LEAD.SCORING")

    response = send(sid, "truncate_scope", "LEAD")

    state = sessions[sid]
    assert state.step == "greeting"
    assert state.scope_path == []
    assert state.date_from is None
    assert state.date_to is None
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert response.scope_breadcrumb == []


def test_truncate_works_from_the_time_step_too():
    sid = walk_to_leaf("LEAD", "LEAD.SCORING")  # stops at "time", never reaches "ready"
    assert sessions[sid].step == "time"

    response = send(sid, "truncate_scope", "SCORING")

    assert sessions[sid].step == "scope"
    assert sessions[sid].scope_path == ["LEAD"]
    assert [b.key for b in response.scope_breadcrumb] == ["LEAD"]


def test_truncate_invalid_node_key_reprompts_current_step_untouched():
    sid = walk_to_ready("LEAD", "LEAD.SCORING")

    response = send(sid, "truncate_scope", "NOT_IN_PATH")

    state = sessions[sid]
    assert state.step == "ready"  # untouched
    assert state.scope_path == ["LEAD", "SCORING"]
    assert state.date_from == "2025-10-01"
    assert state.date_to == "2025-12-31"
    assert "Stellen Sie jetzt Ihre Frage" in response.bot_message


def test_truncate_with_no_payload_reprompts_current_step():
    sid = walk_to_leaf("LEAD", "LEAD.SCORING")
    response = send(sid, "truncate_scope", None)
    assert sessions[sid].step == "time"
    assert "Für welchen Zeitraum" in response.bot_message


def test_truncate_at_greeting_is_a_noop_reprompt():
    sid = start_session().session_id
    response = send(sid, "truncate_scope", "LEAD")
    assert sessions[sid].step == "greeting"
    assert "Was möchten Sie heute analysieren?" in response.bot_message


# --- guard rails ---------------------------------------------------------------------------


def test_wrong_action_for_step_reprompts_greeting():
    sid = start_session().session_id
    response = send(sid, "set_time_range", date_from="2025-10-01", date_to="2025-12-31")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert sessions[sid].step == "greeting"
    assert sessions[sid].date_from is None


def test_unknown_domain_payload_reprompts_greeting():
    sid = start_session().session_id
    response = send(sid, "select_domain", "FOO")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert sessions[sid].scope_path == []


def test_invalid_scope_node_key_reprompts_scope_step_unchanged():
    sid = start_session().session_id
    send(sid, "select_domain", "LEAD")

    response = send(sid, "select_scope", "LEAD.BOGUS")

    assert sessions[sid].step == "scope"
    assert sessions[sid].scope_path == ["LEAD"]
    assert "Bitte grenzen Sie das Thema ein" in response.bot_message


def test_select_scope_at_greeting_reprompts_greeting():
    sid = start_session().session_id
    response = send(sid, "select_scope", "LEAD.SCORING")
    assert "Was möchten Sie heute analysieren?" in response.bot_message
    assert sessions[sid].step == "greeting"


@pytest.mark.parametrize(
    "date_from,date_to",
    [
        ("not-a-date", "2025-12-31"),  # malformed
        ("2025-10-01", None),  # missing field
        ("2025-12-31", "2025-10-01"),  # reversed
    ],
)
def test_invalid_time_range_reprompts_time_step_with_invalid_message(date_from, date_to):
    sid = walk_to_leaf("LEAD", "LEAD.SCORING")
    response = send(sid, "set_time_range", date_from=date_from, date_to=date_to)
    assert "ungültig" in response.bot_message
    assert response.awaiting_time_range is True
    assert sessions[sid].step == "time"
    assert sessions[sid].date_from is None
    assert sessions[sid].date_to is None


def test_select_domain_again_at_scope_step_reprompts_scope():
    sid = start_session().session_id
    send(sid, "select_domain", "LEAD")

    response = send(sid, "select_domain", "CUSTOMER")

    assert sessions[sid].step == "scope"
    assert sessions[sid].scope_path == ["LEAD"]
    assert "Bitte grenzen Sie das Thema ein" in response.bot_message


def test_unknown_session_id_restarts_funnel():
    response = send("no-such-session", "set_time_range", date_from="2025-10-01", date_to="2025-12-31")
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
    assert state.scope_path == []
    assert state.date_from is None
    assert state.date_to is None


def test_query_without_payload_at_ready_reprompts():
    sid = walk_to_ready()
    response = send(sid, "query", None)
    assert "Stellen Sie jetzt Ihre Frage" in response.bot_message
    assert sessions[sid].step == "ready"
