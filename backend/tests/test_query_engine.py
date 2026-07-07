"""Unit tests for the TimeRange + tables_used + empty-aware outcome additions (#24).

No live Ollama/DB needed: `execute` is monkeypatched and a FakeProvider stands in for
the LLM so these run everywhere `pytest` runs, unlike scripts/eval_query.py.
"""

from dataclasses import dataclass

import pytest

from modules.query import engine
from modules.query.engine import QueryOutcome, run_query
from modules.query.executor import QueryResult
from modules.query.schemas import TimeRange
from shared.llm import RankingParams, SqlGenResult

TABLES = ["cobra.CrmLead"]


@dataclass
class FakeProvider:
    """Records the date_from/date_to it was called with; returns a fixed SQL result."""

    sql: str | None = "SELECT TOP 10 Id FROM cobra.CrmLead"
    error: str | None = None
    seen_date_from: str | None = None
    seen_date_to: str | None = None

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        few_shots: list[str],
        last_error: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> SqlGenResult:
        self.seen_date_from = date_from
        self.seen_date_to = date_to
        return SqlGenResult(sql=self.sql, error=self.error)

    async def extract_ranking_params(self, question: str, schema_context: str) -> RankingParams:
        raise AssertionError("ranking path should not be reached by these non-ranking questions")


@pytest.fixture(autouse=True)
def stub_execute(monkeypatch):
    """Default: any SQL "runs" and returns one row. Tests override via monkeypatch again."""
    monkeypatch.setattr(engine, "execute", lambda sql: QueryResult(rows=[{"Id": 1}], columns=[]))
    yield


def test_time_range_is_forwarded_to_provider_as_iso_dates():
    provider = FakeProvider()
    time_range = TimeRange(key="THIS_YEAR", date_from="2026-01-01", date_to="2026-12-31")

    run_query("Wie viele Leads gibt es?", TABLES, provider=provider, time_range=time_range)

    assert provider.seen_date_from == "2026-01-01"
    assert provider.seen_date_to == "2026-12-31"


def test_time_range_none_is_backward_compatible():
    provider = FakeProvider()

    outcome = run_query("Wie viele Leads gibt es?", TABLES, provider=provider)

    assert provider.seen_date_from is None
    assert provider.seen_date_to is None
    assert outcome.status == "SUCCESS"


def test_empty_result_is_success_not_gave_up(monkeypatch):
    monkeypatch.setattr(engine, "execute", lambda sql: QueryResult(rows=[], columns=[]))
    provider = FakeProvider()

    outcome = run_query("Wie viele Leads gibt es?", TABLES, provider=provider)

    assert outcome.status == "SUCCESS"
    assert outcome.rows == []
    assert outcome.tables_used == TABLES


def test_gave_up_still_reports_tables_used():
    provider = FakeProvider(sql=None)  # never produces usable SQL -> exhausts retries

    outcome = run_query("Wie viele Leads gibt es?", TABLES, provider=provider, max_attempts=2)

    assert outcome.status == "GAVE_UP"
    assert outcome.tables_used == TABLES


def test_out_of_scope_reports_tables_used():
    provider = FakeProvider(sql=None, error="OUT_OF_SCOPE")

    outcome = run_query("Wie wird das Wetter morgen?", TABLES, provider=provider)

    assert outcome.status == "OUT_OF_SCOPE"
    assert outcome.tables_used == TABLES


def test_success_reports_tables_used():
    provider = FakeProvider()

    outcome = run_query("Wie viele Leads gibt es?", TABLES, provider=provider)

    assert outcome.status == "SUCCESS"
    assert outcome.tables_used == TABLES


def test_query_outcome_default_tables_used_is_empty_list():
    # Guards against a shared-mutable-default regression (dataclasses.field vs bare []).
    assert QueryOutcome(status="OUT_OF_SCOPE").tables_used == []
