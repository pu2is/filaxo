"""Direct date-entry parsing (D6, #34; open-ended bounds added later). Replaces the old
preset-key resolver: the user types/picks von/bis themselves, so there is nothing to
compute relative to `date.today()` -- this module only validates and echoes back what was
entered.
"""

from datetime import date

from modules.query.schemas import TimeRange


def parse_time_range(date_from: str | None, date_to: str | None) -> TimeRange | None:
    """Strict ISO (YYYY-MM-DD) parse of whichever fields are present. Either side may be
    omitted -- an omitted date_from means "from the earliest record", an omitted date_to
    means "with no upper bound" (never "up to today": this dataset's dates don't track
    wall-clock today, see CLAUDE.md). Returns None -- never raises -- only when a
    *provided* field is unparseable, or when both are given with date_from > date_to; the
    caller re-prompts on None rather than letting a bad string reach SQL or the LLM prompt.
    """
    parsed_from = None
    parsed_to = None

    if date_from:
        try:
            parsed_from = date.fromisoformat(date_from)
        except ValueError:
            return None

    if date_to:
        try:
            parsed_to = date.fromisoformat(date_to)
        except ValueError:
            return None

    if parsed_from and parsed_to and parsed_from > parsed_to:
        return None

    return TimeRange(date_from=date_from or None, date_to=date_to or None)
