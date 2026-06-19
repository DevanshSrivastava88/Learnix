import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone

with patch('supabase_svc.create_client'):
    import scheduler

def make_goal(name='AI Engineer', total=10, completed=3, target='2026-12-01'):
    return {'id': 'g1', 'name': name, 'target_date': target, 'status': 'in_progress'}

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

def test_format_eod_empty():
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 2}):
        msg = scheduler.format_eod(123)
        assert 'wrap' in msg.lower() or 'eod' in msg.lower() or 'day' in msg.lower()
        assert '2' in msg

def test_get_missed_yesterday_runs_without_nameerror():
    # Regression: timedelta used at module scope must be importable, else NameError.
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
    with patch('supabase_svc.get_client', return_value=sb):
        result = scheduler.get_missed_yesterday(123)
    assert isinstance(result, list)
    assert result == []
