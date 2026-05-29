"""
twilio_svc.py — Twilio missed-call notification settings per user.
"""

from supabase_svc import get_client


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


def get_all_twilio_users() -> list:
    res = get_client().table("settings").select("user_id").eq("twilio_enabled", True).execute()
    return res.data or []
