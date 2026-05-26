from unittest.mock import MagicMock, patch
import pytest

with patch('supabase_svc.create_client'):
    from study import svc as study_svc

USER_ID = 111

def _mock_execute(rows):
    m = MagicMock()
    m.data = rows
    return m

def make_client():
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = _mock_execute([])
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = _mock_execute([])
    c.table.return_value.insert.return_value.execute.return_value = _mock_execute([{
        'id': 'abc', 'name': 'Test', 'user_id': USER_ID,
        'description': '', 'target_date': '2026-12-01', 'status': 'in_progress',
        'created_at': '2026-01-01T00:00:00'
    }])
    return c

def test_create_goal_returns_dict():
    with patch('study.svc.get_client', return_value=make_client()):
        result = study_svc.create_goal(USER_ID, 'Test Goal', 'desc', '2026-12-01')
        assert result['name'] == 'Test'

def test_list_goals_filters_by_user_id():
    with patch('study.svc.get_client') as mock_get:
        client = MagicMock()
        chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value
        chain.data = []
        mock_get.return_value = client
        result = study_svc.list_goals(USER_ID)
        assert result == []
        client.table.assert_called_with("goals")

def test_count_topics_returns_correct_counts():
    with patch('study.svc.list_topics_for_goal') as mock_list:
        mock_list.return_value = [
            {'status': 'completed'},
            {'status': 'completed'},
            {'status': 'not_started'},
            {'status': 'needs_revision'},
        ]
        result = study_svc.count_topics_for_goal('goal-id')
        assert result['total'] == 4
        assert result['completed'] == 2
        assert result['not_started'] == 1
        assert result['needs_revision'] == 1
