from unittest.mock import MagicMock, patch
import pytest

with patch('supabase_svc.create_client'):
    import settings_svc

def make_mock_client(rows=None):
    client = MagicMock()
    execute = MagicMock()
    execute.data = rows or []
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = execute
    client.table.return_value.insert.return_value.execute.return_value = execute
    client.table.return_value.upsert.return_value.execute.return_value = execute
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = execute
    return client

def test_get_settings_returns_existing_row():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[{
            'user_id': 123, 'daily_session_time': '09:00',
            'morning_brief_time': '08:00', 'eod_time': '21:00',
            'streak': 3, 'last_study_date': None
        }])
        mock_get.return_value = client
        result = settings_svc.get_settings(123)
        assert result['streak'] == 3
        assert result['daily_session_time'] == '09:00'

def test_get_settings_creates_default_row_if_missing():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[])
        mock_get.return_value = client
        result = settings_svc.get_settings(999)
        assert result['user_id'] == 999
        assert result['daily_session_time'] == '09:00'
        client.table.return_value.insert.assert_called_once()

def test_update_streak_increments_on_consecutive_day():
    from datetime import date, timedelta
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings') as mock_upsert:
        yesterday = date.today() - timedelta(days=1)
        mock_get.return_value = {'streak': 4, 'last_study_date': yesterday.isoformat()}
        result = settings_svc.update_streak(123, date.today())
        assert result == 5

def test_update_streak_resets_on_gap():
    from datetime import date, timedelta
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings'):
        three_days_ago = date.today() - timedelta(days=3)
        mock_get.return_value = {'streak': 10, 'last_study_date': three_days_ago.isoformat()}
        result = settings_svc.update_streak(123, date.today())
        assert result == 1
