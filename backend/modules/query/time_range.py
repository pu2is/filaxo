"""Funnel time-key -> TimeRange resolution (#25). Pure and deterministic: dates are
computed here in Python, never left to the LLM (#24). Bounds are calendar-aligned
(e.g. THIS_YEAR = Jan 1 - Dec 31 of the current year), not "N days back from today",
so a fixed `today` always resolves to the same range regardless of when it's called.
"""

from datetime import date, timedelta

from modules.query.schemas import TimeRange

_ISO = "%Y-%m-%d"


def resolve_time_range(key: str, today: date | None = None) -> TimeRange | None:
    """ALL, and any key this funnel doesn't recognize, resolve to None (no time filter)."""
    if today is None:
        today = date.today()

    if key == "TODAY":
        date_from = date_to = today
    elif key == "THIS_WEEK":
        date_from = today - timedelta(days=today.weekday())
        date_to = date_from + timedelta(days=6)
    elif key == "THIS_MONTH":
        date_from = today.replace(day=1)
        date_to = _last_day_of_month(today)
    elif key == "THIS_YEAR":
        date_from = today.replace(month=1, day=1)
        date_to = today.replace(month=12, day=31)
    else:
        return None

    return TimeRange(key=key, date_from=date_from.strftime(_ISO), date_to=date_to.strftime(_ISO))


def _last_day_of_month(today: date) -> date:
    next_month = today.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)
