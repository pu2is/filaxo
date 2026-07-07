"""Unit tests for the #25 startup self-check (fail fast on a missing/unreachable table).

Uses a fake engine/connection instead of the real DB -- unlike scripts/eval_query.py,
`pytest` here must pass with no docker services running.
"""

import pytest

from main import check_domain_tables_reachable


class _FakeConnection:
    def __init__(self, missing_table: str | None):
        self._missing_table = missing_table
        self.executed: list[str] = []

    def execute(self, statement):
        sql = str(statement)
        self.executed.append(sql)
        if self._missing_table and self._missing_table in sql:
            raise Exception(f"Invalid object name '{self._missing_table}'")


class _FakeEngine:
    """Stands in for sqlalchemy.engine.Engine: `.connect()` returns a context manager."""

    def __init__(self, missing_table: str | None = None):
        self.connection = _FakeConnection(missing_table)

    def connect(self):
        return self

    def __enter__(self):
        return self.connection

    def __exit__(self, *exc_info):
        return False


def test_passes_when_every_table_is_reachable():
    engine = _FakeEngine()
    check_domain_tables_reachable(engine, {"LEAD": ["cobra.CrmLead"], "CUSTOMER": ["cobra.BaAddress"]})
    assert len(engine.connection.executed) == 2


def test_raises_on_a_missing_table():
    engine = _FakeEngine(missing_table="cobra.Bogus")
    with pytest.raises(Exception, match="Bogus"):
        check_domain_tables_reachable(engine, {"LEAD": ["cobra.CrmLead", "cobra.Bogus"]})


def test_dedupes_tables_shared_across_domains():
    engine = _FakeEngine()
    check_domain_tables_reachable(engine, {"A": ["cobra.X"], "B": ["cobra.X"]})
    assert len(engine.connection.executed) == 1
