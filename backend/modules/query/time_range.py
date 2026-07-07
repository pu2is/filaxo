"""Direct date-entry parsing (D6, #34). Replaces the old preset-key resolver: the user
types/picks von/bis themselves, so there is nothing to compute relative to `date.today()`
-- this module only validates and echoes back what was entered.
"""

from datetime import date

from modules.query.schemas import TimeRange


def parse_time_range(date_from: str | None, date_to: str | None) -> TimeRange | None:
    """Strict ISO (YYYY-MM-DD) parse of both fields. Returns None -- never raises -- if
    either field is missing, unparseable, or date_from > date_to; the caller re-prompts
    on None rather than letting a bad string reach SQL or the LLM prompt."""
    if not date_from or not date_to:
        return None

    try:
        parsed_from = date.fromisoformat(date_from)
        parsed_to = date.fromisoformat(date_to)
    except ValueError:
        return None

    if parsed_from > parsed_to:
        return None

    return TimeRange(date_from=date_from, date_to=date_to)
