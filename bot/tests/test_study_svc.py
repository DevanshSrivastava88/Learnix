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


# ---------------------------------------------------------------------------
# bubble_up_completion tests
# ---------------------------------------------------------------------------

def test_bubble_up_completion_marks_parent_when_all_siblings_done():
    """When all siblings are completed, parent gets marked completed too."""
    child = {'id': 'c1', 'goal_id': 'g1', 'parent_id': 'p1', 'status': 'completed'}
    siblings = [{'status': 'completed'}, {'status': 'completed'}]

    with patch('study.svc.get_client') as mock_get:
        client = MagicMock()
        # get_topic('c1') → child
        topic_ex = MagicMock(); topic_ex.data = [child]
        # siblings query for parent_id='p1'
        sib_ex = MagicMock(); sib_ex.data = siblings
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = topic_ex
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = sib_ex
        mock_get.return_value = client

        with patch('study.svc.update_topic_status') as mock_update, \
             patch('study.svc.get_topic', side_effect=[child, None]):
            study_svc.bubble_up_completion('c1')
        mock_update.assert_called_once_with('p1', 'completed')


def test_bubble_up_completion_skips_when_sibling_pending():
    """Parent stays untouched if any sibling is not yet completed."""
    child = {'id': 'c1', 'goal_id': 'g1', 'parent_id': 'p1', 'status': 'completed'}
    siblings = [{'status': 'completed'}, {'status': 'not_started'}]

    with patch('study.svc.get_topic', return_value=child), \
         patch('study.svc.get_client') as mock_get:
        client = MagicMock()
        sib_ex = MagicMock(); sib_ex.data = siblings
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = sib_ex
        mock_get.return_value = client

        with patch('study.svc.update_topic_status') as mock_update:
            study_svc.bubble_up_completion('c1')
        mock_update.assert_not_called()


def test_bubble_up_completion_no_op_when_no_parent():
    """Root topics (no parent_id) cause early return without any update."""
    root_topic = {'id': 'r1', 'goal_id': 'g1', 'parent_id': None, 'status': 'completed'}
    with patch('study.svc.get_topic', return_value=root_topic), \
         patch('study.svc.update_topic_status') as mock_update:
        study_svc.bubble_up_completion('r1')
    mock_update.assert_not_called()


def test_bubble_up_completion_no_op_when_topic_missing():
    """Missing topic (None from DB) returns without crashing."""
    with patch('study.svc.get_topic', return_value=None), \
         patch('study.svc.update_topic_status') as mock_update:
        study_svc.bubble_up_completion('gone')
    mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# get_weak_topics tests
# ---------------------------------------------------------------------------

def test_get_weak_topics_returns_needs_revision():
    """Topics with status=needs_revision are always returned."""
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'needs_revision', 'score': None},
        {'id': 't2', 'title': 'OOP', 'status': 'completed', 'score': '5/5'},
    ]
    with patch('study.svc.list_topics_for_goal', return_value=topics):
        weak = study_svc.get_weak_topics('g1')
    assert len(weak) == 1 and weak[0]['id'] == 't1'


def test_get_weak_topics_returns_low_score_completed():
    """Completed topics scoring below threshold (80% by default) are included."""
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'completed', 'score': '2/5'},   # 40% < 80%
        {'id': 't2', 'title': 'OOP', 'status': 'completed', 'score': '4/5'},    # 80% = threshold
        {'id': 't3', 'title': 'IO', 'status': 'completed', 'score': '5/5'},     # 100% fine
    ]
    with patch('study.svc.list_topics_for_goal', return_value=topics):
        weak = study_svc.get_weak_topics('g1')
    assert len(weak) == 1 and weak[0]['id'] == 't1'


def test_get_weak_topics_skips_not_started():
    """Topics with status=not_started are never flagged as weak."""
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'not_started', 'score': None},
    ]
    with patch('study.svc.list_topics_for_goal', return_value=topics):
        weak = study_svc.get_weak_topics('g1')
    assert weak == []


def test_get_weak_topics_handles_malformed_score():
    """Completed topics with unparseable score strings are not raised — just skipped."""
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'completed', 'score': 'bad/data'},
        {'id': 't2', 'title': 'OOP', 'status': 'completed', 'score': ''},
        {'id': 't3', 'title': 'IO', 'status': 'completed', 'score': None},
    ]
    with patch('study.svc.list_topics_for_goal', return_value=topics):
        # No score info → not flagged (can't determine weakness)
        weak = study_svc.get_weak_topics('g1')
    assert weak == []


def test_get_weak_topics_custom_threshold():
    """Custom ratio_threshold is respected."""
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'completed', 'score': '3/5'},   # 60%
    ]
    with patch('study.svc.list_topics_for_goal', return_value=topics):
        # threshold=0.5 → 60% >= 50%, not weak
        assert study_svc.get_weak_topics('g1', ratio_threshold=0.5) == []
        # threshold=0.7 → 60% < 70%, weak
        assert len(study_svc.get_weak_topics('g1', ratio_threshold=0.7)) == 1


# ---------------------------------------------------------------------------
# bulk_create_topics tests
# ---------------------------------------------------------------------------

def test_bulk_create_topics_creates_in_order():
    """All titles are created in the given order, starting at order_index 0 when empty."""
    with patch('study.svc.list_topics_for_goal', return_value=[]), \
         patch('study.svc.create_topic', side_effect=lambda **kw: {'id': kw['title'], **kw}) as mock_create:
        result = study_svc.bulk_create_topics('g1', ['Vars', 'OOP', 'IO'])
    assert len(result) == 3
    calls = mock_create.call_args_list
    assert calls[0][1]['title'] == 'Vars' and calls[0][1]['order_index'] == 0
    assert calls[1][1]['title'] == 'OOP' and calls[1][1]['order_index'] == 1
    assert calls[2][1]['title'] == 'IO' and calls[2][1]['order_index'] == 2


def test_bulk_create_topics_appends_after_existing():
    """New topics start at max(existing order_index) + 1."""
    existing = [
        {'id': 'e1', 'order_index': 0},
        {'id': 'e2', 'order_index': 1},
    ]
    with patch('study.svc.list_topics_for_goal', return_value=existing), \
         patch('study.svc.create_topic', side_effect=lambda **kw: {'id': kw['title'], **kw}) as mock_create:
        study_svc.bulk_create_topics('g1', ['NewTopic'])
    assert mock_create.call_args[1]['order_index'] == 2  # starts after index 1


def test_bulk_create_topics_empty_list_returns_empty():
    """Empty titles list produces no DB calls and returns []."""
    with patch('study.svc.list_topics_for_goal', return_value=[]), \
         patch('study.svc.create_topic') as mock_create:
        result = study_svc.bulk_create_topics('g1', [])
    assert result == []
    mock_create.assert_not_called()
