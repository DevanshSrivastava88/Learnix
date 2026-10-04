import os
import sys
from unittest.mock import MagicMock, patch

with patch("supabase_svc.create_client"):
    import twilio_svc


def _make_client(rows=None):
    client = MagicMock()
    execute = MagicMock()
    execute.data = rows if rows is not None else []
    chain = client.table.return_value
    chain.select.return_value.eq.return_value.execute.return_value = execute
    chain.update.return_value.eq.return_value.execute.return_value = execute
    chain.insert.return_value.execute.return_value = execute
    return client


# ---------------------------------------------------------------------------
# is_twilio_enabled
# ---------------------------------------------------------------------------

def test_is_twilio_enabled_true():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[{"twilio_enabled": True}])
        assert twilio_svc.is_twilio_enabled(123) is True


def test_is_twilio_enabled_false_when_flag_off():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[{"twilio_enabled": False}])
        assert twilio_svc.is_twilio_enabled(123) is False


def test_is_twilio_enabled_false_when_no_row():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[])
        assert twilio_svc.is_twilio_enabled(123) is False


def test_is_twilio_enabled_false_when_key_absent():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[{"user_id": 123}])
        assert twilio_svc.is_twilio_enabled(123) is False


# ---------------------------------------------------------------------------
# set_twilio_enabled
# ---------------------------------------------------------------------------

def test_set_twilio_enabled_updates_existing_row():
    with patch("twilio_svc.get_client") as mock_get:
        client = _make_client(rows=[{"user_id": 123}])
        mock_get.return_value = client
        twilio_svc.set_twilio_enabled(123, True)
        client.table.return_value.update.assert_called_once_with({"twilio_enabled": True})


def test_set_twilio_enabled_inserts_new_row_when_absent():
    with patch("twilio_svc.get_client") as mock_get:
        client = _make_client(rows=[])
        mock_get.return_value = client
        twilio_svc.set_twilio_enabled(456, False)
        inserted = client.table.return_value.insert.call_args[0][0]
        assert inserted["twilio_enabled"] is False
        assert inserted["user_id"] == 456
        assert "daily_session_time" in inserted


def test_set_twilio_enabled_off_updates_existing_row():
    with patch("twilio_svc.get_client") as mock_get:
        client = _make_client(rows=[{"user_id": 99}])
        mock_get.return_value = client
        twilio_svc.set_twilio_enabled(99, False)
        client.table.return_value.update.assert_called_once_with({"twilio_enabled": False})


# ---------------------------------------------------------------------------
# get_phone_number / set_phone_number
# ---------------------------------------------------------------------------

def test_get_phone_number_returns_stored_number():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[{"phone_number": "+918004844144"}])
        assert twilio_svc.get_phone_number(123) == "+918004844144"


def test_get_phone_number_returns_none_when_no_row():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[])
        assert twilio_svc.get_phone_number(123) is None


def test_get_phone_number_returns_none_when_key_absent():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[{"user_id": 123}])
        assert twilio_svc.get_phone_number(123) is None


def test_set_phone_number_calls_update_with_correct_args():
    with patch("twilio_svc.get_client") as mock_get:
        client = _make_client()
        mock_get.return_value = client
        twilio_svc.set_phone_number(123, "+918004844144")
        client.table.return_value.update.assert_called_once_with({"phone_number": "+918004844144"})


# ---------------------------------------------------------------------------
# get_all_twilio_users
# ---------------------------------------------------------------------------

def test_get_all_twilio_users_returns_list():
    with patch("twilio_svc.get_client") as mock_get:
        rows = [{"user_id": 1, "phone_number": "+91111"}, {"user_id": 2, "phone_number": "+91222"}]
        mock_get.return_value = _make_client(rows=rows)
        result = twilio_svc.get_all_twilio_users()
        assert len(result) == 2
        assert result[0]["user_id"] == 1


