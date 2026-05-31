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


# ---------------------------------------------------------------------------
# Difficulty encode/decode tests
# ---------------------------------------------------------------------------

def test_set_and_get_difficulty():
    from study.svc import _set_difficulty, _get_difficulty
    desc = _set_difficulty("My desc", "hard")
    assert "|diff:hard" in desc
    assert _get_difficulty(desc) == "hard"

def test_get_difficulty_defaults_to_medium():
    from study.svc import _get_difficulty
    assert _get_difficulty("plain description") == "medium"
    assert _get_difficulty("") == "medium"
    assert _get_difficulty(None) == "medium"

def test_create_goal_encodes_difficulty():
    with patch('study.svc.get_client') as mock_get:
        client = MagicMock()
        ex = MagicMock()
        ex.data = [{'id': 'g1', 'name': 'Learn Rust', 'description': 'basic|diff:hard',
                    'user_id': USER_ID, 'status': 'in_progress',
                    'target_date': None, 'created_at': '2026-01-01'}]
        client.table.return_value.insert.return_value.execute.return_value = ex
        mock_get.return_value = client
        result = study_svc.create_goal(USER_ID, 'Learn Rust', 'basic', None, difficulty='hard')
        insert_call = client.table.return_value.insert.call_args[0][0]
        assert '|diff:hard' in insert_call['description']


# ---------------------------------------------------------------------------
# fuzzy_match_topic tests
# ---------------------------------------------------------------------------

def test_fuzzy_match_topic_exact():
    from study.svc import fuzzy_match_topic
    topics = [
        {'id': '1', 'title': 'OOP Basics', 'status': 'not_started'},
        {'id': '2', 'title': 'File I/O', 'status': 'not_started'},
        {'id': '3', 'title': 'Error Handling', 'status': 'not_started'},
    ]
    result = fuzzy_match_topic("OOP Basics", topics)
    assert result is not None
    assert result['id'] == '1'

def test_fuzzy_match_topic_partial():
    from study.svc import fuzzy_match_topic
    topics = [
        {'id': '1', 'title': 'OOP Basics', 'status': 'not_started'},
        {'id': '2', 'title': 'File I/O', 'status': 'not_started'},
    ]
    result = fuzzy_match_topic("oop", topics)
    assert result is not None
    assert result['id'] == '1'

def test_fuzzy_match_topic_no_match():
    from study.svc import fuzzy_match_topic
    topics = [{'id': '1', 'title': 'OOP Basics', 'status': 'not_started'}]
    result = fuzzy_match_topic("xyz zyx qrs", topics)
    assert result is None


# ---------------------------------------------------------------------------
# get_study_progress tests
# ---------------------------------------------------------------------------

def test_get_study_progress_returns_dict():
    from study.svc import get_study_progress
    with patch('study.svc.list_goals') as mock_goals, \
         patch('study.svc.list_topics_for_goal') as mock_topics, \
         patch('study.svc.get_next_pending_topic') as mock_next:
        mock_goals.return_value = [{'id': 'g1', 'name': 'Learn Python', 'description': ''}]
        mock_topics.return_value = [
            {'id': 't1', 'title': 'Vars', 'status': 'completed', 'order_index': 0, 'parent_id': None},
            {'id': 't2', 'title': 'OOP', 'status': 'not_started', 'order_index': 1, 'parent_id': None},
        ]
        mock_next.return_value = {'id': 't2', 'title': 'OOP', 'goal_id': 'g1',
                                  'status': 'not_started', 'order_index': 1, 'parent_id': None}
        result = get_study_progress(USER_ID)
        assert result['goal_name'] == 'Learn Python'
        assert result['pct'] == 50
        assert result['position'] == 2
        assert result['total'] == 2
