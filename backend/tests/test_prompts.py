"""Unit tests for the time-filter prompt slot added in #24."""

from shared.prompts import build_generate_sql_prompt


def test_time_range_renders_explicit_iso_dates_in_prompt():
    prompt = build_generate_sql_prompt(
        "Wie viele Leads gibt es?", "-- schema --", [], None, date_from="2026-01-01", date_to="2026-12-31"
    )

    assert "# Time range" in prompt
    assert "2026-01-01" in prompt
    assert "2026-12-31" in prompt


def test_no_time_range_omits_the_section():
    prompt = build_generate_sql_prompt("Wie viele Leads gibt es?", "-- schema --", [], None)

    assert "# Time range" not in prompt


def test_open_upper_bound_renders_from_onward():
    # date_to omitted -- no upper bound, never "today" (see build_generate_sql_prompt).
    prompt = build_generate_sql_prompt("Wie viele Leads gibt es?", "-- schema --", [], None, date_from="2026-01-01")

    assert "# Time range" in prompt
    assert "2026-01-01" in prompt
    assert "onward" in prompt


def test_open_lower_bound_renders_up_to():
    # date_from omitted -- no lower bound (from the earliest record).
    prompt = build_generate_sql_prompt("Wie viele Leads gibt es?", "-- schema --", [], None, date_to="2026-12-31")

    assert "# Time range" in prompt
    assert "2026-12-31" in prompt
    assert "earlier" in prompt
