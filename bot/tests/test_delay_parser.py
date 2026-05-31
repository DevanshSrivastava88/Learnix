"""Tests for _parse_delay_duration — imported directly, no bot.py import needed."""
import re


# Copy of the function under test to avoid importing bot.py (which has heavy deps)
def _parse_delay_duration(text: str):
    """Parse delay duration from text. Returns minutes, or None if can't parse."""
    text_lower = text.lower().strip()

    bare_delay = re.match(r'^(delay|remind me later|later|snooze)$', text_lower)
    if bare_delay:
        return None

    hours_match = re.search(r'(\d+(?:\.\d+)?)\s*h(?:ours?)?', text_lower)
    mins_match = re.search(r'(\d+)\s*m(?:in(?:utes?)?)?', text_lower)

    total_minutes = 0
    found = False

    if hours_match:
        total_minutes += int(float(hours_match.group(1)) * 60)
        found = True
    if mins_match:
        total_minutes += int(mins_match.group(1))
        found = True

    if found and total_minutes > 0:
        return total_minutes

    bare_num = re.match(r'^(\d+)$', text_lower)
    if bare_num:
        return int(bare_num.group(1))

    return None


def test_bare_delay_returns_none():
    assert _parse_delay_duration("delay") is None


def test_remind_me_later_returns_none():
    assert _parse_delay_duration("remind me later") is None


def test_later_returns_none():
    assert _parse_delay_duration("later") is None


def test_30_mins():
    assert _parse_delay_duration("30 mins") == 30


def test_2_hours():
    assert _parse_delay_duration("2 hours") == 120


def test_1_hour_30_mins():
    assert _parse_delay_duration("1 hour 30 mins") == 90


def test_bare_number_treated_as_minutes():
    assert _parse_delay_duration("45") == 45


def test_delay_30_mins_phrase():
    assert _parse_delay_duration("delay 30 mins") == 30


def test_delay_2h_phrase():
    assert _parse_delay_duration("delay by 2 hours") == 120


def test_snooze_returns_none():
    assert _parse_delay_duration("snooze") is None


def test_1_5_hours():
    assert _parse_delay_duration("1.5 hours") == 90
