"""Tests for format_plan and _format_goal_status in study/handlers.py (zero prior coverage)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
import pytz
import pytest

with patch('supabase_svc.create_client'):
    from study.handlers import format_plan, _format_goal_status

IST = pytz.timezone("Asia/Kolkata")


# ---------------------------------------------------------------------------
# format_plan
# ---------------------------------------------------------------------------

def test_format_plan_includes_goal_name():
    result = format_plan("Machine Learning", [])
    assert "Machine Learning" in result


def test_format_plan_default_difficulty_medium():
    result = format_plan("X", [])
    assert "Medium 🟡" in result


def test_format_plan_difficulty_easy():
    result = format_plan("X", [], difficulty="easy")
    assert "Easy 🟢" in result


def test_format_plan_difficulty_hard():
    result = format_plan("X", [], difficulty="hard")
    assert "Hard 🔴" in result


def test_format_plan_unknown_difficulty_falls_back_to_medium():
    result = format_plan("X", [], difficulty="legendary")
    assert "Medium 🟡" in result


def test_format_plan_today_label_when_scheduled_today():
    today = date.today()
    topics = [{"title": "Intro", "scheduled_date": today.isoformat()}]
    result = format_plan("Python", topics)
    assert "today" in result


def test_format_plan_non_today_date_formatted():
    # Use a fixed date that is clearly not today.
    fixed = date(2030, 12, 25)
    topics = [{"title": "Deep Learning", "scheduled_date": fixed.isoformat()}]
    result = format_plan("ML", topics)
    # Topic line should show the formatted date ("Wed 25 Dec"), not "today"
    assert "25 Dec" in result
    topic_line = [l for l in result.splitlines() if "Deep Learning" in l][0]
    assert "today" not in topic_line


def test_format_plan_no_scheduled_date_shows_dash():
    topics = [{"title": "Intro", "scheduled_date": None}]
    result = format_plan("Python", topics)
    assert "—" in result


def test_format_plan_footer_has_topic_count():
    topics = [
        {"title": "A", "scheduled_date": None},
        {"title": "B", "scheduled_date": None},
        {"title": "C", "scheduled_date": None},
    ]
    result = format_plan("Python", topics)
    assert "3 topics" in result


def test_format_plan_footer_mentions_goal_name():
    result = format_plan("System Design", [{"title": "A", "scheduled_date": None}])
    assert "study System Design" in result


def test_format_plan_topics_are_numbered():
    topics = [
        {"title": "First", "scheduled_date": None},
        {"title": "Second", "scheduled_date": None},
    ]
    result = format_plan("Python", topics)
    assert "1." in result
    assert "2." in result


def test_format_plan_empty_scheduled_gives_zero_count():
    result = format_plan("X", [])
    assert "0 topics" in result


# ---------------------------------------------------------------------------
# _format_goal_status
# ---------------------------------------------------------------------------

def _mock_counts(total, completed):
    return {"total": total, "completed": completed}


def test_format_goal_status_no_topics_shows_placeholder():
    goal = {"id": "g1", "name": "Python", "target_date": None}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(0, 0)
        result = _format_goal_status(goal)
    assert "No topics yet" in result


def test_format_goal_status_includes_goal_name():
    goal = {"id": "g1", "name": "Deep Learning", "target_date": None}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(0, 0)
        result = _format_goal_status(goal)
    assert "Deep Learning" in result


def test_format_goal_status_all_done_shows_100_percent():
    goal = {"id": "g1", "name": "Python", "target_date": None}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(10, 10)
        result = _format_goal_status(goal)
    assert "10/10" in result
    assert "100%" in result


def test_format_goal_status_half_done_shows_50_percent():
    goal = {"id": "g1", "name": "Python", "target_date": None}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(10, 5)
        result = _format_goal_status(goal)
    assert "5/10" in result
    assert "50%" in result


def test_format_goal_status_no_target_date_has_no_deadline_indicator():
    goal = {"id": "g1", "name": "Python", "target_date": None}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(4, 1)
        result = _format_goal_status(goal)
    assert "⚠️" not in result
    assert "🔥" not in result
    assert "⏰" not in result
    assert "📅" not in result


def test_format_goal_status_overdue_shows_warning():
    goal = {"id": "g1", "name": "Python", "target_date": "2020-01-01"}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(5, 2)
        result = _format_goal_status(goal)
    assert "⚠️" in result
    assert "Overdue" in result


def test_format_goal_status_due_today_shows_fire():
    today_ist = datetime.now(IST).date().isoformat()
    goal = {"id": "g1", "name": "Python", "target_date": today_ist}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(5, 2)
        result = _format_goal_status(goal)
    assert "🔥" in result
    assert "Due today" in result


def test_format_goal_status_within_7_days_shows_clock():
    in_3_days = (datetime.now(IST).date() + timedelta(days=3)).isoformat()
    goal = {"id": "g1", "name": "Python", "target_date": in_3_days}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(5, 2)
        result = _format_goal_status(goal)
    assert "⏰" in result
    assert "3d left" in result


def test_format_goal_status_more_than_7_days_shows_calendar():
    in_30_days = (datetime.now(IST).date() + timedelta(days=30)).isoformat()
    goal = {"id": "g1", "name": "Python", "target_date": in_30_days}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(5, 2)
        result = _format_goal_status(goal)
    assert "📅" in result
    assert "30d left" in result


def test_format_goal_status_invalid_date_falls_back_gracefully():
    goal = {"id": "g1", "name": "Python", "target_date": "not-a-date"}
    with patch('study.handlers.db') as mock_db:
        mock_db.count_topics_for_goal.return_value = _mock_counts(3, 1)
        result = _format_goal_status(goal)
    # Fallback: shows "📅 not-a-date"
    assert "📅" in result
    assert "not-a-date" in result
