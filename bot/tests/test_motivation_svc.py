"""
Tests for motivation_svc.py — trigger detection and motivational message generation.

All Supabase and Gemini calls are mocked; no live credentials needed.
Async entry point (check_and_send_for_user) is tested via asyncio.run().
"""
import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

with patch("supabase_svc.create_client"):
    import motivation_svc


# ─── Helpers ────────────────────────────────────────────────────────────────

def _mock_hour(h: int):
    """Return a mock replacing motivation_svc.datetime so .now(IST).hour == h."""
    m = MagicMock()
    m.now.return_value.hour = h
    return m


def _two_table_client(task_skips_count: int, activity_count: int):
    """Client whose table() returns different mocks for task_skips vs activity_log."""
    skip_ex = MagicMock()
    skip_ex.count = task_skips_count

    done_ex = MagicMock()
    done_ex.count = activity_count

    skip_tbl = MagicMock()
    skip_tbl.select.return_value.eq.return_value.gte.return_value.execute.return_value = skip_ex

    done_tbl = MagicMock()
    done_tbl.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = done_ex

    c = MagicMock()
    c.table.side_effect = lambda name: skip_tbl if name == "task_skips" else done_tbl
    return c


# ─── _was_recently_motivated ────────────────────────────────────────────────

def test_was_recently_motivated_true_when_row_exists():
    c = MagicMock()
    ex = c.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value
    ex.data = [{"id": 1}]
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._was_recently_motivated(123) is True


def test_was_recently_motivated_false_when_no_rows():
    c = MagicMock()
    ex = c.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value
    ex.data = []
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._was_recently_motivated(123) is False


# ─── _is_streak_broken ──────────────────────────────────────────────────────

def test_is_streak_broken_true_when_streak_and_old_date():
    old = (date.today() - timedelta(days=3)).isoformat()
    with patch("settings_svc.get_settings", return_value={"streak": 5, "last_study_date": old}):
        assert motivation_svc._is_streak_broken(1) is True


def test_is_streak_broken_false_when_no_streak():
    with patch("settings_svc.get_settings", return_value={"streak": 0, "last_study_date": None}):
        assert motivation_svc._is_streak_broken(1) is False


def test_is_streak_broken_false_when_recent_date():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with patch("settings_svc.get_settings", return_value={"streak": 3, "last_study_date": yesterday}):
        assert motivation_svc._is_streak_broken(1) is False


def test_is_streak_broken_false_when_no_last_study_date():
    with patch("settings_svc.get_settings", return_value={"streak": 5, "last_study_date": None}):
        assert motivation_svc._is_streak_broken(1) is False


# ─── _count_skips_today ─────────────────────────────────────────────────────

def test_count_skips_today_returns_db_count():
    c = MagicMock()
    ex = c.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value
    ex.count = 4
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._count_skips_today(1) == 4


def test_count_skips_today_returns_zero_when_none_count():
    c = MagicMock()
    ex = c.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value
    ex.count = None
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._count_skips_today(1) == 0


# ─── _skip_rate_last_7_days ─────────────────────────────────────────────────

def test_skip_rate_returns_correct_ratio():
    c = _two_table_client(task_skips_count=3, activity_count=3)
    with patch("motivation_svc.get_client", return_value=c):
        rate = motivation_svc._skip_rate_last_7_days(1)
        assert abs(rate - 0.5) < 1e-9


def test_skip_rate_returns_zero_when_no_data():
    c = _two_table_client(task_skips_count=0, activity_count=0)
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._skip_rate_last_7_days(1) == 0.0


def test_skip_rate_all_skips_returns_one():
    c = _two_table_client(task_skips_count=5, activity_count=0)
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._skip_rate_last_7_days(1) == 1.0


# ─── _days_since_any_activity ───────────────────────────────────────────────

def test_days_since_any_activity_returns_999_when_no_data():
    c = MagicMock()
    ex = c.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value
    ex.data = []
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._days_since_any_activity(1) == 999


def test_days_since_any_activity_uses_activity_log_date():
    five_days_ago = (date.today() - timedelta(days=5)).isoformat()

    activity_tbl = MagicMock()
    activity_tbl.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"event_date": five_days_ago}
    ]
    skip_tbl = MagicMock()
    skip_tbl.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    c = MagicMock()
    c.table.side_effect = lambda name: activity_tbl if name == "activity_log" else skip_tbl
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._days_since_any_activity(1) == 5


