"""Data models for the query engine (#24). Kept separate from engine.py so
`TimeRange` stays a plain, dependency-free shape callers construct directly."""

from dataclasses import dataclass


@dataclass
class TimeRange:
    # ISO date (YYYY-MM-DD), user-entered and validated -- never left to the LLM. Either
    # side may be None for an open-ended bound (no lower/upper restriction) -- the
    # constructor is never called with both None (see modules.chat.service._answer_question).
    date_from: str | None
    date_to: str | None
