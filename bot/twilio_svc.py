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


async def send_voice_reminder(bot, user_id: int, task_title: str) -> bool:
    """
    Send a Telegram voice message with TTS saying the task name.
    Uses gTTS (Google TTS, free) — no phone call needed, plays in Telegram.
    Falls back to Twilio call if TWILIO_ACCOUNT_SID is set.
    """
    # Try gTTS voice note first (free, works in Telegram)
    try:
        import io
        from gtts import gTTS
        text = f"Hey! Time to {task_title}. Don't forget!"
        tts = gTTS(text=text, lang="en")
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        buf.name = "reminder.mp3"
        await bot.send_voice(chat_id=user_id, voice=buf, caption=f"⏰ *{task_title}*")
        logger.info(f"Voice reminder sent to {user_id} for '{task_title}'")
        return True
    except Exception as e:
        logger.error(f"gTTS voice reminder failed for {user_id}: {e}")

    # Fallback: Twilio call (if configured)
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")
    to_number   = get_phone_number(user_id)

    if all([account_sid, auth_token, from_number, to_number]):
        try:
            from twilio.rest import Client
            twiml = f"<Response><Say>Hey! Time to {task_title}. Don't forget!</Say></Response>"
            call = Client(account_sid, auth_token).calls.create(
                to=to_number, from_=from_number, twiml=twiml, timeout=20
            )
            logger.info(f"Twilio fallback call placed: {call.sid}")
            return True
        except Exception as e:
            logger.error(f"Twilio fallback failed: {e}")

    return False


def make_reminder_call(user_id: int, task_title: str) -> bool:
    """Sync wrapper kept for backwards compat — prefer send_voice_reminder."""
    return False