def test_get_all_twilio_users_returns_empty_list_when_none():
    with patch("twilio_svc.get_client") as mock_get:
        mock_get.return_value = _make_client(rows=[])
        result = twilio_svc.get_all_twilio_users()
        assert result == []


# ---------------------------------------------------------------------------
# make_reminder_call
# ---------------------------------------------------------------------------

_TWILIO_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest123",
    "TWILIO_AUTH_TOKEN": "auth_token_test",
    "TWILIO_PHONE_NUMBER": "+15005550006",
}


def _mock_twilio_rest():
    """Return a mock twilio.rest module with a pre-wired Client."""
    mock_call = MagicMock()
    mock_call.sid = "CAtest"
    mock_client = MagicMock()
    mock_client.calls.create.return_value = mock_call
    mock_rest = MagicMock()
    mock_rest.Client.return_value = mock_client
    return mock_rest, mock_client


def test_make_reminder_call_returns_false_when_env_vars_missing():
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in _TWILIO_ENV}
    with patch.dict(os.environ, clean_env, clear=True):
        result = twilio_svc.make_reminder_call(123, "tid", "Walk")
    assert result is False


def test_make_reminder_call_returns_false_when_one_env_var_missing():
    partial_env = {k: v for k, v in _TWILIO_ENV.items() if k != "TWILIO_AUTH_TOKEN"}
    with patch.dict(os.environ, partial_env, clear=False):
        with patch.dict(os.environ, {"TWILIO_AUTH_TOKEN": ""}, clear=False):
            result = twilio_svc.make_reminder_call(123, "tid", "Walk")
    assert result is False


def test_make_reminder_call_returns_false_when_no_phone_number():
    with patch.dict(os.environ, _TWILIO_ENV), \
         patch("twilio_svc.get_phone_number", return_value=None):
        result = twilio_svc.make_reminder_call(123, "tid", "Walk")
    assert result is False


def test_make_reminder_call_success_with_ivr_flow():
    mock_rest, mock_client = _mock_twilio_rest()
    with patch.dict(os.environ, _TWILIO_ENV), \
         patch("twilio_svc.get_phone_number", return_value="+918004844144"), \
         patch.dict(sys.modules, {"twilio": MagicMock(), "twilio.rest": mock_rest}):
        result = twilio_svc.make_reminder_call(
            123, "task-abc", "Cook dinner",
            railway_url="https://app.railway.app"
        )
    assert result is True
    mock_client.calls.create.assert_called_once()
    twiml = mock_client.calls.create.call_args[1]["twiml"]
    assert "task_id=task-abc" in twiml
    assert "user_id=123" in twiml
    assert "Cook dinner" in twiml
    assert "Gather" in twiml


def test_make_reminder_call_success_with_plain_say_fallback():
    mock_rest, mock_client = _mock_twilio_rest()
    with patch.dict(os.environ, _TWILIO_ENV), \
         patch("twilio_svc.get_phone_number", return_value="+918004844144"), \
         patch.dict(sys.modules, {"twilio": MagicMock(), "twilio.rest": mock_rest}):
        result = twilio_svc.make_reminder_call(123, "task-abc", "Drink water")
    assert result is True
    mock_client.calls.create.assert_called_once()
    twiml = mock_client.calls.create.call_args[1]["twiml"]
    assert "Drink water" in twiml
    assert "Gather" not in twiml


def test_make_reminder_call_returns_false_on_exception():
    mock_rest, mock_client = _mock_twilio_rest()
    mock_client.calls.create.side_effect = RuntimeError("network error")
    with patch.dict(os.environ, _TWILIO_ENV), \
         patch("twilio_svc.get_phone_number", return_value="+918004844144"), \
         patch.dict(sys.modules, {"twilio": MagicMock(), "twilio.rest": mock_rest}):
        result = twilio_svc.make_reminder_call(123, "task-abc", "Meditate")
    assert result is False