# ─── evaluate_triggers ──────────────────────────────────────────────────────

def test_evaluate_daily_skip_burst_fires_at_evening_with_3plus_skips():
    with patch("motivation_svc.datetime", _mock_hour(18)), \
         patch("motivation_svc._count_skips_today", return_value=3):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger == "daily_skip_burst"
    assert fired is True


def test_evaluate_daily_skip_burst_does_not_fire_below_threshold():
    with patch("motivation_svc.datetime", _mock_hour(18)), \
         patch("motivation_svc._count_skips_today", return_value=2), \
         patch("motivation_svc._is_streak_broken", return_value=False), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.0), \
         patch("motivation_svc._days_since_any_activity", return_value=0):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger is None
    assert fired is False


def test_evaluate_streak_broken_fires_at_morning_hour():
    with patch("motivation_svc.datetime", _mock_hour(8)), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=True):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger == "streak_broken"
    assert fired is True


def test_evaluate_streak_broken_does_not_fire_outside_window():
    # Hour 11 is outside the 08-09 window for streak_broken
    with patch("motivation_svc.datetime", _mock_hour(11)), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=True), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.0), \
         patch("motivation_svc._days_since_any_activity", return_value=0):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger is None


def test_evaluate_low_weekly_rate_fires_at_morning():
    with patch("motivation_svc.datetime", _mock_hour(9)), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=False), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.6):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger == "low_weekly_rate"
    assert fired is True


def test_evaluate_no_activity_fires_at_daytime():
    with patch("motivation_svc.datetime", _mock_hour(14)), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=False), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.0), \
         patch("motivation_svc._days_since_any_activity", return_value=3):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger == "no_activity"
    assert fired is True


def test_evaluate_returns_none_when_no_window_matches():
    # Hour 23 falls outside all trigger windows
    with patch("motivation_svc.datetime", _mock_hour(23)), \
         patch("motivation_svc._count_skips_today", return_value=5), \
         patch("motivation_svc._is_streak_broken", return_value=True), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.9), \
         patch("motivation_svc._days_since_any_activity", return_value=7):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger is None
    assert fired is False


def test_evaluate_burst_takes_priority_over_streak_at_shared_hour():
    # Hour 8 is within both burst window (17-22 — no) actually not shared.
    # Let's use hour 8 where streak_broken (08-09) and low_weekly_rate (08-10) overlap.
    # Priority: daily_skip_burst > streak_broken > low_weekly_rate
    # At hour 8, skip_burst window is 17-22, so it won't fire.
    # streak_broken fires first at hour 8.
    with patch("motivation_svc.datetime", _mock_hour(8)), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=True), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.7):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    # streak_broken has higher priority than low_weekly_rate
    assert trigger == "streak_broken"


# ─── generate_motivation_message ────────────────────────────────────────────

def test_generate_motivation_message_calls_claude_ask():
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "You've got this!"
        result = motivation_svc.generate_motivation_message("daily_skip_burst")
    mock_claude._ask.assert_called_once()
    assert result == "You've got this!"


def test_generate_motivation_message_prompt_contains_tone():
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "test"
        motivation_svc.generate_motivation_message("daily_skip_burst")
    prompt = mock_claude._ask.call_args[0][0]
    assert "skipped 3 or more" in prompt


def test_generate_motivation_message_unknown_trigger_uses_fallback():
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "test"
        motivation_svc.generate_motivation_message("nonexistent_trigger")
    prompt = mock_claude._ask.call_args[0][0]
    # Falls back to the default tone string
    assert "brief" in prompt.lower() or "warm" in prompt.lower()


def test_generate_motivation_message_passes_max_tokens():
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "test"
        motivation_svc.generate_motivation_message("no_activity")
    _, kwargs = mock_claude._ask.call_args
    assert kwargs.get("max_tokens") == 200


# ─── check_and_send_for_user ────────────────────────────────────────────────

def test_check_and_send_skips_if_recently_motivated():
    bot = AsyncMock()
    with patch("motivation_svc._was_recently_motivated", return_value=True):
        asyncio.run(motivation_svc.check_and_send_for_user(bot, 42))
    bot.send_message.assert_not_called()


