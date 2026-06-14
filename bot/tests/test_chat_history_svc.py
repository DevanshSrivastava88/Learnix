from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta
import pytest

with patch('supabase_svc.create_client'):
    import chat_history_svc


def _mock_client(rows=None):
    """Return a mock Supabase client whose select chain returns `rows`."""
    c = MagicMock()
    ex = MagicMock()
    ex.data = rows if rows is not None else []
    # select → eq → order → limit → execute
    (c.table.return_value
      .select.return_value
      .eq.return_value
      .order.return_value
      .limit.return_value
      .execute.return_value) = ex
    # insert → execute
    c.table.return_value.insert.return_value.execute.return_value = ex
    # delete → lt → execute
    c.table.return_value.delete.return_value.lt.return_value.execute.return_value = ex
    return c


# ── load_history ─────────────────────────────────────────────────────────────

def test_load_history_returns_lines_oldest_first():
    rows = [{"line": "C"}, {"line": "B"}, {"line": "A"}]
    with patch('chat_history_svc.get_client', return_value=_mock_client(rows=rows)):
        result = chat_history_svc.load_history(42)
    # reversed from query order (desc) → oldest first
    assert result == ["A", "B", "C"]


def test_load_history_empty_db():
    with patch('chat_history_svc.get_client', return_value=_mock_client(rows=[])):
        result = chat_history_svc.load_history(42)
    assert result == []


def test_load_history_none_data():
    with patch('chat_history_svc.get_client', return_value=_mock_client(rows=None)):
        result = chat_history_svc.load_history(42)
    assert result == []


def test_load_history_returns_empty_on_exception():
    c = MagicMock()
    c.table.side_effect = RuntimeError("DB down")
    with patch('chat_history_svc.get_client', return_value=c):
        result = chat_history_svc.load_history(42)
    assert result == []


def test_load_history_respects_max_lines():
    # MAX_LINES is 12 — verify the limit is passed through
    c = _mock_client(rows=[{"line": "x"}])
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.load_history(1)
    limit_call = c.table.return_value.select.return_value.eq.return_value.order.return_value.limit
    limit_call.assert_called_once_with(chat_history_svc.MAX_LINES)


# ── save_line ─────────────────────────────────────────────────────────────────

def test_save_line_inserts_row():
    c = _mock_client()
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.save_line(7, "hello world")
    c.table.return_value.insert.assert_called_once_with({"user_id": 7, "line": "hello world"})


def test_save_line_truncates_to_500_chars():
    long_line = "x" * 600
    c = _mock_client()
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.save_line(7, long_line)
    inserted = c.table.return_value.insert.call_args[0][0]["line"]
    assert len(inserted) == 500


def test_save_line_swallows_exception():
    c = MagicMock()
    c.table.side_effect = RuntimeError("DB down")
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.save_line(7, "test")  # must not raise


# ── cleanup_old ───────────────────────────────────────────────────────────────

def test_cleanup_old_deletes_rows_older_than_n_days():
    c = _mock_client()
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.cleanup_old(days=7)
    delete_chain = c.table.return_value.delete.return_value.lt
    delete_chain.assert_called_once()
    col, cutoff_iso = delete_chain.call_args[0]
    assert col == "created_at"
    # Cutoff should be roughly 7 days ago
    cutoff = datetime.fromisoformat(cutoff_iso)
    expected = datetime.now(timezone.utc) - timedelta(days=7)
    assert abs((cutoff - expected).total_seconds()) < 5


def test_cleanup_old_default_is_7_days():
    c = _mock_client()
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.cleanup_old()
    delete_chain = c.table.return_value.delete.return_value.lt
    delete_chain.assert_called_once()


def test_cleanup_old_swallows_exception():
    c = MagicMock()
    c.table.side_effect = RuntimeError("DB down")
    with patch('chat_history_svc.get_client', return_value=c):
        chat_history_svc.cleanup_old(days=7)  # must not raise


# ── DbHistory ─────────────────────────────────────────────────────────────────

def test_dbhistory_initialises_with_items():
    h = chat_history_svc.DbHistory(user_id=5, items=["a", "b"])
    assert list(h) == ["a", "b"]
    assert h._user_id == 5


def test_dbhistory_append_saves_to_db():
    c = _mock_client()
    with patch('chat_history_svc.get_client', return_value=c):
        h = chat_history_svc.DbHistory(user_id=5, items=[])
        h.append("new line")
    assert list(h) == ["new line"]
    c.table.return_value.insert.assert_called_once_with({"user_id": 5, "line": "new line"})


def test_dbhistory_append_multiple_lines():
    c = _mock_client()
    with patch('chat_history_svc.get_client', return_value=c):
        h = chat_history_svc.DbHistory(user_id=9, items=["first"])
        h.append("second")
        h.append("third")
    assert list(h) == ["first", "second", "third"]
    assert c.table.return_value.insert.call_count == 2
