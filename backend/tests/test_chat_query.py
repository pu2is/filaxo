"""Unit tests for the #25/#31 query -> engine -> German copy mapping, and the D7/#35
post-answer follow-up loop that every one of those outcomes now lands on.

`modules.chat.service.run_query` is monkeypatched -- the engine itself is already
covered by test_query_engine.py / scripts/eval_query.py; this file only covers how
chat/service.py reacts to each of the four QueryOutcome shapes, now scoped to a
scope-tree leaf rather than a flat thema (#31), and the followup/time_offer navigation
that follows (#35). Both new steps are only reachable after a query outcome, so their
guard rails live here too rather than in test_chat_funnel.py (which has no monkeypatched
engine to reach them with).
"""

import pytest

from modules.chat import service
from modules.chat.schemas import ChatRequest, ChatResponse
from modules.chat.service import handle_chat
from modules.chat.session_store import sessions
from modules.query.engine import QueryOutcome


@pytest.fixture(autouse=True)
def clean_sessions():
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


def walk_to_ready(
    thema: str = "LEAD",
    leaf_id: str = "LEAD.SCORING",
    date_from: str = "2025-10-01",
    date_to: str = "2025-12-31",
) -> str:
    sid = send(None, "start").session_id
    send(sid, "select_domain", thema)
    send(sid, "select_scope", leaf_id)
    send(sid, "set_time_range", date_from=date_from, date_to=date_to)
    return sid


def _assert_followup_choices(response: ChatResponse) -> None:
    assert [c.action for c in response.choices] == ["continue_topic", "change_topic"]


def test_success_with_rows_returns_result_payload_and_moves_to_followup(monkeypatch):
    outcome = QueryOutcome(
        status="SUCCESS",
        sql="SELECT COUNT(*) AS n FROM cobra.CrmLead",
        rows=[{"n": 4}],
        columns=[{"name": "n", "type": "int"}],
        tables_used=["cobra.CrmLead"],
    )
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "Wie viele Leads gibt es?")

    assert "Hier ist Ihr Ergebnis (1 Zeilen)" in response.bot_message
    assert "Bewertung & Scoring" in response.bot_message  # leaf label, not the thema label
    assert response.result is not None
    assert response.result.rows == [{"n": 4}]
    assert response.result.chart_type == "table"
    assert response.result.sql == outcome.sql
    assert [s.table for s in response.result.sources] == ["cobra.CrmLead"]
    assert [s.doc_ref for s in response.result.sources] == ["docs/01-lead-sales-erDiagram.md"]
    _assert_followup_choices(response)
    assert sessions[sid].step == "followup"


def test_success_with_no_rows_returns_null_result_with_honest_message(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", sql="SELECT * FROM cobra.CrmLead WHERE 1=0", rows=[], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "Wie viele Leads aus 2099 gibt es?")

    assert response.result is None
    assert "keine Daten gefunden" in response.bot_message
    assert "Bewertung & Scoring" in response.bot_message
    _assert_followup_choices(response)
    assert sessions[sid].step == "followup"


def test_out_of_scope_returns_refusal_with_null_result(monkeypatch):
    outcome = QueryOutcome(status="OUT_OF_SCOPE")
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "Wie wird das Wetter morgen?")

    assert response.result is None
    assert "keine Daten" in response.bot_message
    _assert_followup_choices(response)
    assert sessions[sid].step == "followup"


def test_gave_up_returns_exact_ticket_copy(monkeypatch):
    outcome = QueryOutcome(status="GAVE_UP", error="could not parse SQL")
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "irgendetwas Unklares")

    assert response.result is None
    assert response.bot_message == (
        "Ich konnte dazu keine gültige Abfrage erstellen. Bitte formulieren Sie die Frage anders."
    )
    _assert_followup_choices(response)
    assert sessions[sid].step == "followup"


def test_engine_receives_leaf_tables_few_shots_and_resolved_time_range(monkeypatch):
    captured = {}

    def fake_run_query(question, tables, **kwargs):
        captured["question"] = question
        captured["tables"] = tables
        captured["time_range"] = kwargs.get("time_range")
        captured["few_shots"] = kwargs.get("few_shots")
        return QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=tables)

    monkeypatch.setattr(service, "run_query", fake_run_query)

    sid = walk_to_ready(thema="CUSTOMER", leaf_id="CUSTOMER.CONTACT", date_from="2025-01-01", date_to="2025-12-31")
    send(sid, "query", "Wie viele Kunden gibt es?")

    assert captured["question"] == "Wie viele Kunden gibt es?"
    assert captured["tables"] == ["cobra.BaAddress", "cobra.BaAddInfo"]
    assert captured["time_range"].date_from == "2025-01-01"
    assert captured["time_range"].date_to == "2025-12-31"
    # #31: leaf-scoped few-shots (#30's loader) reach the engine, not an empty list.
    assert captured["few_shots"] != []
    assert all("-- Frage:" in shot for shot in captured["few_shots"])


