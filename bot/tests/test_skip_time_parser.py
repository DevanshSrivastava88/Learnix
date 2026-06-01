"""Tests for skip_time_parser.parse_time_expression.

All tests freeze 'now' at 2026-01-15 10:00:00 IST (04:30:00 UTC).
IST = UTC+5:30.
"""
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import pytest
import pytz

import skip_time_parser
from skip_time_parser import parse_time_expression

IST = pytz.timezone("Asia/Kolkata")

# Frozen reference point: 2026-01-15 10:00:00 IST
FROZEN_IST = IST.localize(datetime(2026, 1, 15, 10, 0, 0))
FROZEN_UTC = FROZEN_IST.astimezone(timezone.utc)


def _patch_now(fake_now=FROZEN_IST):
    """Patch datetime.now inside skip_time_parser to return fake_now."""
    mock_dt = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(
        wraps=datetime
    )
    mock_dt.now.return_value = fake_now
    return patch.object(skip_time_parser, 'datetime', mock_dt)


# ---------------------------------------------------------------------------
# "in X minutes / hours" patterns
# ---------------------------------------------------------------------------

def test_in_30_minutes():
    with _patch_now():
        result = parse_time_expression("in 30 minutes")
    expected = (FROZEN_IST + timedelta(minutes=30)).astimezone(timezone.utc)
    assert result == expected


def test_in_2_hours():
    with _patch_now():
        result = parse_time_expression("in 2 hours")
    expected = (FROZEN_IST + timedelta(hours=2)).astimezone(timezone.utc)
    assert result == expected


def test_in_fractional_hours():
    with _patch_now():
        result = parse_time_expression("in 1.5 hours")
    expected = (FROZEN_IST + timedelta(hours=1.5)).astimezone(timezone.utc)
    assert result == expected


def test_in_minutes_short_form():
    with _patch_now():
        result = parse_time_expression("in 10 mins")
    expected = (FROZEN_IST + timedelta(minutes=10)).astimezone(timezone.utc)
    assert result == expected


def test_in_hours_short_form():
    with _patch_now():
        result = parse_time_expression("in 3 hr")
    expected = (FROZEN_IST + timedelta(hours=3)).astimezone(timezone.utc)
    assert result == expected


# ---------------------------------------------------------------------------
# Absolute time — today (future) vs rolls to tomorrow (past)
# ---------------------------------------------------------------------------

def test_3pm_is_today_when_now_is_10am():
    # 3pm IST is in the future relative to 10am IST
    with _patch_now():
        result = parse_time_expression("3pm")
    expected_ist = FROZEN_IST.replace(hour=15, minute=0, second=0, microsecond=0)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


def test_9am_rolls_to_tomorrow_when_now_is_10am():
    # 9am IST is already past — should roll to next day
    with _patch_now():
        result = parse_time_expression("9am")
    expected_ist = FROZEN_IST.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


def test_time_with_minutes():
    # "3:30pm" → 15:30 IST today (future from 10am)
    with _patch_now():
        result = parse_time_expression("3:30pm")
    expected_ist = FROZEN_IST.replace(hour=15, minute=30, second=0, microsecond=0)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


def test_24h_format_future():
    # "15:00" — no am/pm, 24h style, future
    with _patch_now():
        result = parse_time_expression("15:00")
    expected_ist = FROZEN_IST.replace(hour=15, minute=0, second=0, microsecond=0)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


def test_midnight_noon_am_pm_edge():
    # 12am = midnight (0:00), 12pm = noon (12:00)
    with _patch_now():
        result_noon = parse_time_expression("12pm")
    expected_ist = FROZEN_IST.replace(hour=12, minute=0, second=0, microsecond=0)
    assert result_noon == expected_ist.astimezone(timezone.utc)

    with _patch_now():
        result_midnight = parse_time_expression("12am")
    # 12am = 0:00, which is past 10:00am → rolls to tomorrow
    expected_ist = FROZEN_IST.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    assert result_midnight == expected_ist.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# "tomorrow Xam/pm" pattern
# ---------------------------------------------------------------------------

def test_tomorrow_9am():
    with _patch_now():
        result = parse_time_expression("tomorrow 9am")
    tomorrow = FROZEN_IST + timedelta(days=1)
    expected_ist = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


def test_tomorrow_with_minutes():
    with _patch_now():
        result = parse_time_expression("tomorrow 10:30am")
    tomorrow = FROZEN_IST + timedelta(days=1)
    expected_ist = tomorrow.replace(hour=10, minute=30, second=0, microsecond=0)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


def test_tomorrow_evening():
    with _patch_now():
        result = parse_time_expression("tomorrow 8pm")
    tomorrow = FROZEN_IST + timedelta(days=1)
    expected_ist = tomorrow.replace(hour=20, minute=0, second=0, microsecond=0)
    expected = expected_ist.astimezone(timezone.utc)
    assert result == expected


# ---------------------------------------------------------------------------
# Result is always UTC
# ---------------------------------------------------------------------------

def test_result_is_utc():
    with _patch_now():
        result = parse_time_expression("in 60 minutes")
    assert result is not None
    assert result.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Unparseable inputs return None
# ---------------------------------------------------------------------------

def test_garbage_returns_none():
    with _patch_now():
        assert parse_time_expression("blah blah") is None


def test_empty_string_returns_none():
    with _patch_now():
        assert parse_time_expression("") is None


def test_bare_word_returns_none():
    with _patch_now():
        assert parse_time_expression("skip") is None
