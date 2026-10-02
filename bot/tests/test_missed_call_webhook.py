"""Tests for missed_call_webhook.py — signature helper, Telegram notify, Flask routes."""

import base64
import hashlib
import hmac
import os
from unittest.mock import MagicMock, patch

# Module reads these env vars at import time — set before importing.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_bot_token")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_twilio_auth")

# Pre-import twilio_svc (mocked Supabase) so _notify_all's local `import twilio_svc`
# resolves from sys.modules cache rather than failing on missing credentials.
with patch("supabase_svc.create_client"):
    import twilio_svc  # noqa: F401

import missed_call_webhook  # noqa: E402

_app = missed_call_webhook.app
_app.config["TESTING"] = True


# ---------------------------------------------------------------------------
# _twilio_signature (pure function)
# ---------------------------------------------------------------------------

def test_twilio_signature_matches_manual_hmac():
    auth = "my_secret"
    url = "https://example.com/twilio/missed-call"
    params = {"CallStatus": "no-answer", "From": "+1234567890"}

    s = url
    for key in sorted(params.keys()):
        s += key + params[key]
    expected = base64.b64encode(
        hmac.new(auth.encode(), s.encode(), hashlib.sha1).digest()
    ).decode()

    assert missed_call_webhook._twilio_signature(auth, url, params) == expected


def test_twilio_signature_empty_params():
    auth = "key"
    url = "https://example.com"
    expected = base64.b64encode(
        hmac.new(auth.encode(), url.encode(), hashlib.sha1).digest()
    ).decode()
    assert missed_call_webhook._twilio_signature(auth, url, {}) == expected


# ---------------------------------------------------------------------------
# _send_telegram
# ---------------------------------------------------------------------------

def test_send_telegram_posts_to_correct_url():
    with patch("missed_call_webhook.requests.post") as mock_post:
        missed_call_webhook._send_telegram(12345, "Hello!")
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        payload = mock_post.call_args[1]["json"]
        assert "test_bot_token" in url
        assert payload["chat_id"] == 12345
        assert payload["text"] == "Hello!"


def test_send_telegram_silently_swallows_exception():
    with patch("missed_call_webhook.requests.post", side_effect=Exception("network down")):
        # Must not raise
        missed_call_webhook._send_telegram(12345, "Hello!")


# ---------------------------------------------------------------------------
# _notify_all
# ---------------------------------------------------------------------------

def test_notify_all_sends_to_all_twilio_users():
    users = [{"user_id": 1}, {"user_id": 2}]
    with patch("twilio_svc.get_all_twilio_users", return_value=users), \
         patch("missed_call_webhook._send_telegram") as mock_tg:
        missed_call_webhook._notify_all("Test message")
        assert mock_tg.call_count == 2
        mock_tg.assert_any_call(1, "Test message")
        mock_tg.assert_any_call(2, "Test message")


def test_notify_all_falls_back_to_chat_id_env_when_no_users():
    with patch("twilio_svc.get_all_twilio_users", return_value=[]), \
         patch("missed_call_webhook._send_telegram") as mock_tg, \
         patch.dict("os.environ", {"TELEGRAM_CHAT_ID": "999"}):
        missed_call_webhook._notify_all("Fallback!")
        mock_tg.assert_called_once_with("999", "Fallback!")


def test_notify_all_does_nothing_when_no_users_and_no_fallback():
    env = {k: v for k, v in os.environ.items() if k != "TELEGRAM_CHAT_ID"}
    with patch("twilio_svc.get_all_twilio_users", return_value=[]), \
         patch("missed_call_webhook._send_telegram") as mock_tg, \
         patch.dict("os.environ", env, clear=True):
        missed_call_webhook._notify_all("Should be silent")
        mock_tg.assert_not_called()


# ---------------------------------------------------------------------------
# POST /twilio/missed-call
# ---------------------------------------------------------------------------

def test_missed_call_returns_403_on_invalid_signature():
    with _app.test_client() as client:
        with patch("missed_call_webhook._validate_twilio", return_value=False):
            resp = client.post("/twilio/missed-call", data={"CallStatus": "no-answer", "From": "+1"})
            assert resp.status_code == 403


def test_missed_call_returns_204_for_non_missed_status():
    with _app.test_client() as client:
        with patch("missed_call_webhook._validate_twilio", return_value=True):
            resp = client.post("/twilio/missed-call", data={"CallStatus": "completed", "From": "+1"})
            assert resp.status_code == 204


def test_missed_call_notifies_on_no_answer():
    with _app.test_client() as client:
        with patch("missed_call_webhook._validate_twilio", return_value=True), \
             patch("missed_call_webhook._notify_all") as mock_notify:
            resp = client.post("/twilio/missed-call", data={"CallStatus": "no-answer", "From": "+1234567890"})
            assert resp.status_code == 200
            text = mock_notify.call_args[0][0]
            assert "+1234567890" in text
            assert "no answer" in text.lower()


