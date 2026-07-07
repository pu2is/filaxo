"""LangGraph state shape for the run_query workflow (#33).

A straight TypedDict translation of the local variables engine.py's old for-loop used
to track -- the swap from loop to graph is a pure refactor (D3), so every field here
exists because the loop already needed it, nothing added for its own sake.
"""

from typing import TypedDict

from shared.llm import LLMProvider


class QueryState(TypedDict):
    # Inputs -- set once by run_query(), never mutated by any node.
    question: str
    tables: list[str]
    max_attempts: int
    provider: LLMProvider
    schema_context: str
    few_shots: list[str]
    date_from: str | None
    date_to: str | None

    # Ranking short-circuit (#15) -- decided once by the check_ranking node, consumed
    # by its own conditional edge right after.
    is_ranking_candidate: bool
    ranking_ok: bool

    # Mutated across retries: attempts increments once per generate_sql node visit;
    # sql is set to None to mean "this attempt failed", regardless of which step failed.
    attempts: int
    sql: str | None
    last_error: str | None

    # Final result -- mirrors modules.query.engine.QueryOutcome's own fields 1:1 so
    # run_query() builds the dataclass from this with zero translation.
    status: str | None
    rows: list[dict] | None
    columns: list[dict] | None
    error: str | None
