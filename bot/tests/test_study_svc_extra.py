"""
Tests for study/svc.py functions with zero prior coverage:
  get_goal_difficulty, get_topic, update_goal_status, update_topic_status,
  skip_topic, insert_quiz_attempt, get_attempts_for_topic,
  get_next_pending_topic (leaf-selection logic), get_topic_position.

Suite: ~20 new tests, all mocking Supabase — no live credentials needed.
"""
from unittest.mock import MagicMock, patch

import pytest

with patch("supabase_svc.create_client"):
    from study import svc as study_svc


# ── helpers ──────────────────────────────────────────────────────────────────

def _ex(rows=None):
    m = MagicMock()
    m.data = rows if rows is not None else []
    return m


def _simple_client(rows=None):
    """Client whose generic chains (.select/update/insert/delete) all return rows."""
    c = MagicMock()
    ex = _ex(rows)
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = ex
    c.table.return_value.update.return_value.eq.return_value.execute.return_value = ex
    c.table.return_value.insert.return_value.execute.return_value = ex
    c.table.return_value.delete.return_value.eq.return_value.execute.return_value = ex
    return c


# ── get_goal_difficulty ───────────────────────────────────────────────────────

def test_get_goal_difficulty_decodes_from_description():
    goal = {"description": "Learn fast |diff:hard"}
    assert study_svc.get_goal_difficulty(goal) == "hard"


def test_get_goal_difficulty_defaults_to_medium_when_absent():
    assert study_svc.get_goal_difficulty({"description": "plain description"}) == "medium"


def test_get_goal_difficulty_handles_none_description():
    assert study_svc.get_goal_difficulty({"description": None}) == "medium"


# ── get_topic ─────────────────────────────────────────────────────────────────

def test_get_topic_returns_row_when_found():
    topic = {"id": "t1", "title": "Loops", "status": "not_started"}
    with patch("study.svc.get_client", return_value=_simple_client([topic])):
        assert study_svc.get_topic("t1") == topic


def test_get_topic_returns_none_when_not_found():
    with patch("study.svc.get_client", return_value=_simple_client([])):
        assert study_svc.get_topic("missing") is None


# ── update_goal_status ────────────────────────────────────────────────────────

def test_update_goal_status_calls_update_with_correct_status():
    c = _simple_client()
    with patch("study.svc.get_client", return_value=c):
        study_svc.update_goal_status("g1", "completed")
    c.table.return_value.update.assert_called_once_with({"status": "completed"})
    c.table.return_value.update.return_value.eq.assert_called_once_with("id", "g1")


# ── update_topic_status ───────────────────────────────────────────────────────

def test_update_topic_status_sets_status_and_score():
    c = _simple_client()
    with patch("study.svc.get_client", return_value=c):
        study_svc.update_topic_status("t1", "completed", score="4/5")
    data = c.table.return_value.update.call_args[0][0]
    assert data["status"] == "completed"
    assert data["score"] == "4/5"
    assert "completed_at" in data  # terminal status → timestamp added


def test_update_topic_status_omits_score_when_none():
    c = _simple_client()
    with patch("study.svc.get_client", return_value=c):
        study_svc.update_topic_status("t1", "needs_revision")
    data = c.table.return_value.update.call_args[0][0]
    assert "score" not in data
    assert "completed_at" in data  # needs_revision is also terminal


def test_update_topic_status_no_completed_at_for_not_started():
    c = _simple_client()
    with patch("study.svc.get_client", return_value=c):
        study_svc.update_topic_status("t1", "not_started")
    data = c.table.return_value.update.call_args[0][0]
    assert "completed_at" not in data


# ── skip_topic ────────────────────────────────────────────────────────────────

def test_skip_topic_updates_status_to_skipped():
    c = _simple_client()
    with patch("study.svc.get_client", return_value=c):
        study_svc.skip_topic("t99")
    c.table.return_value.update.assert_called_once_with({"status": "skipped"})
    c.table.return_value.update.return_value.eq.assert_called_once_with("id", "t99")


# ── insert_quiz_attempt ───────────────────────────────────────────────────────

def test_insert_quiz_attempt_inserts_correct_fields():
    c = _simple_client()
    with patch("study.svc.get_client", return_value=c):
        study_svc.insert_quiz_attempt("t1", score=4)
    data = c.table.return_value.insert.call_args[0][0]
    assert data["topic_id"] == "t1"
    assert data["score"] == 4
    assert "attempted_at" in data


# ── get_attempts_for_topic ────────────────────────────────────────────────────

def test_get_attempts_for_topic_returns_rows():
    attempts = [{"topic_id": "t1", "score": 3}, {"topic_id": "t1", "score": 5}]
    c = MagicMock()
    (c.table.return_value.select.return_value.eq.return_value
      .order.return_value.execute.return_value.data) = attempts
    with patch("study.svc.get_client", return_value=c):
        assert study_svc.get_attempts_for_topic("t1") == attempts


