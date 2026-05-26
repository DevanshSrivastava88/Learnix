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
