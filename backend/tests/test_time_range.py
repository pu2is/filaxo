"""Unit tests for the direct date-entry parser (D6, #34)."""

from modules.query.time_range import parse_time_range


def test_valid_range_is_echoed_back():
    tr = parse_time_range("2025-10-01", "2025-12-31")
    assert tr.date_from == "2025-10-01"
    assert tr.date_to == "2025-12-31"


def test_single_day_range_is_valid():
    tr = parse_time_range("2025-10-01", "2025-10-01")
    assert tr.date_from == tr.date_to == "2025-10-01"


def test_missing_date_from_returns_none():
    assert parse_time_range(None, "2025-12-31") is None


def test_missing_date_to_returns_none():
    assert parse_time_range("2025-10-01", None) is None


def test_both_missing_returns_none():
    assert parse_time_range(None, None) is None


def test_unparseable_date_from_returns_none():
    assert parse_time_range("not-a-date", "2025-12-31") is None


def test_unparseable_date_to_returns_none():
    assert parse_time_range("2025-10-01", "not-a-date") is None


def test_wrong_format_is_rejected_even_if_almost_iso():
    assert parse_time_range("01-10-2025", "2025-12-31") is None


def test_date_from_after_date_to_returns_none():
    assert parse_time_range("2025-12-31", "2025-10-01") is None
