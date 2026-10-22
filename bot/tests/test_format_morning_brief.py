"""
Tests for format_morning_brief and format_eod in scheduler.py.

Covers previously untested paths:
  - plan-status study goal (Day X/N, on-track vs behind)
  - milestones with overdue / near / far / absent deadlines
  - habits due today vs. scheduled for a future date
  - unscheduled tasks section
  - missed-yesterday section
  - EOD with studied-today topics
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytz
import pytest

# scheduler is already imported in conftest; re-import from sys.modules is fine.
import scheduler

IST = pytz.timezone("Asia/Kolkata")

_EMPTY_SETTINGS = {"streak": 0}
_GOAL = {"id": "g1", "name": "Python", "target_date": "2026-12-31", "status": "in_progress"}
_TOPIC = {"id": "t1", "title": "Decorators", "goal_id": "g1",
          "status": "not_started", "parent_id": None}


def _tomorrow_ist_iso() -> str:
    return (datetime.now(IST) + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    ).isoformat()


def _past_ist_iso() -> str:
    return (datetime.now(IST) - timedelta(hours=2)).replace(second=0, microsecond=0).isoformat()


# ── format_morning_brief: plan-status study path ─────────────────────────────

def test_morning_brief_plan_on_track_shows_day_and_status():
    plan = {"day": 3, "total_days": 10, "completed": 3, "total": 10,
            "on_track": True, "today_topic": _TOPIC, "goal_name": "Python"}
    with patch("scheduler.study_svc.list_goals", return_value=[_GOAL]), \
         patch("scheduler.study_svc.get_plan_status", return_value=plan), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[]), \
         patch("scheduler.tasks_svc.count_milestones", return_value={"done": 0, "total": 0}), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "Day 3/10" in msg
    assert "on track" in msg
    assert "Decorators" in msg


def test_morning_brief_plan_behind_shows_behind_status():
    plan = {"day": 5, "total_days": 10, "completed": 2, "total": 10,
            "on_track": False, "today_topic": _TOPIC, "goal_name": "Python"}
    with patch("scheduler.study_svc.list_goals", return_value=[_GOAL]), \
         patch("scheduler.study_svc.get_plan_status", return_value=plan), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[]), \
         patch("scheduler.tasks_svc.count_milestones", return_value={"done": 0, "total": 0}), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "behind" in msg.lower()


# ── format_morning_brief: milestone deadline variants ────────────────────────

def _milestone_brief(target_date_iso: str | None):
    milestone = {"id": "m1", "title": "Launch v1", "task_type": "milestone",
                 "target_date": target_date_iso, "next_reminder_at": None}
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[milestone]), \
         patch("scheduler.tasks_svc.count_milestones", return_value={"done": 1, "total": 4}), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        return scheduler.format_morning_brief(1)


def test_morning_brief_milestone_overdue():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    msg = _milestone_brief(yesterday)
    assert "Launch v1" in msg
    assert "Overdue" in msg


def test_morning_brief_milestone_near_deadline():
    in_two_days = (date.today() + timedelta(days=2)).isoformat()
    msg = _milestone_brief(in_two_days)
    assert "Launch v1" in msg
    assert "🔥" in msg
    assert "2d left" in msg


def test_morning_brief_milestone_far_deadline():
    far_future = (date.today() + timedelta(days=20)).isoformat()
    msg = _milestone_brief(far_future)
    assert "Launch v1" in msg
    assert "(20d left)" in msg
    assert "Overdue" not in msg
    # The far-deadline line must NOT carry the 🔥 urgency marker
    milestone_line = next(l for l in msg.splitlines() if "Launch v1" in l)
    assert "🔥" not in milestone_line


def test_morning_brief_milestone_no_target_date():
    msg = _milestone_brief(None)
    assert "Launch v1" in msg
    # No deadline suffix means none of these markers appear on that line
    assert "Overdue" not in msg
    assert "d left" not in msg


# ── format_morning_brief: habits ─────────────────────────────────────────────

def test_morning_brief_habit_due_today_shows_due_today():
    habit = {"id": "h1", "title": "Morning run", "task_type": "habit",
             "next_reminder_at": _past_ist_iso()}
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[habit]), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "Morning run" in msg
    assert "due today" in msg


def test_morning_brief_habit_future_shows_next_date():
    habit = {"id": "h1", "title": "Evening walk", "task_type": "habit",
             "next_reminder_at": _tomorrow_ist_iso()}
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[habit]), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "Evening walk" in msg
    assert "next:" in msg.lower()


# ── format_morning_brief: unscheduled tasks section ──────────────────────────

def test_morning_brief_unscheduled_task_appears_in_section():
    task = {"id": "u1", "title": "Review PR", "task_type": "task",
            "next_reminder_at": None}
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[task]), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "Review PR" in msg
    assert "Unscheduled" in msg


def test_morning_brief_no_unscheduled_section_when_all_have_reminders():
    task = {"id": "u1", "title": "Review PR", "task_type": "task",
            "next_reminder_at": _tomorrow_ist_iso()}
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[task]), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "Unscheduled tasks" not in msg


# ── format_morning_brief: missed yesterday section ───────────────────────────

def test_morning_brief_missed_yesterday_listed():
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[]), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=["Meditation", "Reading"]):
        msg = scheduler.format_morning_brief(1)
    assert "Missed yesterday" in msg
    assert "Meditation" in msg
    assert "Reading" in msg


def test_morning_brief_no_missed_section_when_none_missed():
    with patch("scheduler.study_svc.list_goals", return_value=[]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[]), \
         patch("scheduler.study_svc.get_next_pending_topic", return_value=None), \
         patch("scheduler.settings_svc.get_settings", return_value=_EMPTY_SETTINGS), \
         patch("scheduler.get_missed_yesterday", return_value=[]):
        msg = scheduler.format_morning_brief(1)
    assert "Missed yesterday" not in msg


# ── format_eod: studied-today topics ─────────────────────────────────────────

def test_format_eod_studied_today_topic_shown():
    now_ist = datetime.now(IST)
    # completed_at set to today in IST → should appear as studied today
    completed_at = now_ist.replace(hour=14, minute=0, second=0, microsecond=0).isoformat()
    goal = {"id": "g1", "name": "Algorithms", "status": "in_progress"}
    topic = {"id": "t1", "title": "Binary Search", "status": "completed",
             "completed_at": completed_at}
    with patch("scheduler.study_svc.list_goals", return_value=[goal]), \
         patch("scheduler.study_svc.list_topics_for_goal", return_value=[topic]), \
         patch("scheduler.tasks_svc.list_tasks", return_value=[]), \
         patch("scheduler.settings_svc.get_settings", return_value={"streak": 3}):
        msg = scheduler.format_eod(1)
    assert "Binary Search" in msg
    assert "Studied today" in msg or "studied today" in msg.lower()
