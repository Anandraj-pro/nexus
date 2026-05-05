"""Unit tests for the Jireh scheduling daemon helper."""

from __future__ import annotations

import pytest

from orchestrator import _build_schedule_times


# ─── _build_schedule_times ────────────────────────────────────────────────────

def test_returns_correct_number_of_slots():
    # 5:00 → 9:00 inclusive, every 30 min = 9 slots
    times = _build_schedule_times("05:00", 30, "09:15")
    assert len(times) == 9


def test_first_slot_is_scout_start():
    times = _build_schedule_times("05:00", 30, "09:15")
    assert times[0] == (5, 0)


def test_last_slot_is_before_deadline():
    times = _build_schedule_times("05:00", 30, "09:15")
    assert times[-1] == (9, 0)
    assert (9, 15) not in times


def test_deadline_excluded():
    # deadline is exactly on an interval boundary — still excluded
    times = _build_schedule_times("05:00", 30, "09:00")
    assert (9, 0) not in times
    assert times[-1] == (8, 30)


def test_all_expected_slots_present():
    times = _build_schedule_times("05:00", 30, "09:15")
    expected = [
        (5, 0), (5, 30), (6, 0), (6, 30),
        (7, 0), (7, 30), (8, 0), (8, 30), (9, 0),
    ]
    assert times == expected


def test_hourly_interval():
    times = _build_schedule_times("06:00", 60, "09:00")
    assert times == [(6, 0), (7, 0), (8, 0)]


def test_single_slot_when_interval_spans_window():
    times = _build_schedule_times("05:00", 60, "05:30")
    assert times == [(5, 0)]


def test_returns_empty_when_start_equals_deadline():
    times = _build_schedule_times("09:15", 30, "09:15")
    assert times == []


def test_returns_empty_when_start_after_deadline():
    times = _build_schedule_times("10:00", 30, "09:00")
    assert times == []


def test_non_zero_minute_start():
    times = _build_schedule_times("05:30", 30, "07:00")
    assert times == [(5, 30), (6, 0), (6, 30)]


def test_slots_are_tuples_of_ints():
    times = _build_schedule_times("05:00", 30, "06:00")
    for h, m in times:
        assert isinstance(h, int)
        assert isinstance(m, int)


def test_fifteen_minute_interval():
    times = _build_schedule_times("08:00", 15, "09:00")
    assert times == [(8, 0), (8, 15), (8, 30), (8, 45)]