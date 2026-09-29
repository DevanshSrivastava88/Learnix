import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone, timedelta

import pytz

with patch('supabase_svc.create_client'):
    import scheduler

IST = pytz.timezone("Asia/Kolkata")


def make_goal(name='AI Engineer', total=10, completed=3, target='2026-12-01'):
    return {'id': 'g1', 'name': name, 'target_date': target, 'status': 'in_progress'}


def make_task(title, task_type='habit', next_reminder_at=None):
    return {'id': '1', 'title': title, 'task_type': task_type, 'next_reminder_at': next_reminder_at}


# ── format_morning_brief ──────────────────────────────────────────────────────

def test_format_morning_brief_no_data():
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.study_svc.get_next_pending_topic', return_value=None), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 0}):
        msg = scheduler.format_morning_brief(123)
        assert 'morning' in msg.lower() or 'Morning' in msg
        assert 'No ' in msg or 'no ' in msg.lower()

def test_format_morning_brief_with_study_goal():
    goal = make_goal()
    topic = {'id': 't1', 'title': 'Backprop', 'goal_id': 'g1', 'status': 'not_started', 'parent_id': None}
    with patch('scheduler.study_svc.list_goals', return_value=[goal]), \
         patch('scheduler.study_svc.count_topics_for_goal', return_value={'total': 10, 'completed': 3, 'not_started': 7, 'needs_revision': 0}), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.study_svc.get_next_pending_topic', return_value=topic), \
         patch('scheduler.study_svc.get_goal', return_value=goal), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 5}):
        msg = scheduler.format_morning_brief(123)
        assert 'Backprop' in msg
        assert 'AI Engineer' in msg


# ── format_eod ────────────────────────────────────────────────────────────────

def test_format_eod_empty():
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 2}):
        msg = scheduler.format_eod(123)
        assert 'wrap' in msg.lower() or 'eod' in msg.lower() or 'day' in msg.lower()
        assert '2' in msg


def test_format_eod_habit_done_shows_checkmark():
    # A habit whose next_reminder_at is tomorrow → done today
    tomorrow_ist = (datetime.now(IST) + timedelta(days=1)).replace(hour=9, minute=0, second=0)
    habit = make_task('Meditate', task_type='habit', next_reminder_at=tomorrow_ist.isoformat())
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[habit]), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 3}):
        msg = scheduler.format_eod(123)
    assert 'Meditate' in msg
    assert '✅' in msg


def test_format_eod_habit_not_done_shows_cross():
    # A habit whose next_reminder_at is today or earlier → not done
    overdue_ist = (datetime.now(IST) - timedelta(hours=1)).replace(second=0)
    habit = make_task('Evening run', task_type='habit', next_reminder_at=overdue_ist.isoformat())
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[habit]), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 0}):
        msg = scheduler.format_eod(123)
    assert 'Evening run' in msg
    assert 'not done' in msg


# ── format_evening_digest ─────────────────────────────────────────────────────

def test_format_evening_digest_empty_when_all_tasks_have_reminders():
    tasks = [
        make_task('Workout', task_type='habit', next_reminder_at='2026-09-29T18:00:00+05:30'),
        make_task('Reading', task_type='task', next_reminder_at='2026-09-29T20:00:00+05:30'),
    ]
    with patch('scheduler.tasks_svc.list_tasks', return_value=tasks):
        result = scheduler.format_evening_digest(42)
    assert result == ''


def test_format_evening_digest_returns_message_for_unscheduled():
    tasks = [make_task('Morning yoga', task_type='habit', next_reminder_at=None)]
    with patch('scheduler.tasks_svc.list_tasks', return_value=tasks):
        result = scheduler.format_evening_digest(42)
    assert 'Morning yoga' in result
    assert result != ''


def test_format_evening_digest_habits_get_recycle_marker():
    tasks = [make_task('Daily walk', task_type='habit', next_reminder_at=None)]
    with patch('scheduler.tasks_svc.list_tasks', return_value=tasks):
        result = scheduler.format_evening_digest(42)
    assert '🔁' in result


def test_format_evening_digest_plain_tasks_get_bullet():
    tasks = [make_task('Buy groceries', task_type='task', next_reminder_at=None)]
    with patch('scheduler.tasks_svc.list_tasks', return_value=tasks):
        result = scheduler.format_evening_digest(42)
    assert '•' in result
    assert '🔁' not in result


def test_format_evening_digest_excludes_subtasks():
    tasks = [
        make_task('Project — Step 1: Research', task_type='task', next_reminder_at=None),
        make_task('Journaling', task_type='habit', next_reminder_at=None),
    ]
    with patch('scheduler.tasks_svc.list_tasks', return_value=tasks):
        result = scheduler.format_evening_digest(42)
    assert 'Project' not in result
    assert 'Journaling' in result


def test_format_evening_digest_excludes_milestones():
    tasks = [
        make_task('Ship feature', task_type='milestone', next_reminder_at=None),
        make_task('Meditate', task_type='habit', next_reminder_at=None),
    ]
    with patch('scheduler.tasks_svc.list_tasks', return_value=tasks):
        result = scheduler.format_evening_digest(42)
    assert 'Ship feature' not in result
    assert 'Meditate' in result


def test_format_evening_digest_empty_task_list():
    with patch('scheduler.tasks_svc.list_tasks', return_value=[]):
        result = scheduler.format_evening_digest(42)
    assert result == ''