def test_check_and_send_skips_if_no_trigger_fires():
    bot = AsyncMock()
    with patch("motivation_svc._was_recently_motivated", return_value=False), \
         patch("motivation_svc.evaluate_triggers", return_value=(None, False)):
        asyncio.run(motivation_svc.check_and_send_for_user(bot, 42))
    bot.send_message.assert_not_called()


def test_check_and_send_sends_message_when_triggered():
    bot = AsyncMock()
    with patch("motivation_svc._was_recently_motivated", return_value=False), \
         patch("motivation_svc.evaluate_triggers", return_value=("no_activity", True)), \
         patch("motivation_svc.generate_motivation_message", return_value="Hey, you ok?"), \
         patch("motivation_svc._log_motivation_sent") as mock_log:
        asyncio.run(motivation_svc.check_and_send_for_user(bot, 42))
    bot.send_message.assert_called_once_with(42, "Hey, you ok?")
    mock_log.assert_called_once_with(42, "no_activity")


def test_check_and_send_logs_after_successful_send():
    bot = AsyncMock()
    with patch("motivation_svc._was_recently_motivated", return_value=False), \
         patch("motivation_svc.evaluate_triggers", return_value=("streak_broken", True)), \
         patch("motivation_svc.generate_motivation_message", return_value="Come back!"), \
         patch("motivation_svc._log_motivation_sent") as mock_log:
        asyncio.run(motivation_svc.check_and_send_for_user(bot, 99))
    mock_log.assert_called_once_with(99, "streak_broken")


def test_check_and_send_does_not_log_if_send_fails():
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("network error")
    with patch("motivation_svc._was_recently_motivated", return_value=False), \
         patch("motivation_svc.evaluate_triggers", return_value=("no_activity", True)), \
         patch("motivation_svc.generate_motivation_message", return_value="Hey!"), \
         patch("motivation_svc._log_motivation_sent") as mock_log:
        # Should not raise — exception is caught inside the function
        asyncio.run(motivation_svc.check_and_send_for_user(bot, 5))
    mock_log.assert_not_called()


# ─── Context engine: _most_avoided_task ─────────────────────────────────────

def test_most_avoided_task_returns_most_skipped_title():
    rows = [{"task_id": "a"}, {"task_id": "b"}, {"task_id": "a"}, {"task_id": "a"}]
    with patch("tasks.svc.get_task", return_value={"title": "Morning run"}):
        assert motivation_svc._most_avoided_task(1, rows) == "Morning run"


def test_most_avoided_task_strips_subtask_suffix():
    rows = [{"task_id": "x"}]
    with patch("tasks.svc.get_task", return_value={"title": "Learn Spanish — Step 2: Verbs"}):
        assert motivation_svc._most_avoided_task(1, rows) == "Learn Spanish"


def test_most_avoided_task_none_when_no_skips():
    assert motivation_svc._most_avoided_task(1, []) is None


def test_most_avoided_task_none_when_task_lookup_empty():
    rows = [{"task_id": "gone"}]
    with patch("tasks.svc.get_task", return_value=None):
        assert motivation_svc._most_avoided_task(1, rows) is None


def test_most_avoided_task_ignores_null_task_ids():
    rows = [{"task_id": None}, {"task_id": None}]
    assert motivation_svc._most_avoided_task(1, rows) is None


# ─── Context engine: _busiest_weekday ───────────────────────────────────────

def test_busiest_weekday_picks_most_common():
    # Three Mondays, one Friday
    mondays = [date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15)]
    friday = [date(2026, 6, 5)]
    assert motivation_svc._busiest_weekday(mondays + friday) == "Monday"


def test_busiest_weekday_none_on_empty():
    assert motivation_svc._busiest_weekday([]) is None


# ─── Context engine: _recent_wins ───────────────────────────────────────────

def test_recent_wins_returns_titles_newest_first():
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"note": "Gym", "event_type": "habit", "event_date": "2026-06-13"},
        {"note": "Read", "event_type": "study", "event_date": "2026-06-12"},
    ]
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._recent_wins(1) == ["Gym", "Read"]


def test_recent_wins_filters_auto_skip_and_dedupes():
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"note": "auto_skip:Gym"}, {"note": "Read"}, {"note": "Read"}, {"note": ""},
    ]
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._recent_wins(1) == ["Read"]


