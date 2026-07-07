"""Data models for the query engine (#24). Kept separate from engine.py so
`TimeRange` stays a plain, dependency-free shape callers construct directly."""

from dataclasses import dataclass


@dataclass
class TimeRange:
    key: str  # funnel choice, e.g. "THIS_YEAR" -- echoed through, not parsed here
    date_from: str  # ISO date (YYYY-MM-DD), computed in Python -- never left to the LLM
    date_to: str
