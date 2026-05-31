"""Tests for study handler helpers (non-async parts)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
import pytest

with patch('supabase_svc.create_client'):
    from study import svc as study_svc

USER_ID = 111


# ---------------------------------------------------------------------------
# _format_topics_list
# ---------------------------------------------------------------------------

def test_format_topics_list_output():
    """_format_topics_list returns correct icons and numbering."""
    with patch('supabase_svc.create_client'):
        from study.handlers import _format_topics_list
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'completed', 'order_index': 0, 'parent_id': None},
        {'id': 't2', 'title': 'OOP', 'status': 'in_progress', 'order_index': 1, 'parent_id': None, 'score': '2/5'},
        {'id': 't3', 'title': 'File I/O', 'status': 'skipped', 'order_index': 2, 'parent_id': None},
        {'id': 't4', 'title': 'Error Handling', 'status': 'not_started', 'order_index': 3, 'parent_id': None},
    ]
    goal = {'id': 'g1', 'name': 'Learn Python', 'description': ''}

    with patch('study.svc.count_topics_for_goal', return_value={'total': 4, 'completed': 1, 'not_started': 2, 'needs_revision': 0}):
        result = _format_topics_list(goal, topics, current_topic_id='t2')

    assert '✅' in result  # completed
    assert '🔄' in result  # in_progress
    assert '⏭' in result  # skipped
    assert '⬜' in result  # not_started
    assert 'Learn Python' in result
    assert '1.' in result
    assert '2.' in result


# ---------------------------------------------------------------------------
# _parse_bullet_list
# ---------------------------------------------------------------------------

def test_parse_bullet_list_numbered():
    with patch('supabase_svc.create_client'):
        import bot
    result = bot._parse_bullet_list("1. Variables\n2. OOP\n3. File I/O")
    assert result == ["Variables", "OOP", "File I/O"]

def test_parse_bullet_list_dashes():
    with patch('supabase_svc.create_client'):
        import bot
    result = bot._parse_bullet_list("- Variables\n- OOP\n- File I/O")
    assert result == ["Variables", "OOP", "File I/O"]

def test_parse_bullet_list_returns_none_for_plain_text():
    with patch('supabase_svc.create_client'):
        import bot
    result = bot._parse_bullet_list("how am I doing today")
    assert result is None

def test_parse_bullet_list_minimum_two_items():
    with patch('supabase_svc.create_client'):
        import bot
    result = bot._parse_bullet_list("1. Just one thing")
    assert result is None  # single item — not a list