def test_recent_wins_dedupes_case_insensitively():
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"note": "Call the Bank"}, {"note": "Call The Bank"}, {"note": "call the bank"},
    ]
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._recent_wins(1) == ["Call the Bank"]


def test_recent_wins_empty_on_db_error():
    c = MagicMock()
    c.table.side_effect = Exception("boom")
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._recent_wins(1) == []


# ─── Context engine: gather_user_context ────────────────────────────────────

def test_gather_user_context_assembles_fields():
    skip_rows = [{"task_id": "a", "skipped_at": "2026-06-08T10:00:00+00:00"}]  # Monday IST
    done_rows = [{"event_date": "2026-06-13"}]  # Saturday
    with patch("settings_svc.get_settings", return_value={"streak": 4, "persona": "flirty"}), \
         patch("tasks.svc.list_tasks", return_value=[{"title": "Run"}, {"title": "X — Step 1: y"}]), \
         patch("analytics_svc.get_skips_last_n_days", return_value=skip_rows), \
         patch("analytics_svc.get_done_counts_last_n_days", return_value=done_rows), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.3), \
         patch("motivation_svc._days_since_any_activity", return_value=1), \
         patch("motivation_svc._most_avoided_task", return_value="Run"), \
         patch("motivation_svc._recent_wins", return_value=["Gym"]):
        ctx = motivation_svc.gather_user_context(1)
    assert ctx["streak"] == 4
    assert ctx["persona"] == "flirty"
    assert ctx["n_active_habits"] == 1  # subtask excluded
    assert ctx["most_avoided_task"] == "Run"
    assert ctx["recent_wins"] == ["Gym"]
    assert ctx["best_weekday"] == "Saturday"
    assert ctx["worst_weekday"] == "Monday"


def test_gather_user_context_degrades_on_errors():
    with patch("settings_svc.get_settings", side_effect=Exception), \
         patch("tasks.svc.list_tasks", side_effect=Exception), \
         patch("analytics_svc.get_skips_last_n_days", side_effect=Exception), \
         patch("analytics_svc.get_done_counts_last_n_days", side_effect=Exception), \
         patch("motivation_svc._skip_rate_last_7_days", side_effect=Exception), \
         patch("motivation_svc._days_since_any_activity", side_effect=Exception), \
         patch("motivation_svc._recent_wins", return_value=[]):
        ctx = motivation_svc.gather_user_context(1)
    assert ctx["streak"] == 0
    assert ctx["persona"] == "default"
    assert ctx["most_avoided_task"] is None
    assert ctx["days_since_active"] == 999


# ─── Context engine: _context_brief ─────────────────────────────────────────

def test_context_brief_includes_specifics():
    ctx = {"streak": 5, "most_avoided_task": "Run", "best_weekday": "Monday",
           "worst_weekday": "Friday", "recent_wins": ["Gym"], "n_active_habits": 2}
    brief = motivation_svc._context_brief(ctx)
    assert "Run" in brief and "Monday" in brief and "Gym" in brief and "5 days" in brief


def test_context_brief_empty_when_no_data():
    brief = motivation_svc._context_brief({})
    assert "No history" in brief


def test_context_brief_omits_streak_of_one():
    brief = motivation_svc._context_brief({"streak": 1})
    assert "streak" not in brief.lower()


def test_generate_motivation_message_weaves_real_specifics():
    ctx = {"most_avoided_task": "Morning run", "streak": 6}
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "ok"
        motivation_svc.generate_motivation_message("daily_skip_burst", ctx)
    prompt = mock_claude._ask.call_args[0][0]
    assert "Morning run" in prompt and "identity" in prompt.lower()


# ─── comeback trigger: _just_came_back ──────────────────────────────────────

def _activity_client(event_dates: list):
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"event_date": d} for d in event_dates
    ]
    return c


def test_just_came_back_true_when_returned_today_after_gap():
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=4)).isoformat()
    with patch("motivation_svc.get_client", return_value=_activity_client([today, old])):
        assert motivation_svc._just_came_back(1) is True


def test_just_came_back_false_when_gap_too_small():
    today = date.today().isoformat()
    yest = (date.today() - timedelta(days=1)).isoformat()
    with patch("motivation_svc.get_client", return_value=_activity_client([today, yest])):
        assert motivation_svc._just_came_back(1) is False