def test_missed_call_notifies_on_busy():
    with _app.test_client() as client:
        with patch("missed_call_webhook._validate_twilio", return_value=True), \
             patch("missed_call_webhook._notify_all") as mock_notify:
            resp = client.post("/twilio/missed-call", data={"CallStatus": "busy", "From": "+9999"})
            assert resp.status_code == 200
            assert "busy" in mock_notify.call_args[0][0].lower()


def test_missed_call_notifies_on_failed():
    with _app.test_client() as client:
        with patch("missed_call_webhook._validate_twilio", return_value=True), \
             patch("missed_call_webhook._notify_all") as mock_notify:
            resp = client.post("/twilio/missed-call", data={"CallStatus": "failed", "From": "+0000"})
            assert resp.status_code == 200
            assert "failed" in mock_notify.call_args[0][0].lower()


def test_missed_call_returns_xml_response_body():
    with _app.test_client() as client:
        with patch("missed_call_webhook._validate_twilio", return_value=True), \
             patch("missed_call_webhook._notify_all"):
            resp = client.post("/twilio/missed-call", data={"CallStatus": "no-answer", "From": "+1"})
            assert b"Response" in resp.data


# ---------------------------------------------------------------------------
# POST /twilio/call-response
# ---------------------------------------------------------------------------

def test_call_response_missing_both_params_returns_error_xml():
    with _app.test_client() as client:
        resp = client.post("/twilio/call-response", data={"Digits": "1"})
        assert resp.status_code == 200
        assert b"Invalid request" in resp.data


def test_call_response_missing_user_id_returns_error_xml():
    with _app.test_client() as client:
        resp = client.post("/twilio/call-response?task_id=abc", data={"Digits": "1"})
        assert resp.status_code == 200
        assert b"Invalid request" in resp.data


def test_call_response_missing_task_id_returns_error_xml():
    with _app.test_client() as client:
        resp = client.post("/twilio/call-response?user_id=123", data={"Digits": "1"})
        assert resp.status_code == 200
        assert b"Invalid request" in resp.data


def test_call_response_non_numeric_user_id_returns_error_xml():
    with _app.test_client() as client:
        resp = client.post(
            "/twilio/call-response?task_id=abc&user_id=notanumber",
            data={"Digits": "1"},
        )
        assert resp.status_code == 200
        assert b"Invalid user" in resp.data


def test_call_response_digit_1_marks_done_and_notifies():
    with _app.test_client() as client:
        with patch("missed_call_webhook._get_task_title", return_value="Morning run"), \
             patch("missed_call_webhook._mark_task_done_supabase") as mock_done, \
             patch("missed_call_webhook._send_telegram") as mock_tg:
            resp = client.post(
                "/twilio/call-response?task_id=abc&user_id=123",
                data={"Digits": "1"},
            )
            assert resp.status_code == 200
            mock_done.assert_called_once_with("abc")
            mock_tg.assert_called_once_with(
                123,
                "✅ Great! Marked <b>Morning run</b> as done via phone call. Keep it up!",
            )
            assert b"done" in resp.data.lower()


def test_call_response_digit_2_skips_and_notifies():
    with _app.test_client() as client:
        with patch("missed_call_webhook._get_task_title", return_value="Reading"), \
             patch("missed_call_webhook._skip_task_supabase") as mock_skip, \
             patch("missed_call_webhook._send_telegram") as mock_tg:
            resp = client.post(
                "/twilio/call-response?task_id=xyz&user_id=456",
                data={"Digits": "2"},
            )
            assert resp.status_code == 200
            mock_skip.assert_called_once_with("xyz", 456)
            mock_tg.assert_called_once_with(456, "⏭ Skipped <b>Reading</b> for now.")
            assert b"skipped" in resp.data.lower()


def test_call_response_unknown_digit_sends_no_telegram_and_returns_reminder():
    with _app.test_client() as client:
        with patch("missed_call_webhook._get_task_title", return_value="Workout"), \
             patch("missed_call_webhook._send_telegram") as mock_tg:
            resp = client.post(
                "/twilio/call-response?task_id=xyz&user_id=123",
                data={"Digits": "9"},
            )
            assert resp.status_code == 200
            mock_tg.assert_not_called()
            assert b"remind" in resp.data.lower()


def test_call_response_falls_back_to_your_task_when_title_empty():
    with _app.test_client() as client:
        with patch("missed_call_webhook._get_task_title", return_value=""), \
             patch("missed_call_webhook._mark_task_done_supabase"), \
             patch("missed_call_webhook._send_telegram") as mock_tg:
            client.post("/twilio/call-response?task_id=abc&user_id=123", data={"Digits": "1"})
            assert "your task" in mock_tg.call_args[0][1]


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    with _app.test_client() as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
