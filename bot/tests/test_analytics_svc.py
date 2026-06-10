from unittest.mock import MagicMock, patch
from datetime import date, timedelta
import pytest

with patch('supabase_svc.create_client'):
    import analytics_svc

def make_client(rows=None):
    c = MagicMock()
    ex = MagicMock(); ex.data = rows or []
    c.table.return_value.insert.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = ex
    return c

def test_log_activity_inserts_row():
    with patch('analytics_svc.get_client', return_value=make_client()):
        analytics_svc.log_activity(123, 'study', note='Neural Networks')
        # No exception = pass

def test_get_activity_returns_data():
    rows = [
        {'event_type': 'study', 'event_date': date.today().isoformat()},
        {'event_type': 'habit', 'event_date': date.today().isoformat()},
    ]
    with patch('analytics_svc.get_client', return_value=make_client(rows=rows)):
        result = analytics_svc.get_activity_last_n_days(123, 30)
        assert len(result) == 2
        assert result[0]['event_type'] == 'study'

def test_build_graph_returns_bytes_buffer():
    with patch('analytics_svc.get_activity_last_n_days', return_value=[]):
        buf = analytics_svc.build_graph(123, days=7)
        assert buf.read(4) == b'\x89PNG'


# ── get_skips_last_n_days ────────────────────────────────────────────────────

def test_get_skips_last_n_days_returns_data():
    today = date.today().isoformat()
    rows = [
        {'task_id': 1, 'skipped_at': today + 'T10:00:00+00:00', 'note': ''},
        {'task_id': 2, 'skipped_at': today + 'T12:00:00+00:00', 'note': 'busy'},
    ]
    with patch('analytics_svc.get_client', return_value=make_client(rows=rows)):
        result = analytics_svc.get_skips_last_n_days(123, 30)
        assert len(result) == 2
        assert result[0]['task_id'] == 1

def test_get_skips_last_n_days_returns_empty_when_none():
    c = MagicMock()
    ex = MagicMock(); ex.data = None
    c.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = ex
    with patch('analytics_svc.get_client', return_value=c):
        result = analytics_svc.get_skips_last_n_days(123, 30)
        assert result == []


# ── get_done_counts_last_n_days ──────────────────────────────────────────────

def test_get_done_counts_last_n_days_returns_data():
    today = date.today().isoformat()
    rows = [{'event_date': today}, {'event_date': today}]
    c = MagicMock()
    ex = MagicMock(); ex.data = rows
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = ex
    with patch('analytics_svc.get_client', return_value=c):
        result = analytics_svc.get_done_counts_last_n_days(123, 30)
        assert len(result) == 2

def test_get_done_counts_last_n_days_returns_empty_when_none():
    c = MagicMock()
    ex = MagicMock(); ex.data = None
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = ex
    with patch('analytics_svc.get_client', return_value=c):
        result = analytics_svc.get_done_counts_last_n_days(123, 30)
        assert result == []


# ── build_skip_graph ─────────────────────────────────────────────────────────

def test_build_skip_graph_returns_png_no_data():
    with patch('analytics_svc.get_skips_last_n_days', return_value=[]), \
         patch('analytics_svc.get_done_counts_last_n_days', return_value=[]):
        buf = analytics_svc.build_skip_graph(123, days=7)
        assert buf.read(4) == b'\x89PNG'

def test_build_skip_graph_returns_png_with_skip_and_done_data():
    today = date.today().isoformat()
    skip_rows = [
        {'task_id': 1, 'skipped_at': today + 'T10:00:00+00:00', 'note': ''},
        {'task_id': 1, 'skipped_at': today + 'T14:00:00+00:00', 'note': ''},
    ]
    done_rows = [{'event_date': today}]
    with patch('analytics_svc.get_skips_last_n_days', return_value=skip_rows), \
         patch('analytics_svc.get_done_counts_last_n_days', return_value=done_rows), \
         patch('tasks.svc.get_task', return_value={'title': 'Morning workout'}):
        buf = analytics_svc.build_skip_graph(123, days=7)
        assert buf.read(4) == b'\x89PNG'

def test_build_skip_graph_handles_none_task_lookup():
    today = date.today().isoformat()
    skip_rows = [{'task_id': 99, 'skipped_at': today + 'T10:00:00+00:00', 'note': ''}]
    with patch('analytics_svc.get_skips_last_n_days', return_value=skip_rows), \
         patch('analytics_svc.get_done_counts_last_n_days', return_value=[]), \
         patch('tasks.svc.get_task', return_value=None):
        buf = analytics_svc.build_skip_graph(123, days=7)
        assert buf.read(4) == b'\x89PNG'
