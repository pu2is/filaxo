"""Data models for the query engine (#24). Kept separate from engine.py so
`TimeRange` stays a plain, dependency-free shape callers construct directly."""

from dataclasses import dataclass


@dataclass
class TimeRange:
    date_from: str  # ISO date (YYYY-MM-DD), user-entered and validated -- never left to the LLM
    date_to: str