def test_just_came_back_false_when_latest_not_today():
    y = (date.today() - timedelta(days=1)).isoformat()
    old = (date.today() - timedelta(days=6)).isoformat()
    with patch("motivation_svc.get_client", return_value=_activity_client([y, old])):
        assert motivation_svc._just_came_back(1) is False


def test_just_came_back_false_with_single_day():
    today = date.today().isoformat()
    with patch("motivation_svc.get_client", return_value=_activity_client([today])):
        assert motivation_svc._just_came_back(1) is False


def test_just_came_back_dedupes_same_day_rows():
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=5)).isoformat()
    # multiple dones today should not count as two distinct days
    with patch("motivation_svc.get_client", return_value=_activity_client([today, today, today, old])):
        assert motivation_svc._just_came_back(1) is True


# ─── comeback trigger in evaluate_triggers ──────────────────────────────────

def test_evaluate_comeback_fires_daytime_top_priority():
    with patch("motivation_svc.datetime", _mock_hour(14)), \
         patch("motivation_svc._just_came_back", return_value=True), \
         patch("motivation_svc._count_skips_today", return_value=5), \
         patch("motivation_svc._is_streak_broken", return_value=True), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.9), \
         patch("motivation_svc._days_since_any_activity", return_value=9):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger == "comeback" and fired is True


def test_evaluate_comeback_does_not_fire_at_night():
    with patch("motivation_svc.datetime", _mock_hour(23)), \
         patch("motivation_svc._just_came_back", return_value=True), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=False), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.0), \
         patch("motivation_svc._days_since_any_activity", return_value=0):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger is None


def test_comeback_tone_guide_exists_and_celebrates():
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "welcome back!"
        motivation_svc.generate_motivation_message("comeback", {"streak": 2})
    prompt = mock_claude._ask.call_args[0][0]
    assert "celebrate" in prompt.lower() or "came back" in prompt.lower()


# ─── memory of what works: _responds_to ─────────────────────────────────────

def _reengage_client(rows):
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.execute.return_value.data = rows
    return c


def test_responds_to_none_with_too_little_data():
    rows = [{"trigger_type": "comeback", "reengaged": True}]  # only 1 scored
    with patch("motivation_svc.get_client", return_value=_reengage_client(rows)):
        assert motivation_svc._responds_to(1) is None


def test_responds_to_none_when_nothing_landed():
    rows = [{"trigger_type": "no_activity", "reengaged": False},
            {"trigger_type": "streak_broken", "reengaged": False}]
    with patch("motivation_svc.get_client", return_value=_reengage_client(rows)):
        assert motivation_svc._responds_to(1) is None


def test_responds_to_picks_best_trigger_by_rate():
    rows = [
        {"trigger_type": "comeback", "reengaged": True},
        {"trigger_type": "comeback", "reengaged": True},
        {"trigger_type": "no_activity", "reengaged": False},
        {"trigger_type": "no_activity", "reengaged": False},
    ]
    with patch("motivation_svc.get_client", return_value=_reengage_client(rows)):
        assert motivation_svc._responds_to(1) == "comeback"


def test_responds_to_safe_on_db_error():
    c = MagicMock()
    c.table.side_effect = Exception("boom")
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._responds_to(1) is None


# ─── memory of what works: _score_recent_outcomes ───────────────────────────

def test_score_recent_outcomes_marks_old_skips_recent():
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc)
    old = (now - timedelta(hours=30)).isoformat()   # window closed -> score it
    fresh = (now - timedelta(hours=2)).isoformat()  # too early -> leave NULL
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = [
        {"id": "A", "sent_at": old, "reengaged": None},
        {"id": "B", "sent_at": fresh, "reengaged": None},
    ]
    with patch("motivation_svc.get_client", return_value=c), \
         patch("motivation_svc._user_reengaged_between", return_value=True) as ms:
        motivation_svc._score_recent_outcomes(1)
    # only the old (window-closed) row gets scored
    ms.assert_called_once()
    upd = c.table.return_value.update
    upd.assert_called_once_with({"reengaged": True})
    upd.return_value.eq.assert_called_once_with("id", "A")


