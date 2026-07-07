"""Unit tests for the #25 query -> engine -> German copy mapping.

`modules.chat.service.run_query` is monkeypatched -- the engine itself is already
covered by test_query_engine.py / scripts/eval_query.py; this file only covers how
chat/service.py reacts to each of the four QueryOutcome shapes.
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


def send(session_id: str | None, action: str, payload: str | None = None) -> ChatResponse:
    return handle_chat(ChatRequest(session_id=session_id, action=action, payload=payload))


def walk_to_ready(domain: str = "LEAD", time_key: str = "THIS_MONTH") -> str:
    sid = send(None, "start").session_id
    send(sid, "select_domain", domain)
    send(sid, "select_time", time_key)
    return sid


def test_success_with_rows_returns_result_payload_and_stays_ready(monkeypatch):
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
    assert "Verkauf & Leads" in response.bot_message
    assert response.result is not None
    assert response.result.rows == [{"n": 4}]
    assert response.result.chart_type == "table"
    assert response.result.sql == outcome.sql
    assert [s.table for s in response.result.sources] == ["cobra.CrmLead"]
    assert [s.doc_ref for s in response.result.sources] == ["docs/01-lead-sales-erDiagram.md"]
    assert sessions[sid].step == "ready"


def test_success_with_no_rows_returns_null_result_with_honest_message(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", sql="SELECT * FROM cobra.CrmLead WHERE 1=0", rows=[], tables_used=["cobra.CrmLead"])
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "Wie viele Leads aus 2099 gibt es?")

    assert response.result is None
    assert "keine Daten gefunden" in response.bot_message
    assert "Verkauf & Leads" in response.bot_message
    assert sessions[sid].step == "ready"


def test_out_of_scope_returns_refusal_with_null_result(monkeypatch):
    outcome = QueryOutcome(status="OUT_OF_SCOPE")
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "Wie wird das Wetter morgen?")

    assert response.result is None
    assert "keine Daten" in response.bot_message
    assert sessions[sid].step == "ready"


def test_gave_up_returns_exact_ticket_copy(monkeypatch):
    outcome = QueryOutcome(status="GAVE_UP", error="could not parse SQL")
    monkeypatch.setattr(service, "run_query", lambda *a, **k: outcome)

    sid = walk_to_ready()
    response = send(sid, "query", "irgendetwas Unklares")

    assert response.result is None
    assert response.bot_message == (
        "Ich konnte dazu keine gültige Abfrage erstellen. Bitte formulieren Sie die Frage anders."
    )
    assert sessions[sid].step == "ready"


def test_engine_receives_domain_tables_and_resolved_time_range(monkeypatch):
    captured = {}

    def fake_run_query(question, tables, **kwargs):
        captured["question"] = question
        captured["tables"] = tables
        captured["time_range"] = kwargs.get("time_range")
        return QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=tables)

    monkeypatch.setattr(service, "run_query", fake_run_query)

    sid = walk_to_ready(domain="CUSTOMER", time_key="THIS_YEAR")
    send(sid, "query", "Wie viele Kunden gibt es?")

    assert captured["question"] == "Wie viele Kunden gibt es?"
    assert captured["tables"] == ["cobra.BaAddress", "cobra.BaAddInfo"]
    assert captured["time_range"].key == "THIS_YEAR"


def test_second_query_on_same_session_works(monkeypatch):
    outcome = QueryOutcome(status="SUCCESS", rows=[{"n": 1}], tables_used=["cobra.CrmLead"])
    calls = []
    monkeypatch.setattr(service, "run_query", lambda *a, **k: (calls.append(1), outcome)[1])

    sid = walk_to_ready()
    first = send(sid, "query", "Wie viele Leads gibt es?")
    second = send(sid, "query", "Und wie viele davon haben einen Score?")

    assert len(calls) == 2
    assert first.result is not None
    assert second.result is not None
    assert sessions[sid].step == "ready"
