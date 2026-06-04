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
