"""Deterministic time-preposition guard: 'at N' = clock, 'in N' = minutes.
The 8B/70B model flips these; the guard must override its guess. These are the
tests that were missing when the bug shipped."""
from unittest.mock import patch

import pytest

import claude_svc


# ── _time_from_preposition (pure) ───────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("feed cat at 10", (None, "10:00", "at")),
    ("call john at 10:30", (None, "10:30", "at")),
    ("gym at 8", (None, "08:00", "at")),
    ("at 10pm", (None, "22:00", "at")),
    ("meeting at 8 am", (None, "08:00", "at")),
    ("at 12pm", (None, "12:00", "at")),   # noon
    ("at 12am", (None, "00:00", "at")),   # midnight
    ("call john in 10", (10, None, "in")),
    ("drink water in 30 mins", (30, None, "in")),
    ("in 2 hours", (120, None, "in")),
    ("in an hour", (60, None, "in")),
    ("in half an hour", (30, None, "in")),
    ("feed the cat", (None, None, None)),       # no preposition
    ("water the plants in kitchen", (None, None, None)),  # 'in' but no number
])
def test_time_from_preposition(text, expected):
    assert claude_svc._time_from_preposition(text) == expected


# ── override inside understand_message ──────────────────────────────────────

def _llm(task_fields):
    return {"intent": "task", "task": {"type": "reminder", "title": "X",
            "time_minutes": None, "time_hhmm": None, "day_offset": None,
            "recurrence_days": 1, "clarify": "", **task_fields},
            "extra_tasks": [], "task_ref": ""}


def test_at_overrides_model_minutes():
    # model wrongly returned minutes for "at 10" → guard forces clock
    with patch("claude_svc._ask_json", return_value=_llm({"time_minutes": 10})):
        r = claude_svc.understand_message("feed cat at 10")
    t = r["task"]
    assert t["time_hhmm"] == "10:00" and t["time_minutes"] is None


def test_in_overrides_model_clock():
    # model wrongly returned clock for "in 10" → guard forces minutes
    with patch("claude_svc._ask_json", return_value=_llm({"time_hhmm": "10:00"})):
        r = claude_svc.understand_message("call john in 10")
    t = r["task"]
    assert t["time_minutes"] == 10 and t["time_hhmm"] is None and t["day_offset"] is None


def test_at_pm_overrides():
    with patch("claude_svc._ask_json", return_value=_llm({"time_minutes": 10})):
        r = claude_svc.understand_message("gym at 7pm")
    assert r["task"]["time_hhmm"] == "19:00" and r["task"]["time_minutes"] is None


def test_no_preposition_leaves_model_value():
    # "tomorrow at..." not present; model said hhmm and there's no in/at number → keep it
    with patch("claude_svc._ask_json", return_value=_llm({"time_hhmm": "20:00"})):
        r = claude_svc.understand_message("dinner tonight")
    assert r["task"]["time_hhmm"] == "20:00"


# ── parse_time_only (pending "want a time?" answer path) — no LLM for in/at ──

def test_parse_time_only_in_n_is_minutes():
    from datetime import datetime, timezone
    # must NOT call the LLM — guard handles it. If it does, fail loudly.
    with patch("claude_svc._ask_json", side_effect=AssertionError("should not hit LLM")):
        dt = claude_svc.parse_time_only("in 10")
    mins = (dt - datetime.now(timezone.utc)).total_seconds() / 60
    assert 9 <= mins <= 11  # ~10 minutes from now


def test_parse_time_only_walk_dog_in_10_is_minutes():
    from datetime import datetime, timezone
    with patch("claude_svc._ask_json", side_effect=AssertionError("should not hit LLM")):
        dt = claude_svc.parse_time_only("walk dog in 10")
    mins = (dt - datetime.now(timezone.utc)).total_seconds() / 60
    assert 9 <= mins <= 11


def test_parse_time_only_at_10_is_clock_not_minutes():
    from datetime import datetime, timezone
    with patch("claude_svc._ask_json", side_effect=AssertionError("should not hit LLM")):
        dt = claude_svc.parse_time_only("at 10")
    # 10:00 IST = 04:30 UTC; minute field is 30 (clock), not ~10 min from now
    assert dt.astimezone(timezone.utc).minute == 30
