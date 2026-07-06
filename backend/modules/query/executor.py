"""Read-only SQL execution gateway. No validation, no LLM, no retry (see validator.py for that)."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shared.db import engine
from shared.exceptions import DatabaseError


@dataclass
class QueryResult:
    rows: list[dict]
    columns: list[dict]  # [{"name": ..., "type": ...}]


def execute(sql: str) -> QueryResult:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = [
                {"name": name, "type": type_code.__name__ if type_code else None}
                for name, type_code, *_ in result.cursor.description
            ]
            rows = [dict(row._mapping) for row in result]
    except SQLAlchemyError as e:
        orig = getattr(e, "orig", None)
        raise DatabaseError(str(orig) if orig is not None else str(e), original=e) from e

    return QueryResult(rows=rows, columns=columns)