def test_get_attempts_for_topic_returns_empty_on_none_data():
    c = MagicMock()
    (c.table.return_value.select.return_value.eq.return_value
      .order.return_value.execute.return_value.data) = None
    with patch("study.svc.get_client", return_value=c):
        assert study_svc.get_attempts_for_topic("t1") == []


# ── get_next_pending_topic ────────────────────────────────────────────────────

def _pending_client(topic_rows):
    """Client for get_next_pending_topic's .in_().in_().order() query chain."""
    c = MagicMock()
    ex = _ex(topic_rows)
    (c.table.return_value.select.return_value
      .in_.return_value.in_.return_value.order.return_value.execute.return_value) = ex
    return c


def test_get_next_pending_topic_none_when_no_goals():
    with patch("study.svc.list_goals", return_value=[]):
        assert study_svc.get_next_pending_topic(1) is None


def test_get_next_pending_topic_none_when_no_pending_topics():
    with patch("study.svc.list_goals", return_value=[{"id": "g1"}]), \
         patch("study.svc.get_client", return_value=_pending_client([])):
        assert study_svc.get_next_pending_topic(1) is None


def test_get_next_pending_topic_returns_leaf_not_parent():
    """A topic that is a parent of another pending topic is skipped in favour of its child."""
    parent = {"id": "p1", "goal_id": "g1", "parent_id": None, "order_index": 0}
    child  = {"id": "c1", "goal_id": "g1", "parent_id": "p1", "order_index": 0}
    with patch("study.svc.list_goals", return_value=[{"id": "g1"}]), \
         patch("study.svc.get_client", return_value=_pending_client([parent, child])):
        result = study_svc.get_next_pending_topic(1)
    # p1 is in ids_with_pending_children (because c1.parent_id == "p1") → only c1 is a leaf
    assert result["id"] == "c1"


def test_get_next_pending_topic_returns_first_root_when_all_leaves():
    """Root topics with no children are all leaves; the first by order is returned."""
    t1 = {"id": "t1", "goal_id": "g1", "parent_id": None, "order_index": 0}
    t2 = {"id": "t2", "goal_id": "g1", "parent_id": None, "order_index": 1}
    with patch("study.svc.list_goals", return_value=[{"id": "g1"}]), \
         patch("study.svc.get_client", return_value=_pending_client([t1, t2])):
        result = study_svc.get_next_pending_topic(1)
    assert result["id"] == "t1"


def test_get_next_pending_topic_fallback_to_first_when_no_leaves():
    """If every pending topic is also a parent (edge case), fall back to the first topic."""
    # Both topics reference each other as parent → neither is a leaf
    ta = {"id": "a", "goal_id": "g1", "parent_id": "b", "order_index": 0}
    tb = {"id": "b", "goal_id": "g1", "parent_id": "a", "order_index": 1}
    with patch("study.svc.list_goals", return_value=[{"id": "g1"}]), \
         patch("study.svc.get_client", return_value=_pending_client([ta, tb])):
        result = study_svc.get_next_pending_topic(1)
    assert result == ta  # fallback: topics[0]


# ── get_topic_position ────────────────────────────────────────────────────────

def test_get_topic_position_root_topic():
    """Root topics use .is_('parent_id', 'null') branch; position is 1-based."""
    topic = {"id": "t2", "goal_id": "g1", "parent_id": None, "order_index": 1}
    siblings = [{"id": "t1", "order_index": 0}, {"id": "t2", "order_index": 1}]
    c = MagicMock()
    # Root path: .eq(goal_id).is_(...).order().execute()
    (c.table.return_value.select.return_value.eq.return_value
      .is_.return_value.order.return_value.execute.return_value.data) = siblings
    with patch("study.svc.get_client", return_value=c):
        pos = study_svc.get_topic_position(topic)
    assert pos["position"] == 2
    assert pos["total"] == 2


def test_get_topic_position_child_topic_scoped_to_parent():
    """Child topics use .eq(parent_id) branch; only siblings of the same parent are counted."""
    topic = {"id": "c2", "goal_id": "g1", "parent_id": "p1", "order_index": 1}
    siblings = [{"id": "c1", "order_index": 0}, {"id": "c2", "order_index": 1}]
    c = MagicMock()
    # Child path: .eq(goal_id).eq(parent_id).order().execute()
    (c.table.return_value.select.return_value.eq.return_value
      .eq.return_value.order.return_value.execute.return_value.data) = siblings
    with patch("study.svc.get_client", return_value=c):
        pos = study_svc.get_topic_position(topic)
    assert pos["position"] == 2
    assert pos["total"] == 2
