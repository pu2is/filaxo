"""Deterministic T-SQL guardrail: single SELECT, no DML/DDL, always TOP-bounded.

Runs before any LLM-generated SQL touches the DB. No DB connection, no LLM call.

sqlglot's tsql reader already accepts Postgres-style LIMIT/OFFSET and normalizes
it onto the same node TOP uses, so the common "7B outputs LIMIT" failure mode
self-repairs through the normal parse -> regenerate(dialect="tsql") path. The
postgres-read fallback below only matters for inputs tsql-read can't parse at all.
"""

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

_DIALECT = "tsql"
_DEFAULT_TOP = 1000

# AST-checking "must be exactly one SELECT" already rejects structural DML/DDL
# (DELETE/INSERT/DROP/UPDATE/ALTER/MERGE/EXECUTE all parse to their own non-Select
# expression types). This regex is the backstop: it also catches these keywords
# wherever they appear in the raw text (e.g. inside a subquery, or a construct the
# AST check doesn't model), matching the read-only DB login as a second layer.
_BLOCKED_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|EXEC|MERGE|ALTER|xp_\w*)\b",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    ok: bool
    sql: str | None
    error: str | None


def _parse_single_select(sql: str) -> tuple[exp.Expression | None, str | None]:
    try:
        statements = [s for s in sqlglot.parse(sql, read=_DIALECT) if s is not None]
    except ParseError:
        try:
            statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
        except ParseError as e:
            return None, f"could not parse SQL: {e}"

    if len(statements) != 1:
        return None, f"expected exactly one statement, got {len(statements)}"

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        return None, f"only SELECT statements are allowed, got {type(statement).__name__}"

    return statement, None


def validate(sql: str) -> ValidationResult:
    """Validate and repair a single T-SQL SELECT before it reaches the DB."""
    statement, error = _parse_single_select(sql)
    if error:
        return ValidationResult(ok=False, sql=None, error=error)

    if _BLOCKED_RE.search(sql):
        return ValidationResult(
            ok=False, sql=None, error="blocked keyword detected (DML/DDL or restricted procedure)"
        )

    if statement.args.get("limit") is None:
        statement = statement.limit(_DEFAULT_TOP)

    return ValidationResult(ok=True, sql=statement.sql(dialect=_DIALECT), error=None)
