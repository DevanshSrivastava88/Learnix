from datetime import date
from typing import Optional
from supabase_svc import get_client


def get_settings(user_id: int) -> dict:
    """Return settings for user, creating defaults if first time."""
    sb = get_client()
    res = sb.table("settings").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    row = {
        "user_id": user_id,
        "daily_session_time": "09:00",
        "morning_brief_time": "08:00",
        "eod_time": "21:00",
        "streak": 0,
        "last_study_date": None,
    }
    sb.table("settings").insert(row).execute()
    return row


def upsert_settings(user_id: int, **kwargs) -> dict:
    kwargs["user_id"] = user_id
    res = get_client().table("settings").upsert(kwargs).execute()
    return res.data[0] if res.data else {}


def set_daily_time(user_id: int, time_str: str) -> None:
    upsert_settings(user_id, daily_session_time=time_str)


def set_morning_brief_time(user_id: int, time_str: str) -> None:
    upsert_settings(user_id, morning_brief_time=time_str)


def set_eod_time(user_id: int, time_str: str) -> None:
    upsert_settings(user_id, eod_time=time_str)


def set_persona(user_id: int, persona: str) -> None:
    upsert_settings(user_id, persona=persona)


def get_persona(user_id: int) -> str:
    return get_settings(user_id).get("persona") or "default"


def update_streak(user_id: int, study_date: date) -> int:
    settings = get_settings(user_id)
    last = settings.get("last_study_date")
    current = settings.get("streak", 0) or 0

    if last is None:
        new_streak = 1
    else:
        if isinstance(last, str):
            last = date.fromisoformat(last)
        delta = (study_date - last).days
        if delta == 1:
            new_streak = current + 1
        elif delta == 0:
            new_streak = current
        else:
            new_streak = 1

    upsert_settings(user_id, streak=new_streak, last_study_date=study_date.isoformat())
    return new_streak


def get_all_users() -> list[dict]:
    """Return all settings rows — used by scheduler to fan out to all users."""
    res = get_client().table("settings").select("*").execute()
    return res.data or []
