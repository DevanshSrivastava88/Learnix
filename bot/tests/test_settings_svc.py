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


def test_update_streak_starts_at_1_when_no_last_date():
    from datetime import date
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings') as mock_upsert:
        mock_get.return_value = {'streak': 0, 'last_study_date': None}
        result = settings_svc.update_streak(1, date.today())
    assert result == 1


def test_update_streak_same_day_keeps_streak():
    from datetime import date
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings') as mock_upsert:
        today = date.today()
        mock_get.return_value = {'streak': 7, 'last_study_date': today.isoformat()}
        result = settings_svc.update_streak(1, today)
    assert result == 7


def test_update_streak_accepts_date_object_as_last_study_date():
    from datetime import date, timedelta
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings') as mock_upsert:
        yesterday = date.today() - timedelta(days=1)
        mock_get.return_value = {'streak': 3, 'last_study_date': yesterday}  # date, not str
        result = settings_svc.update_streak(1, date.today())
    assert result == 4


def test_update_streak_upserts_new_streak_and_date():
    from datetime import date, timedelta
    today = date.today()
    yesterday = today - timedelta(days=1)
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings') as mock_upsert:
        mock_get.return_value = {'streak': 2, 'last_study_date': yesterday.isoformat()}
        settings_svc.update_streak(42, today)
    mock_upsert.assert_called_once_with(42, streak=3, last_study_date=today.isoformat())


# ── upsert_settings ───────────────────────────────────────────────────────────

def test_upsert_settings_returns_first_row():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[{'user_id': 5, 'streak': 2}])
        mock_get.return_value = client
        result = settings_svc.upsert_settings(5, streak=2)
    assert result == {'user_id': 5, 'streak': 2}


def test_upsert_settings_returns_empty_dict_when_no_data():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[])
        mock_get.return_value = client
        result = settings_svc.upsert_settings(5, streak=0)
    assert result == {}


def test_upsert_settings_injects_user_id():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[])
        mock_get.return_value = client
        settings_svc.upsert_settings(99, daily_session_time='10:00')
    upsert_call = client.table.return_value.upsert.call_args[0][0]
    assert upsert_call['user_id'] == 99
    assert upsert_call['daily_session_time'] == '10:00'


# ── set_* convenience wrappers ────────────────────────────────────────────────

def test_set_daily_time_calls_upsert_with_correct_key():
    with patch('settings_svc.upsert_settings') as mock_upsert:
        settings_svc.set_daily_time(1, '07:30')
    mock_upsert.assert_called_once_with(1, daily_session_time='07:30')


def test_set_morning_brief_time_calls_upsert_with_correct_key():
    with patch('settings_svc.upsert_settings') as mock_upsert:
        settings_svc.set_morning_brief_time(2, '06:00')
    mock_upsert.assert_called_once_with(2, morning_brief_time='06:00')


def test_set_eod_time_calls_upsert_with_correct_key():
    with patch('settings_svc.upsert_settings') as mock_upsert:
        settings_svc.set_eod_time(3, '22:30')
    mock_upsert.assert_called_once_with(3, eod_time='22:30')


def test_set_persona_calls_upsert_with_correct_key():
    with patch('settings_svc.upsert_settings') as mock_upsert:
        settings_svc.set_persona(4, 'flirty')
    mock_upsert.assert_called_once_with(4, persona='flirty')


# ── get_persona ───────────────────────────────────────────────────────────────

def test_get_persona_returns_stored_persona():
    with patch('settings_svc.get_settings', return_value={'persona': 'flirty'}):
        assert settings_svc.get_persona(1) == 'flirty'


def test_get_persona_returns_default_when_none():
    with patch('settings_svc.get_settings', return_value={'persona': None}):
        assert settings_svc.get_persona(1) == 'default'


def test_get_persona_returns_default_when_key_missing():
    with patch('settings_svc.get_settings', return_value={}):
        assert settings_svc.get_persona(1) == 'default'


# ── get_all_users ─────────────────────────────────────────────────────────────

def test_get_all_users_returns_rows():
    rows = [{'user_id': 1}, {'user_id': 2}]
    with patch('settings_svc.get_client') as mock_get:
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = rows
        mock_get.return_value = client
        result = settings_svc.get_all_users()
    assert result == rows


def test_get_all_users_returns_empty_list_when_none():
    with patch('settings_svc.get_client') as mock_get:
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = None
        mock_get.return_value = client
        result = settings_svc.get_all_users()
    assert result == []
