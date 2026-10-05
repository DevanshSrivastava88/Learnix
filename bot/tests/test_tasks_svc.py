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
    scheduled = _row(recurrence_days=2,
                     next_reminder_at=datetime.now(timezone.utc).isoformat())
    with patch.object(tasks_svc, 'get_task', return_value=scheduled), \
         patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.mark_done('task-1')
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        assert 'next_reminder_at' in kwargs

def test_mark_done_keeps_reminderless_habit_reminderless():
    # No time = no reminder — done must not invent a next reminder
    with patch.object(tasks_svc, 'get_task', return_value=_row(recurrence_days=2)), \
         patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.mark_done('task-1')
        mock_update.assert_not_called()

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
    with patch.object(tasks_svc, 'get_task', return_value=task_data), \
         patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.mark_important('task-1')
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        assert kwargs.get('description') == 'important:true|existing detail'


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
    with patch.object(tasks_svc, 'get_task', return_value=task_data), \
         patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.unmark_important('task-1')
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        assert kwargs.get('description') == 'my notes'


# ---------------------------------------------------------------------------
# get_reminder_count / increment_reminder_count / reset_reminder_count
# ---------------------------------------------------------------------------

def test_get_reminder_count_returns_zero_when_absent():
    assert tasks_svc.get_reminder_count(_row(description='')) == 0


def test_get_reminder_count_returns_zero_when_none_description():
    assert tasks_svc.get_reminder_count(_row(description=None)) == 0


def test_get_reminder_count_extracts_value():
    assert tasks_svc.get_reminder_count(_row(description='reminded:3')) == 3


def test_get_reminder_count_extracts_value_from_compound_description():
    assert tasks_svc.get_reminder_count(_row(description='important:true|reminded:5')) == 5


def test_increment_reminder_count_from_zero_creates_counter():
    task = _row(description='')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        result = tasks_svc.increment_reminder_count('task-1', task)
    assert result == 1
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == 'reminded:1'


def test_increment_reminder_count_increments_existing():
    task = _row(description='reminded:2')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        result = tasks_svc.increment_reminder_count('task-1', task)
    assert result == 3
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == 'reminded:3'


def test_increment_reminder_count_preserves_other_description_fields():
    task = _row(description='important:true|reminded:1')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.increment_reminder_count('task-1', task)
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == 'important:true|reminded:2'


def test_increment_reminder_count_appends_to_existing_description():
    task = _row(description='important:true')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        result = tasks_svc.increment_reminder_count('task-1', task)
    assert result == 1
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == 'important:true|reminded:1'


def test_reset_reminder_count_removes_counter():
    task = _row(description='reminded:5')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.reset_reminder_count('task-1', task)
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == ''


def test_reset_reminder_count_preserves_other_fields():
    task = _row(description='important:true|reminded:3')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.reset_reminder_count('task-1', task)
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == 'important:true'


def test_reset_reminder_count_noop_when_no_counter():
    task = _row(description='important:true')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.reset_reminder_count('task-1', task)
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == 'important:true'


def test_reset_reminder_count_handles_empty_description():
    task = _row(description='')
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.reset_reminder_count('task-1', task)
    _, kwargs = mock_update.call_args
    assert kwargs.get('description') == ''


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

def test_list_tasks_returns_active_tasks():
    rows = [_row(title='Task A'), _row(title='Task B', id='task-2')]
    c = MagicMock()
    ex = MagicMock(); ex.data = rows
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.list_tasks(USER_ID)
    assert len(result) == 2
    assert result[0]['title'] == 'Task A'


def test_list_tasks_returns_empty_when_none():
    c = MagicMock()
    ex = MagicMock(); ex.data = None
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.list_tasks(USER_ID)
    assert result == []


def test_list_tasks_passes_status_filter():
    c = MagicMock()
    ex = MagicMock(); ex.data = []
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        tasks_svc.list_tasks(USER_ID, status='paused')
    c.table.return_value.select.return_value.eq.return_value.eq.assert_called_once_with('status', 'paused')


# ---------------------------------------------------------------------------
# get_task
# ---------------------------------------------------------------------------

def test_get_task_returns_task_when_found():
    row = _row()
    c = MagicMock()
    ex = MagicMock(); ex.data = [row]
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.get_task('task-1')
    assert result == row


def test_get_task_returns_none_when_not_found():
    c = MagicMock()
    ex = MagicMock(); ex.data = []
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.get_task('nonexistent')
    assert result is None


# ---------------------------------------------------------------------------
# delete_task
# ---------------------------------------------------------------------------

def test_delete_task_calls_delete_with_correct_id():
    c = MagicMock()
    c.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
    with patch('tasks.svc.get_client', return_value=c):
        tasks_svc.delete_task('task-1')
    c.table.return_value.delete.return_value.eq.assert_called_once_with('id', 'task-1')


# ---------------------------------------------------------------------------
# delete_subtasks
# ---------------------------------------------------------------------------

def test_delete_subtasks_removes_step_rows():
    step1 = _row(title='Exercise — Step 1: Warmup', id='task-2')
    step2 = _row(title='Exercise — Step 2: Cooldown', id='task-3')
    other = _row(title='Meditation', id='task-4')
    with patch.object(tasks_svc, 'list_tasks') as mock_list, \
         patch.object(tasks_svc, 'delete_task') as mock_delete:
        mock_list.side_effect = [[step1, step2, other], []]
        count = tasks_svc.delete_subtasks(USER_ID, 'Exercise')
    assert count == 2
    deleted_ids = {c[0][0] for c in mock_delete.call_args_list}
    assert deleted_ids == {'task-2', 'task-3'}


