"""Tests for _weekday_offset_from_text in tasks/handlers.py."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytz
from datetime import datetime
from unittest.mock import patch

with patch("supabase_svc.create_client"):
    from tasks.handlers import _weekday_offset_from_text

IST = pytz.timezone("Asia/Kolkata")
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _today_idx():
    return datetime.now(IST).weekday()


# ── No weekday ───────────────────────────────────────────────────────────────

def test_no_weekday_returns_none():
    assert _weekday_offset_from_text("call john tomorrow") is None


def test_empty_string_returns_none():
    assert _weekday_offset_from_text("") is None


def test_unrelated_text_returns_none():
    assert _weekday_offset_from_text("let's have coffee sometime") is None


# ── Same day → 7 (next occurrence, not today) ────────────────────────────────

def test_same_day_full_name_returns_7():
    today_name = _WEEKDAYS[_today_idx()]
    assert _weekday_offset_from_text(f"call on {today_name}") == 7


def test_same_day_abbreviated_returns_7():
    today_abbr = _WEEKDAYS[_today_idx()][:3]
    assert _weekday_offset_from_text(today_abbr) == 7


# ── Next day → 1 ──────────────────────────────────────────────────────────

def test_next_day_returns_1():
    next_name = _WEEKDAYS[(_today_idx() + 1) % 7]
    assert _weekday_offset_from_text(f"gym {next_name}") == 1


def test_next_day_abbreviated_returns_1():
    next_abbr = _WEEKDAYS[(_today_idx() + 1) % 7][:3]
    assert _weekday_offset_from_text(f"run {next_abbr}") == 1


# ── All offsets are in range [1, 7] ─────────────────────────────────────────

def test_all_weekday_full_names_return_valid_offset():
    for day_name in _WEEKDAYS:
        result = _weekday_offset_from_text(day_name)
        assert result is not None, f"{day_name!r} returned None"
        assert 1 <= result <= 7, f"{day_name!r} gave out-of-range offset {result}"


def test_all_weekday_abbreviations_return_valid_offset():
    abbrevs = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for abbr in abbrevs:
        result = _weekday_offset_from_text(abbr)
        assert result is not None, f"{abbr!r} returned None"
        assert 1 <= result <= 7, f"{abbr!r} gave out-of-range offset {result}"


# ── Specific named days (deterministic math checks) ──────────────────────────

def test_monday_offset_matches_arithmetic():
    today_idx = _today_idx()
    expected = (0 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("meeting monday") == expected


def test_friday_offset_matches_arithmetic():
    today_idx = _today_idx()
    expected = (4 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("deadline friday") == expected


def test_sunday_offset_matches_arithmetic():
    today_idx = _today_idx()
    expected = (6 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("family dinner sunday") == expected


# ── Text context around the weekday word ────────────────────────────────────

def test_weekday_embedded_in_long_sentence():
    next_day_name = _WEEKDAYS[(_today_idx() + 1) % 7]
    result = _weekday_offset_from_text(f"Can we meet next {next_day_name} at 3pm?")
    assert result == 1


def test_weekday_with_time_phrase():
    today_idx = _today_idx()
    expected = (2 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("standup wednesday 10am") == expected


# ── Long-form abbreviations ──────────────────────────────────────────────────

def test_tues_recognized_as_tuesday():
    today_idx = _today_idx()
    expected = (1 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("call tues") == expected


def test_thurs_recognized_as_thursday():
    today_idx = _today_idx()
    expected = (3 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("gym thurs") == expected


def test_satur_recognized_as_saturday():
    today_idx = _today_idx()
    expected = (5 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("brunch satur") == expected


# ── Case insensitivity ───────────────────────────────────────────────────────

def test_uppercase_weekday():
    today_idx = _today_idx()
    expected = (4 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("FRIDAY deadline") == expected


def test_mixed_case_weekday():
    today_idx = _today_idx()
    expected = (0 - today_idx) % 7 or 7
    assert _weekday_offset_from_text("Monday morning call") == expected