def test_score_recent_outcomes_never_raises():
    c = MagicMock()
    c.table.side_effect = Exception("db down")
    with patch("motivation_svc.get_client", return_value=c):
        motivation_svc._score_recent_outcomes(1)  # must not raise


# ─── responds_to flows into gather_user_context + prompt ────────────────────

def test_context_brief_includes_responds_to_hint():
    brief = motivation_svc._context_brief({"responds_to": "comeback"})
    assert "landed before" in brief.lower() and "welcome-back" in brief.lower()


def test_context_brief_ignores_unknown_responds_to():
    brief = motivation_svc._context_brief({"responds_to": "bogus"})
    assert "landed before" not in brief.lower()


# ─── CRISIS safety layer ────────────────────────────────────────────────────

import pytest as _pytest


@_pytest.mark.parametrize("text", [
    "i want to kill myself",
    "honestly i don't want to live anymore",
    "i feel suicidal",
    "i'm thinking about ending it all",
    "i just want to die",
    "i've been cutting myself again",
    "there's no reason to live",
    "i wish i was dead",
    "i can't go on anymore",
    "i don't want to be here anymore",
    "i'm going to commit suicide",
])
def test_is_crisis_message_true_on_ideation(text):
    assert motivation_svc.is_crisis_message(text) is True


@_pytest.mark.parametrize("text", [
    "i keep failing at everything",       # struggle, not crisis
    "this deadline is killing me",         # idiom
    "i'm dying to see the results",        # idiom
    "i could kill for a coffee",           # idiom
    "i give up on this habit",             # struggle
    "i'm so overwhelmed today",            # struggle
    "i'm dead tired",                      # idiom
    "add gym at 6pm",                      # normal task
])
def test_is_crisis_message_false_on_idioms_and_struggle(text):
    assert motivation_svc.is_crisis_message(text) is False


def test_crisis_response_is_static_card_with_helplines():
    card = motivation_svc.crisis_response(123)
    assert "1800-599-0019" in card        # KIRAN
    assert "AASRA" in card
    assert "112" in card                  # emergency line


def test_crisis_takes_priority_over_struggle():
    # a phrase that is BOTH crisis and struggle-ish must be classified as crisis
    t = "i can't do this anymore, i want to kill myself"
    assert motivation_svc.is_crisis_message(t) is True
    # handler checks crisis first, so struggle routing never runs for this text


# ─── pattern insight: _skip_weekday_pattern ─────────────────────────────────
# 2026-06-08 is a Monday, 06-12 a Friday (06-14 is Sunday). Midday UTC stays
# on the same IST weekday.

def _skips_on(*iso_days):
    return [{"task_id": "t", "skipped_at": f"{d}T06:00:00+00:00", "note": ""} for d in iso_days]


def test_skip_weekday_pattern_detects_dominant_monday():
    rows = _skips_on("2026-06-08", "2026-06-08", "2026-06-08", "2026-06-12")  # 3 Mon, 1 Fri
    with patch("analytics_svc.get_skips_last_n_days", return_value=rows):
        assert motivation_svc._skip_weekday_pattern(1) == "Monday"


def test_skip_weekday_pattern_none_when_too_few():
    rows = _skips_on("2026-06-08", "2026-06-08", "2026-06-08")  # only 3 total (<4)
    with patch("analytics_svc.get_skips_last_n_days", return_value=rows):
        assert motivation_svc._skip_weekday_pattern(1) is None


def test_skip_weekday_pattern_none_when_no_dominance():
    rows = _skips_on("2026-06-08", "2026-06-09", "2026-06-10", "2026-06-12")  # 4 diff days
    with patch("analytics_svc.get_skips_last_n_days", return_value=rows):
        assert motivation_svc._skip_weekday_pattern(1) is None


def test_skip_weekday_pattern_safe_on_error():
    with patch("analytics_svc.get_skips_last_n_days", side_effect=Exception):
        assert motivation_svc._skip_weekday_pattern(1) is None


def test_evaluate_pattern_insight_fires_and_beats_no_activity():
    with patch("motivation_svc.datetime", _mock_hour(12)), \
         patch("motivation_svc._just_came_back", return_value=False), \
         patch("motivation_svc._count_skips_today", return_value=0), \
         patch("motivation_svc._is_streak_broken", return_value=False), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.0), \
         patch("motivation_svc._skip_weekday_pattern", return_value="Monday"), \
         patch("motivation_svc._days_since_any_activity", return_value=9):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger == "pattern_insight" and fired is True