def test_delete_subtasks_returns_zero_when_no_steps():
    unrelated = _row(title='Meditation')
    with patch.object(tasks_svc, 'list_tasks') as mock_list, \
         patch.object(tasks_svc, 'delete_task') as mock_delete:
        mock_list.side_effect = [[unrelated], []]
        count = tasks_svc.delete_subtasks(USER_ID, 'Exercise')
    assert count == 0
    mock_delete.assert_not_called()


def test_delete_subtasks_checks_both_active_and_paused():
    step_active = _row(title='Run — Step 1: Sprint', id='task-2')
    step_paused = _row(title='Run — Step 2: Cooldown', id='task-3', status='paused')
    with patch.object(tasks_svc, 'list_tasks') as mock_list, \
         patch.object(tasks_svc, 'delete_task'):
        mock_list.side_effect = [[step_active], [step_paused]]
        count = tasks_svc.delete_subtasks(USER_ID, 'Run')
    assert count == 2
    assert mock_list.call_count == 2


# ---------------------------------------------------------------------------
# create_milestone
# ---------------------------------------------------------------------------

def test_create_milestone_inserts_row():
    m_row = {'id': 'm-1', 'task_id': 'task-1', 'title': 'Step 1', 'done': False, 'order_index': 0}
    c = MagicMock()
    ex = MagicMock(); ex.data = [m_row]
    c.table.return_value.insert.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.create_milestone('task-1', 'Step 1', order_index=0)
    assert result['title'] == 'Step 1'
    c.table.return_value.insert.assert_called_once_with({
        'task_id': 'task-1', 'title': 'Step 1', 'done': False, 'order_index': 0
    })


# ---------------------------------------------------------------------------
# list_milestones
# ---------------------------------------------------------------------------

def test_list_milestones_returns_items():
    items = [
        {'id': 'm-1', 'title': 'A', 'done': False, 'order_index': 0},
        {'id': 'm-2', 'title': 'B', 'done': True,  'order_index': 1},
    ]
    c = MagicMock()
    ex = MagicMock(); ex.data = items
    c.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.list_milestones('task-1')
    assert result == items


def test_list_milestones_returns_empty_when_none():
    c = MagicMock()
    ex = MagicMock(); ex.data = None
    c.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.list_milestones('task-1')
    assert result == []


# ---------------------------------------------------------------------------
# count_milestones
# ---------------------------------------------------------------------------

def test_count_milestones_counts_done_and_total():
    items = [{'done': True}, {'done': False}, {'done': True}]
    with patch.object(tasks_svc, 'list_milestones', return_value=items):
        result = tasks_svc.count_milestones('task-1')
    assert result == {'total': 3, 'done': 2}


def test_count_milestones_empty():
    with patch.object(tasks_svc, 'list_milestones', return_value=[]):
        result = tasks_svc.count_milestones('task-1')
    assert result == {'total': 0, 'done': 0}


# ---------------------------------------------------------------------------
# toggle_milestone
# ---------------------------------------------------------------------------

def test_toggle_milestone_marks_done():
    c = MagicMock()
    c.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    with patch('tasks.svc.get_client', return_value=c):
        tasks_svc.toggle_milestone('m-1', True)
    c.table.return_value.update.assert_called_once_with({'done': True})
    c.table.return_value.update.return_value.eq.assert_called_once_with('id', 'm-1')


def test_toggle_milestone_marks_undone():
    c = MagicMock()
    c.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    with patch('tasks.svc.get_client', return_value=c):
        tasks_svc.toggle_milestone('m-1', False)
    c.table.return_value.update.assert_called_once_with({'done': False})


# ---------------------------------------------------------------------------
# log_skip
# ---------------------------------------------------------------------------

def test_log_skip_inserts_row_with_default_note():
    skip_row = {'id': 'skip-1', 'user_id': USER_ID, 'task_id': 'task-1', 'note': 'outright'}
    c = MagicMock()
    ex = MagicMock(); ex.data = [skip_row]
    c.table.return_value.insert.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        result = tasks_svc.log_skip(USER_ID, 'task-1')
    assert result == skip_row
    c.table.return_value.insert.assert_called_once_with({
        'user_id': USER_ID, 'task_id': 'task-1', 'note': 'outright'
    })


def test_log_skip_uses_custom_note():
    c = MagicMock()
    ex = MagicMock(); ex.data = [{}]
    c.table.return_value.insert.return_value.execute.return_value = ex
    with patch('tasks.svc.get_client', return_value=c):
        tasks_svc.log_skip(USER_ID, 'task-1', note='rescheduled')
    inserted = c.table.return_value.insert.call_args[0][0]
    assert inserted['note'] == 'rescheduled'


# ---------------------------------------------------------------------------
# reschedule_task
# ---------------------------------------------------------------------------

def test_reschedule_task_updates_next_reminder_at():
    new_time = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.reschedule_task('task-1', new_time)
    mock_update.assert_called_once_with('task-1', next_reminder_at=new_time.isoformat())


# ---------------------------------------------------------------------------
# set_custom_time
# ---------------------------------------------------------------------------

def test_set_custom_time_sets_time_and_custom_flag():
    new_time = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)
    with patch.object(tasks_svc, 'update_task') as mock_update:
        tasks_svc.set_custom_time('task-1', new_time)
    mock_update.assert_called_once_with(
        'task-1',
        next_reminder_at=new_time.isoformat(),
        has_custom_time=True,
    )
