"""The vertical slice: run_query(question, tables) -> {sql, rows}.

Plain Python, no LangGraph, no HTTP, no session. Steps stay pure (schema -> generate ->
validate -> execute) so a later LangGraph wrapper (mvp-request Phase 2) can wrap this same
sequence with zero rewrite -- only the retry/branching gets replaced by graph edges.
"""

import asyncio
from dataclasses import dataclass
from typing import Literal

from modules.query.executor import execute
from modules.query.validator import validate
from modules.schema.schema_cards import get_schema_context
from shared.exceptions import DatabaseError
from shared.llm import LLMProvider, OllamaProvider

Status = Literal["SUCCESS", "OUT_OF_SCOPE", "GAVE_UP"]


@dataclass
class QueryOutcome:
    status: Status
    sql: str | None = None
    rows: list[dict] | None = None
    error: str | None = None


def run_query(
    question: str,
    tables: list[str],
    max_attempts: int = 3,
    provider: LLMProvider | None = None,
) -> QueryOutcome:
    if provider is None:
        provider = OllamaProvider()
    schema_context = get_schema_context(tables)

    # No domain<->table reverse mapping exists yet (out of scope here, see #10/#11), so
    # few-shots can't be looked up from `tables` alone -- generate_sql runs without them.
    few_shots: list[str] = []

    last_error: str | None = None
    for _ in range(max_attempts):
        generated = asyncio.run(provider.generate_sql(question, schema_context, few_shots, last_error))

        if generated.error == "OUT_OF_SCOPE":
            return QueryOutcome(status="OUT_OF_SCOPE")

        if not generated.sql:
            last_error = "LLM returned neither sql nor an OUT_OF_SCOPE error"
            continue

        validated = validate(generated.sql)
        if not validated.ok:
            last_error = validated.error
            continue

        try:
            result = execute(validated.sql)
        except DatabaseError as e:
            last_error = str(e)
            continue

        return QueryOutcome(status="SUCCESS", sql=validated.sql, rows=result.rows)

    return QueryOutcome(status="GAVE_UP", error=last_error)
