"""Deterministic TOP-N ranking path (#15).

Smoke-testing found ranking questions ("welcher/top N...") are where the 7B most
often emits Postgres-style LIMIT. Mitigation: never let the LLM write the ranking
SQL at all -- it only extracts {sort_column, direction, n} via structured output,
and the SELECT TOP {n} ... ORDER BY is assembled deterministically from a column
whitelist, then still goes through the normal validator + executor (#9, #8).
"""

import re
from dataclasses import dataclass

from modules.query.executor import execute
from modules.query.validator import validate
from modules.schema.schema_cards import get_columns, get_mandatory_filter
from shared.llm import LLMProvider

# German ranking-intent cues: explicit "Top N", or a superlative ("welcher hat den
# hoechsten..." has no number and implies n=1). Optional [nrs]? covers adjective
# declension (hoechste/hoechsten/hoechster/hoechstes).
_RANKING_HINTS = re.compile(
    r"\btop\s*\d+\b"
    r"|\bhöchste[nrs]?\b|\bniedrigste[nrs]?\b"
    r"|\bbeste[nrs]?\b|\bschlechteste[nrs]?\b"
    r"|\bmeisten\b|\bwenigsten\b"
    r"|\bgrößte[nrs]?\b|\bkleinste[nrs]?\b",
    re.IGNORECASE,
)

DEFAULT_N = 1
MAX_N = 1000


def is_ranking_question(question: str) -> bool:
    """Cheap, deterministic keyword check -- no LLM call needed to route."""
    return bool(_RANKING_HINTS.search(question))


@dataclass
class RankingAttempt:
    ok: bool
    sql: str | None = None
    rows: list[dict] | None = None
    error: str | None = None


async def try_ranking_query(
    question: str,
    table: str,
    schema_context: str,
    provider: LLMProvider,
) -> RankingAttempt:
    """Extract {sort_column, direction, n} via the LLM, then build+run the TOP-N
    query deterministically. Never raises -- any failure (hallucinated column,
    a structured-output response that doesn't fit RankingParams, a DB error) comes
    back as ok=False so the caller can fall back to the general SQL-generation
    path instead of losing the whole run_query() call."""
    try:
        params = await provider.extract_ranking_params(question, schema_context)

        valid_columns = get_columns(table)
        if not params.sort_column or params.sort_column not in valid_columns:
            return RankingAttempt(ok=False, error=f"invalid or hallucinated sort_column: {params.sort_column!r}")

        direction = params.direction if params.direction in ("ASC", "DESC") else "DESC"
        n = min(params.n, MAX_N) if params.n and params.n > 0 else DEFAULT_N

        mandatory_filter = get_mandatory_filter(table)
        where_clause = f" WHERE {mandatory_filter}" if mandatory_filter else ""
        sql = (
            f"SELECT TOP {n} {', '.join(valid_columns)} FROM {table}"
            f"{where_clause} ORDER BY {params.sort_column} {direction}"
        )

        validated = validate(sql)
        if not validated.ok:
            return RankingAttempt(ok=False, error=validated.error)

        result = execute(validated.sql)
        return RankingAttempt(ok=True, sql=validated.sql, rows=result.rows)
    except Exception as e:
        return RankingAttempt(ok=False, error=str(e))