def test_facet_skip_leaf_passes_no_time_range(monkeypatch):
    from modules.schema.scope_tree import TREES, ScopeLeaf, ScopeTree

    fake_leaf = ScopeLeaf(
        id="NOFACET.OVERVIEW", label="Testbereich", tables=["cobra.CrmLead"],
        join_snippet=None, date_facet=None,
    )
    monkeypatch.setitem(TREES, "NOFACET", ScopeTree(thema="NOFACET", label="Testthema", doc_ref="docs/test.md", leaves=[fake_leaf]))

    captured = {}

    def fake_run_query(question, tables, **kwargs):
        captured["time_range"] = kwargs.get("time_range")
        return QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=tables)

    monkeypatch.setattr(service, "run_query", fake_run_query)

    sid = send(None, "start").session_id
    send(sid, "select_domain", "NOFACET")
    send(sid, "select_scope", "NOFACET.OVERVIEW")
    assert sessions[sid].step == "ready"  # confirms the facet-skip actually happened

    send(sid, "query", "Wie viele Einträge gibt es?")

    assert captured["time_range"] is None


def test_second_query_on_same_session_works_via_the_followup_loop(monkeypatch):
    # A second question no longer works by sending "query" straight after the first
    # answer (#35, D7) -- the session lands on "followup" and needs continue_topic (+
    # keep_time_range, since LEAD.SCORING has a date facet) to get back to "ready".
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    calls = []
    monkeypatch.setattr(service, "run_query", lambda *a, **k: (calls.append(1), outcome)[1])

    sid = walk_to_ready()
    first = send(sid, "query", "Wie viele Leads gibt es?")
    assert sessions[sid].step == "followup"

    send(sid, "continue_topic")
    assert sessions[sid].step == "time_offer"

    send(sid, "keep_time_range")
    assert sessions[sid].step == "ready"
    assert sessions[sid].date_from == "2025-10-01"  # untouched, per "keep"
    assert sessions[sid].date_to == "2025-12-31"

    second = send(sid, "query", "Und wie viele davon haben einen Score?")

    assert len(calls) == 2
    assert first.result is not None
    assert second.result is not None
    assert sessions[sid].step == "followup"


def test_continue_topic_on_date_facet_leaf_offers_time_change(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    send(sid, "query", "Wie viele Leads gibt es?")

    response = send(sid, "continue_topic")

    assert sessions[sid].step == "time_offer"
    assert "Zeitraum ändern" in response.bot_message
    assert [c.action for c in response.choices] == ["change_time_range", "keep_time_range"]


def test_change_time_range_from_time_offer_returns_to_time_step(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    send(sid, "query", "Wie viele Leads gibt es?")
    send(sid, "continue_topic")

    response = send(sid, "change_time_range")

    assert sessions[sid].step == "time"
    assert response.awaiting_time_range is True

    # #34's time step still works after coming back through the D7 loop.
    ready = send(sid, "set_time_range", date_from="2026-01-01", date_to="2026-01-31")
    assert sessions[sid].step == "ready"
    assert sessions[sid].date_from == "2026-01-01"
    assert sessions[sid].date_to == "2026-01-31"


def test_continue_topic_on_no_date_facet_leaf_skips_straight_to_ready(monkeypatch):
    from modules.schema.scope_tree import TREES, ScopeLeaf, ScopeTree

    fake_leaf = ScopeLeaf(
        id="NOFACET.OVERVIEW", label="Testbereich", tables=["cobra.CrmLead"],
        join_snippet=None, date_facet=None,
    )
    monkeypatch.setitem(TREES, "NOFACET", ScopeTree(thema="NOFACET", label="Testthema", doc_ref="docs/test.md", leaves=[fake_leaf]))

    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = send(None, "start").session_id
    send(sid, "select_domain", "NOFACET")
    send(sid, "select_scope", "NOFACET.OVERVIEW")
    send(sid, "query", "Wie viele Einträge gibt es?")
    assert sessions[sid].step == "followup"

    response = send(sid, "continue_topic")

    assert sessions[sid].step == "ready"  # no time_offer -- nothing to offer
    assert "Stellen Sie jetzt Ihre Frage" in response.bot_message


def test_change_topic_from_followup_returns_switch_variant_greeting(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    send(sid, "query", "Wie viele Leads gibt es?")

    response = send(sid, "change_topic")

    state = sessions[sid]
    assert state.step == "greeting"
    assert state.scope_path == []
    assert state.date_from is None
    assert state.date_to is None
    assert "stattdessen" in response.bot_message  # lightweight variant, not "Guten Tag"
    assert "Guten Tag" not in response.bot_message
    assert {c.id for c in response.choices} == {"LEAD", "CUSTOMER", "NEWCAR", "FINANCE"}


def test_wrong_action_at_followup_reprompts_followup_untouched(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    send(sid, "query", "Wie viele Leads gibt es?")

    response = send(sid, "query", "noch eine Frage")

    assert sessions[sid].step == "followup"  # untouched
    _assert_followup_choices(response)


def test_wrong_action_at_time_offer_reprompts_time_offer_untouched(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    send(sid, "query", "Wie viele Leads gibt es?")
    send(sid, "continue_topic")

    response = send(sid, "change_topic")  # not a valid action for time_offer

    assert sessions[sid].step == "time_offer"  # untouched
    assert [c.action for c in response.choices] == ["change_time_range", "keep_time_range"]