def test_pattern_insight_tone_guide_exists():
    with patch("motivation_svc.claude_svc") as mock_claude:
        mock_claude._ask.return_value = "noticed something"
        motivation_svc.generate_motivation_message("pattern_insight", {"worst_weekday": "Monday"})
    prompt = mock_claude._ask.call_args[0][0]
    assert "pattern" in prompt.lower() and "Monday" in prompt


# ─── adaptive timing: _active_hours / _within_active_hours ──────────────────

def _hours_client(act_times, skip_times):
    c = MagicMock()
    act = MagicMock()
    act.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
        {"created_at": t} for t in act_times]
    sk = MagicMock()
    sk.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
        {"skipped_at": t} for t in skip_times]
    c.table.side_effect = lambda n: act if n == "activity_log" else sk
    return c


def test_active_hours_band_around_peak():
    # five events at IST hour 8 (+05:30 offset fixes the IST hour directly)
    times = [f"2026-06-{d:02d}T08:30:00+05:30" for d in (8, 9, 10, 11, 12)]
    with patch("motivation_svc.get_client", return_value=_hours_client(times, [])):
        band = motivation_svc._active_hours(1)
    assert band == {5, 6, 7, 8, 9, 10, 11}


def test_active_hours_none_when_too_little():
    times = ["2026-06-10T08:30:00+05:30", "2026-06-11T08:30:00+05:30"]
    with patch("motivation_svc.get_client", return_value=_hours_client(times, [])):
        assert motivation_svc._active_hours(1) is None


def test_active_hours_safe_on_error():
    c = MagicMock(); c.table.side_effect = Exception("x")
    with patch("motivation_svc.get_client", return_value=c):
        assert motivation_svc._active_hours(1) is None


def test_within_active_hours_off_always_true():
    with patch("settings_svc.get_adaptive_timing", return_value=False):
        assert motivation_svc._within_active_hours(1, 3) is True  # 3am, but feature off


def test_within_active_hours_on_no_data_true():
    with patch("settings_svc.get_adaptive_timing", return_value=True), \
         patch("motivation_svc._active_hours", return_value=None):
        assert motivation_svc._within_active_hours(1, 3) is True


def test_within_active_hours_on_in_and_out_of_band():
    with patch("settings_svc.get_adaptive_timing", return_value=True), \
         patch("motivation_svc._active_hours", return_value={5, 6, 7, 8, 9}):
        assert motivation_svc._within_active_hours(1, 8) is True
        assert motivation_svc._within_active_hours(1, 20) is False


def test_evaluate_triggers_ignore_hours_fires_off_window():
    # 3am is outside every fixed window; ignore_hours=True fires by condition
    with patch("motivation_svc.datetime", _mock_hour(3)), \
         patch("motivation_svc._just_came_back", return_value=True):
        trigger, fired = motivation_svc.evaluate_triggers(1, ignore_hours=True)
    assert trigger == "comeback" and fired is True


def test_evaluate_triggers_default_respects_window():
    # same 3am, default (fixed windows) → nothing fires
    with patch("motivation_svc.datetime", _mock_hour(3)), \
         patch("motivation_svc._just_came_back", return_value=True), \
         patch("motivation_svc._count_skips_today", return_value=9), \
         patch("motivation_svc._is_streak_broken", return_value=True), \
         patch("motivation_svc._skip_rate_last_7_days", return_value=0.9), \
         patch("motivation_svc._skip_weekday_pattern", return_value="Monday"), \
         patch("motivation_svc._days_since_any_activity", return_value=9):
        trigger, fired = motivation_svc.evaluate_triggers(1)
    assert trigger is None


def test_check_and_send_adaptive_blocks_outside_active_hours():
    bot = AsyncMock()
    with patch("motivation_svc._score_recent_outcomes"), \
         patch("motivation_svc._was_recently_motivated", return_value=False), \
         patch("settings_svc.get_adaptive_timing", return_value=True), \
         patch("motivation_svc.evaluate_triggers", return_value=("no_activity", True)), \
         patch("motivation_svc._within_active_hours", return_value=False):
        asyncio.run(motivation_svc.check_and_send_for_user(bot, 7))
    bot.send_message.assert_not_called()
