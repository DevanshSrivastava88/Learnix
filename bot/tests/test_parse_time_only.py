"""Unit tests for claude_svc.parse_time_only — zero prior coverage.

All tests freeze 'now' at 2026-01-15 10:00:00 IST (04:30:00 UTC).
IST = UTC+5:30.
"""
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import pytz
import pytest

with patch("supabase_svc.create_client"):
    import claude_svc

IST = pytz.timezone("Asia/Kolkata")
FROZEN_IST = IST.localize(datetime(2026, 1, 15, 10, 0, 0))
FROZEN_UTC = FROZEN_IST.astimezone(timezone.utc)


class _FrozenDatetime(datetime):
    """datetime subclass that returns a fixed value from now()."""
    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return FROZEN_IST.astimezone(tz)
        return FROZEN_IST


def _freeze():
    return patch("datetime.datetime", _FrozenDatetime)


# ── Regex fast path: plain clock times ("8am", "3:30pm") ─────────────────────

def test_plain_time_future_returns_utc():
    # 3pm > 10am frozen time → scheduled today
    with _freeze():
        result = claude_svc.parse_time_only("3pm")
    expected_ist = FROZEN_IST.replace(hour=15, minute=0, second=0, microsecond=0)
    assert result == expected_ist.astimezone(timezone.utc)


def test_plain_time_past_rolls_to_tomorrow():
    # 9am < 10am frozen time → rolls to next day
    with _freeze():
        result = claude_svc.parse_time_only("9am")
    expected_ist = FROZEN_IST.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    assert result == expected_ist.astimezone(timezone.utc)


def test_plain_time_with_minutes():
    # "3:30pm" → 15:30 IST today (future from 10:00)
    with _freeze():
        result = claude_svc.parse_time_only("3:30pm")
    expected_ist = FROZEN_IST.replace(hour=15, minute=30, second=0, microsecond=0)
    assert result == expected_ist.astimezone(timezone.utc)


def test_plain_time_midnight_noon_edge():
    # 12pm = noon (12:00), future from 10:00 → today
    with _freeze():
        result = claude_svc.parse_time_only("12pm")
    expected_ist = FROZEN_IST.replace(hour=12, minute=0, second=0, microsecond=0)
    assert result == expected_ist.astimezone(timezone.utc)


def test_plain_time_day_offset_overrides_roll():
    # "8am" is past (< 10am) but day_offset=1 forces +1 day instead of roll logic
    with _freeze():
        result = claude_svc.parse_time_only("8am", day_offset=1)
    expected_ist = FROZEN_IST.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
    assert result == expected_ist.astimezone(timezone.utc)


def test_plain_time_result_is_utc():
    with _freeze():
        result = claude_svc.parse_time_only("3pm")
    assert result is not None
    assert result.tzinfo == timezone.utc


# ── LLM fallback path ─────────────────────────────────────────────────────────

def test_llm_minutes_returns_future_utc():
    # LLM returns {"minutes": 30} → now(UTC) + 30min
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"minutes": 30}):
        result = claude_svc.parse_time_only("in 30 minutes")
    assert result == FROZEN_UTC + timedelta(minutes=30)


def test_llm_minutes_zero_returns_none():
    # LLM returns {"minutes": 0} — nothing scheduled
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"minutes": 0}):
        result = claude_svc.parse_time_only("garble")
    assert result is None


def test_llm_hhmm_future_time():
    # LLM returns {"hhmm": "15:00"} → 3pm IST, future → today
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"hhmm": "15:00"}):
        result = claude_svc.parse_time_only("three in the afternoon")
    expected_ist = FROZEN_IST.replace(hour=15, minute=0, second=0, microsecond=0)
    assert result == expected_ist.astimezone(timezone.utc)


def test_llm_hhmm_past_rolls_to_tomorrow():
    # LLM returns {"hhmm": "09:00"} → 9am IST, past → next day
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"hhmm": "09:00"}):
        result = claude_svc.parse_time_only("nine in the morning")
    expected_ist = FROZEN_IST.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    assert result == expected_ist.astimezone(timezone.utc)


def test_llm_hhmm_tomorrow_flag_adds_day():
    # LLM returns {"hhmm": "09:00", "tomorrow": True} — tomorrow flag forces +1 day
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"hhmm": "09:00", "tomorrow": True}):
        result = claude_svc.parse_time_only("tomorrow at nine")
    expected_ist = FROZEN_IST.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    assert result == expected_ist.astimezone(timezone.utc)


def test_llm_hhmm_with_day_offset():
    # day_offset=2 adds 2 days to the LLM-resolved time
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"hhmm": "10:00"}):
        result = claude_svc.parse_time_only("morning", day_offset=2)
    expected_ist = FROZEN_IST.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2)
    assert result == expected_ist.astimezone(timezone.utc)


def test_llm_invalid_hhmm_falls_through_to_none():
    # "bad" is not "H:M" — ValueError caught, falls to minutes=0 → None
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value={"hhmm": "bad", "minutes": 0}):
        result = claude_svc.parse_time_only("something unclear")
    assert result is None


def test_llm_non_dict_returns_none():
    # LLM returns a string → isinstance check fails → None
    with _freeze(), patch.object(claude_svc, "_ask_json", return_value="not a dict"):
        result = claude_svc.parse_time_only("at the dentist")
    assert result is None
