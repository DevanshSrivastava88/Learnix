"""Tests for the breakdown feature (claude_svc breakdown functions)."""
from unittest.mock import MagicMock, patch
import pytest

# Patch supabase before importing modules that touch it
with patch('supabase_svc.create_client'):
    import claude_svc
    from tasks import svc as tasks_svc
    from study import svc as study_svc


# ---------------------------------------------------------------------------
# claude_svc.breakdown_task
# ---------------------------------------------------------------------------

def test_breakdown_task_returns_list_of_strings():
    steps = ["Warmup stretches", "5-minute jog", "Push-ups 3x15", "Cool down"]
    with patch.object(claude_svc, '_ask_json', return_value=steps):
        result = claude_svc.breakdown_task("Morning workout")
    assert result == steps
    assert all(isinstance(s, str) for s in result)


def test_breakdown_task_filters_empty_strings():
    with patch.object(claude_svc, '_ask_json', return_value=["Step 1", "", "Step 2", "  "]):
        result = claude_svc.breakdown_task("Morning workout")
    assert result == ["Step 1", "Step 2"]


def test_breakdown_task_raises_on_non_list():
    with patch.object(claude_svc, '_ask_json', return_value={"error": "bad"}):
        with pytest.raises(ValueError):
            claude_svc.breakdown_task("Morning workout")


# ---------------------------------------------------------------------------
# claude_svc.breakdown_study_goal
# ---------------------------------------------------------------------------

def test_breakdown_study_goal_returns_list_of_strings():
    topics = ["Variables & Data Types", "Control Flow", "Functions", "Lists & Dicts", "OOP Basics"]
    with patch.object(claude_svc, '_ask_json', return_value=topics):
        result = claude_svc.breakdown_study_goal("Learn Python")
    assert result == topics
    assert all(isinstance(s, str) for s in result)


def test_breakdown_study_goal_filters_empty_strings():
    with patch.object(claude_svc, '_ask_json', return_value=["Topic A", "", "Topic B"]):
        result = claude_svc.breakdown_study_goal("Learn Python")
    assert result == ["Topic A", "Topic B"]


def test_breakdown_study_goal_raises_on_non_list():
    with patch.object(claude_svc, '_ask_json', return_value={"error": "bad"}):
        with pytest.raises(ValueError):
            claude_svc.breakdown_study_goal("Learn Python")


# ---------------------------------------------------------------------------
# claude_svc.extract_breakdown_subject
# ---------------------------------------------------------------------------

def test_extract_breakdown_subject_returns_subject():
    with patch.object(claude_svc, '_ask_json', return_value={"subject": "morning workout"}):
        result = claude_svc.extract_breakdown_subject("break down morning workout")
    assert result == "morning workout"


def test_extract_breakdown_subject_falls_back_to_text():
    with patch.object(claude_svc, '_ask_json', return_value={}):
        result = claude_svc.extract_breakdown_subject("steps for yoga")
    assert result == "steps for yoga"


# ---------------------------------------------------------------------------
# classify_intent recognises breakdown
# ---------------------------------------------------------------------------

def test_classify_intent_breakdown():
    with patch.object(claude_svc, '_ask_json', return_value={"intent": "breakdown"}):
        assert claude_svc.classify_intent("break down morning workout") == "breakdown"


def test_classify_intent_breakdown_learning_path():
    with patch.object(claude_svc, '_ask_json', return_value={"intent": "breakdown"}):
        assert claude_svc.classify_intent("learning path for Python") == "breakdown"


# ---------------------------------------------------------------------------
# tasks_svc.create_task used for step tasks
# ---------------------------------------------------------------------------

def _task_row(**kwargs):
    base = {
        'id': 'task-abc', 'user_id': 1, 'title': 'Morning workout — Step 1: Warmup',
        'task_type': 'habit', 'status': 'active', 'description': '',
        'next_reminder_at': None, 'recurrence_days': 1, 'target_date': None,
        'created_at': '2026-01-01T00:00:00'
    }
    base.update(kwargs)
    return base


def make_tasks_client(row):
    c = MagicMock()
    ex = MagicMock()
    ex.data = [row]
    c.table.return_value.insert.return_value.execute.return_value = ex
    return c


def test_create_step_task_as_habit():
    row = _task_row()
    with patch('tasks.svc.get_client', return_value=make_tasks_client(row)):
        result = tasks_svc.create_task(
            user_id=1,
            title="Morning workout — Step 1: Warmup",
            task_type="habit",
            recurrence_days=1,
        )
    assert result["task_type"] == "habit"
    assert result["recurrence_days"] == 1
    assert "Step 1" in result["title"]


# ---------------------------------------------------------------------------
# study_svc.create_topic used for subtopics
# ---------------------------------------------------------------------------

def make_study_client():
    c = MagicMock()
    ex = MagicMock()
    ex.data = [{
        'id': 'topic-1', 'goal_id': 'goal-1', 'title': 'Variables & Data Types',
        'description': '', 'notes': '', 'parent_id': None,
        'order_index': 0, 'status': 'not_started',
    }]
    c.table.return_value.insert.return_value.execute.return_value = ex
    return c


def test_create_topic_for_breakdown():
    with patch('study.svc.get_client', return_value=make_study_client()):
        result = study_svc.create_topic(
            goal_id="goal-1",
            title="Variables & Data Types",
            order_index=0,
        )
    assert result["title"] == "Variables & Data Types"
    assert result["goal_id"] == "goal-1"
    assert result["order_index"] == 0
