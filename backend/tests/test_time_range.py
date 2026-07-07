"""Unit tests for the funnel time-key -> TimeRange resolver (#25)."""

from datetime import date

from modules.query.time_range import resolve_time_range


def test_all_returns_none():
    assert resolve_time_range("ALL") is None


def test_unknown_key_returns_none():
    assert resolve_time_range("NOT_A_KEY") is None


def test_today():
    tr = resolve_time_range("TODAY", today=date(2026, 7, 7))
    assert tr.key == "TODAY"
    assert tr.date_from == tr.date_to == "2026-07-07"


def test_this_week_is_monday_through_sunday():
    tr = resolve_time_range("THIS_WEEK", today=date(2026, 7, 7))  # a Tuesday
    assert tr.date_from == "2026-07-06"
    assert tr.date_to == "2026-07-12"


def test_this_month_is_full_calendar_bounds():
    tr = resolve_time_range("THIS_MONTH", today=date(2026, 7, 7))
    assert tr.date_from == "2026-07-01"
    assert tr.date_to == "2026-07-31"


def test_this_month_handles_leap_february():
    tr = resolve_time_range("THIS_MONTH", today=date(2028, 2, 15))
    assert tr.date_from == "2028-02-01"
    assert tr.date_to == "2028-02-29"


def test_this_year_is_full_calendar_bounds():
    tr = resolve_time_range("THIS_YEAR", today=date(2026, 7, 7))
    assert tr.date_from == "2026-01-01"
    assert tr.date_to == "2026-12-31"
