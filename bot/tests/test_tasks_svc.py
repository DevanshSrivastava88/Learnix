from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import pytest

with patch('supabase_svc.create_client'):
    from tasks import svc as tasks_svc

USER_ID = 222

def _row(**kwargs):
    base = {
        'id': 'task-1', 'user_id': USER_ID, 'title': 'Make bed',
        'task_type': 'habit', 'status': 'active', 'description': '',
        'next_reminder_at': None, 'recurrence_days': 1,
        'target_date': None, 'created_at': '2026-01-01T00:00:00'
    }
    base.update(kwargs)
    return base

def make_client(rows=None):
    c = MagicMock()
    ex = MagicMock(); ex.data = rows or []
    c.table.return_value.insert.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = ex
    c.table.return_value.update.return_value.eq.return_value.execute.return_value = ex
    return c

def test_create_habit_returns_task():
    with patch('tasks.svc.get_client', return_value=make_client(rows=[_row()])):
        result = tasks_svc.create_task(USER_ID, 'Make bed', 'habit', recurrence_days=1)
        assert result['task_type'] == 'habit'

def test_create_milestone_returns_task():
    row = _row(task_type='milestone', recurrence_days=None, target_date='2026-12-01')
    with patch('tasks.svc.get_client', return_value=make_client(rows=[row])):
        result = tasks_svc.create_task(USER_ID, 'Launch project', 'milestone', target_date='2026-12-01')
        assert result['task_type'] == 'milestone'

def test_mark_done_sets_next_reminder():
    with patch('tasks.svc.get_task') as mock_get, \
         patch('tasks.svc.get_client') as mock_client:
        mock_get.return_value = _row(recurrence_days=2)
        client = make_client()
        mock_client.return_value = client
        tasks_svc.mark_done('task-1')
        update_call = client.table.return_value.update.call_args
        updated_data = update_call[0][0]
        assert 'next_reminder_at' in updated_data

def test_get_due_tasks_returns_overdue():
    overdue = _row(next_reminder_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    with patch('tasks.svc.get_client') as mock_client:
        client = MagicMock()
        ex = MagicMock(); ex.data = [overdue]
        client.table.return_value.select.return_value.lte.return_value.eq.return_value.execute.return_value = ex
        mock_client.return_value = client
        result = tasks_svc.get_due_tasks()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Important flag tests
# ---------------------------------------------------------------------------

def test_is_important_true_when_prefixed():
    task = _row(description='important:true|some detail')
    assert tasks_svc.is_important(task) is True


def test_is_important_true_when_only_flag():
    task = _row(description='important:true')
    assert tasks_svc.is_important(task) is True


def test_is_important_false_when_no_prefix():
    task = _row(description='just a regular description')
    assert tasks_svc.is_important(task) is False


def test_is_important_false_when_empty():
    task = _row(description='')
    assert tasks_svc.is_important(task) is False


def test_mark_important_prepends_flag():
    task_data = _row(description='existing detail')
    with patch('tasks.svc.get_task', return_value=task_data), \
         patch('tasks.svc.get_client') as mock_client:
        client = make_client()
        mock_client.return_value = client
        tasks_svc.mark_important('task-1')
        update_call = client.table.return_value.update.call_args
        updated = update_call[0][0]
        assert updated['description'] == 'important:true|existing detail'


def test_mark_important_noop_if_already_important():
    task_data = _row(description='important:true|existing')
    with patch('tasks.svc.get_task', return_value=task_data), \
         patch('tasks.svc.get_client') as mock_client:
        client = make_client()
        mock_client.return_value = client
        tasks_svc.mark_important('task-1')
        # update should NOT have been called
        assert not client.table.return_value.update.called


def test_unmark_important_removes_prefix():
    task_data = _row(description='important:true|my notes')
    with patch('tasks.svc.get_task', return_value=task_data), \
         patch('tasks.svc.get_client') as mock_client:
        client = make_client()
        mock_client.return_value = client
        tasks_svc.unmark_important('task-1')
        update_call = client.table.return_value.update.call_args
        updated = update_call[0][0]
        assert updated['description'] == 'my notes'
