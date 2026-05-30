"""
twilio_svc.py — Twilio call reminders per user.

Phase 1: ring user's phone → missed call notification
Phase 2: TTS reads task name
Phase 3: Gemini motivation call
"""

import os
import logging
from supabase_svc import get_client

logger = logging.getLogger(__name__)


def is_twilio_enabled(user_id: int) -> bool:
    res = get_client().table("settings").select("twilio_enabled").eq("user_id", user_id).execute()
    if not res.data:
        return False
    return bool(res.data[0].get("twilio_enabled", False))


def set_twilio_enabled(user_id: int, enabled: bool) -> None:
    sb = get_client()
    existing = sb.table("settings").select("user_id").eq("user_id", user_id).execute()
    if existing.data:
        sb.table("settings").update({"twilio_enabled": enabled}).eq("user_id", user_id).execute()
    else:
        sb.table("settings").insert({
            "user_id": user_id,
            "daily_session_time": "09:00",
            "morning_brief_time": "08:00",
            "eod_time": "21:00",
            "streak": 0,
            "last_study_date": None,
            "twilio_enabled": enabled,
        }).execute()


def set_phone_number(user_id: int, phone: str) -> None:
    get_client().table("settings").update({"phone_number": phone}).eq("user_id", user_id).execute()


def get_phone_number(user_id: int) -> str | None:
    """Return user's phone number from settings, or None if not set."""
    res = get_client().table("settings").select("phone_number").eq("user_id", user_id).execute()
    if not res.data:
        return None
    return res.data[0].get("phone_number")


def get_all_twilio_users() -> list:
    res = (get_client().table("settings")
           .select("user_id, phone_number")
           .eq("twilio_enabled", True)
           .execute())
    return res.data or []


def make_reminder_call(user_id: int, task_title: str) -> bool:
    """
    Phase 1: call user's phone, ring for 20s then hang up → they see a missed call.
    Phase 2 (later): swap twiml to <Say> the task name.
    Returns True if call was placed successfully.
    """
    account_sid  = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token   = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number  = os.environ.get("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        logger.error("Twilio env vars not set — skipping call")
        return False

    to_number = get_phone_number(user_id)
    if not to_number:
        logger.warning(f"No phone number for user {user_id} — skipping call")
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)

        # Phase 1: ring and hang up (user sees missed call)
        # Phase 2: replace twiml with <Say> to speak the task name
        twiml = f"<Response><Say>Hey! Time to {task_title}. Don't forget!</Say><Pause length='2'/></Response>"

        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=twiml,
            timeout=20,  # ring for 20 seconds max
        )
        logger.info(f"Twilio call placed to {to_number} for '{task_title}' — SID: {call.sid}")
        return True
    except Exception as e:
        logger.error(f"Twilio call failed for user {user_id}: {e}")
        return False
