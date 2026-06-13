"""
motivation_svc.py — Skip pattern detection + motivational message generation.

Triggers (research-backed timing):
  daily_skip_burst  — 3+ skips today → evening nudge (17-22 IST)
  streak_broken     — streak > 0 but last_study_date 2+ days ago → morning (08-09 IST)
  low_weekly_rate   — skip rate > 50% over last 7 days → morning (08-10 IST)
  no_activity       — no activity or skips in 2+ days → any time (09-20 IST)

One motivation message per user per 24 hours max (enforced via motivation_log table).
Tone: identity-based, never guilt-shaming. References peak performance, not current gap.
"""

import logging
from datetime import datetime, timezone, timedelta, date

import pytz
from supabase_svc import get_client
import claude_svc

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

COOLDOWN_HOURS = 24


# ---------------------------------------------------------------------------
# Delivery guard
# ---------------------------------------------------------------------------

def _was_recently_motivated(user_id: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=COOLDOWN_HOURS)).isoformat()
    res = (
        get_client().table("motivation_log")
        .select("id")
        .eq("user_id", user_id)
        .gte("sent_at", cutoff)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def _log_motivation_sent(user_id: int, trigger_type: str) -> None:
    get_client().table("motivation_log").insert({
        "user_id": user_id,
        "trigger_type": trigger_type,
    }).execute()


# ---------------------------------------------------------------------------
# Trigger detectors
# ---------------------------------------------------------------------------

def _count_skips_today(user_id: int) -> int:
    now_ist = datetime.now(IST)
    today_start_utc = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    res = (
        get_client().table("task_skips")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("skipped_at", today_start_utc.isoformat())
        .execute()
    )
    return res.count or 0


def _skip_rate_last_7_days(user_id: int) -> float:
    """Returns skip / (skip + done) over last 7 days. 0.0 if no data."""
    since = (date.today() - timedelta(days=6)).isoformat()
    skips_res = (
        get_client().table("task_skips")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("skipped_at", since + "T00:00:00+00:00")
        .execute()
    )
    done_res = (
        get_client().table("activity_log")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("event_type", "habit")
        .gte("event_date", since)
        .execute()
    )
    skips = skips_res.count or 0
    done = done_res.count or 0
    total = skips + done
    return skips / total if total > 0 else 0.0


def _is_streak_broken(user_id: int) -> bool:
    """True if user had streak > 0 but last_study_date is 2+ days ago."""
    from settings_svc import get_settings
    s = get_settings(user_id)
    streak = s.get("streak", 0) or 0
    last_str = s.get("last_study_date")
    if streak == 0 or not last_str:
        return False
    last = date.fromisoformat(str(last_str))
    return (date.today() - last).days >= 2


def _days_since_any_activity(user_id: int) -> int:
    """Returns how many days since the last activity_log or task skip. 999 if never."""
    activity_res = (
        get_client().table("activity_log")
        .select("event_date")
        .eq("user_id", user_id)
        .order("event_date", desc=True)
        .limit(1)
        .execute()
    )
    skip_res = (
        get_client().table("task_skips")
        .select("skipped_at")
        .eq("user_id", user_id)
        .order("skipped_at", desc=True)
        .limit(1)
        .execute()
    )
    candidates = []
    if activity_res.data:
        candidates.append(date.fromisoformat(str(activity_res.data[0]["event_date"])))
    if skip_res.data:
        candidates.append(
            datetime.fromisoformat(skip_res.data[0]["skipped_at"]).astimezone(IST).date()
        )
    if not candidates:
        return 999
    return (date.today() - max(candidates)).days


# ---------------------------------------------------------------------------
# Trigger evaluation — hour-gated, priority-ordered
# ---------------------------------------------------------------------------

def evaluate_triggers(user_id: int) -> tuple:
    """
    Returns (trigger_type, True) for the first matching trigger, or (None, False).
    Priority: daily_skip_burst > streak_broken > low_weekly_rate > no_activity
    Hour windows are IST, research-backed:
      - daily_skip_burst: evening 17-22 (after day's skips are known)
      - streak_broken:    morning 08-09 (fresh start framing)
      - low_weekly_rate:  morning 08-10 (re-engagement)
      - no_activity:      daytime 09-20 (gentle check-in)
    """
    now_ist = datetime.now(IST)
    h = now_ist.hour

    if 17 <= h <= 22 and _count_skips_today(user_id) >= 3:
        return "daily_skip_burst", True

    if 8 <= h <= 9 and _is_streak_broken(user_id):
        return "streak_broken", True

    if 8 <= h <= 10 and _skip_rate_last_7_days(user_id) > 0.5:
        return "low_weekly_rate", True

    if 9 <= h <= 20 and _days_since_any_activity(user_id) >= 2:
        return "no_activity", True

    return None, False


# ---------------------------------------------------------------------------
# Message generation — identity-based tone, never guilt-shaming
# ---------------------------------------------------------------------------

_TONE_GUIDES = {
    "daily_skip_burst": (
        "The user skipped 3 or more habits today. "
        "Send a warm, non-judgmental evening message. "
        "Acknowledge that today was tough, remind them that one small win still counts, "
        "and that tomorrow is a fresh start. "
        "Reference their effort, not their failure. Under 60 words. 1-2 emojis. Casual tone."
    ),
    "low_weekly_rate": (
        "The user has been skipping more than half their habits this week. "
        "Send a gentle morning re-engagement message. "
        "Ask one simple question to help them reflect on what's getting in the way — "
        "maybe the schedule needs adjusting, not the person. "
        "Offer to help them scale back. Under 60 words. Warm, supportive."
    ),
    "streak_broken": (
        "The user had a study streak but missed the last 2+ days. "
        "Send an encouraging morning message. "
        "Acknowledge the miss without shame — one skip doesn't erase what they built. "
        "Frame it as: 'you're still that person, let's get back'. "
        "Under 60 words. One emoji max. Identity-based tone."
    ),
    "no_activity": (
        "The user hasn't logged any activity in 2+ days. "
        "Send a gentle check-in — are they okay? No pressure, just warmth. "
        "Remind them you're here whenever they're ready. "
        "Very short, casual, no expectations. Under 50 words."
    ),
}


def generate_motivation_message(trigger_type: str) -> str:
    tone = _TONE_GUIDES.get(trigger_type, "Send a brief, warm encouraging message. Under 60 words.")
    prompt = (
        "You are Learnix, a friendly habit coach on Telegram.\n\n"
        f"Situation: {tone}\n\n"
        "Write the message now. No preamble or explanation — just the message."
    )
    return claude_svc._ask(prompt, max_tokens=200)


# ---------------------------------------------------------------------------
# Main entry: check_and_send_for_user
# ---------------------------------------------------------------------------

async def check_and_send_for_user(bot, user_id: int) -> None:
    """Called by motivation_poller for each user. Sends at most one message per 24h."""
    if _was_recently_motivated(user_id):
        return

    trigger_type, should_send = evaluate_triggers(user_id)
    if not should_send or trigger_type is None:
        return

    try:
        msg = generate_motivation_message(trigger_type)
        await bot.send_message(user_id, msg)
        _log_motivation_sent(user_id, trigger_type)
        logger.info(f"Motivation sent to {user_id} — trigger: {trigger_type}")
    except Exception as e:
        logger.error(f"Motivation send failed for {user_id}: {e}")


# ---------------------------------------------------------------------------
# REACTIVE support — in-the-moment, not scheduled. Fires when the user slips
# right now (rough skip streak) or says they're struggling.
# ---------------------------------------------------------------------------

# Phrases that mean "I'm struggling / I messed up" — routed to active support.
import re as _re_m
STRUGGLE_RE = _re_m.compile(
    r"\b(i (?:keep|always) (?:failing|messing up|screwing up|falling behind)"
    r"|i (?:suck|can'?t do this|can'?t do it|give up|gave up|quit|wanna quit)"
    r"|(?:feel like |feeling like )?(?:giving up|quitting)|feel like quitting"
    r"|i'?m (?:a )?(?:failure|hopeless|useless|so behind|falling apart|burnt? out|burned out|overwhelmed)"
    r"|(?:so |really |feeling )?overwhelmed"
    r"|i (?:messed|screwed|fucked) (?:up|it up)|i'?m struggling|struggling (?:with|to keep)"
    r"|this is too (?:hard|much)|it'?s too much"
    r"|i can'?t keep up|can'?t do this anymore|i'?m never gonna|i'?m so bad at)\b",
    _re_m.IGNORECASE,
)


def is_struggle_message(text: str) -> bool:
    return bool(STRUGGLE_RE.search(text or ""))


def comeback_note_on_skip(user_id: int) -> str:
    """A short, warm note to append to a skip confirmation when the user is having
    a rough day (multiple skips today). Empty string otherwise — no nagging."""
    try:
        skips = _count_skips_today(user_id)
    except Exception:
        return ""
    if skips >= 3:
        return "\n\nThird one today — rough day, huh? No guilt. One tiny win still counts. 💛"
    if skips == 2:
        return "\n\nThat's a couple today. Totally fine — tomorrow's a clean slate. 🌱"
    return ""


def generate_struggle_support(user_id: int, text: str, persona: str = "default") -> str:
    """In-the-moment reply when the user says they're failing/struggling.
    Validates the feeling, never toxic-positivity, and offers ONE concrete way to
    lighten the load (pause a habit / push reminders to tomorrow / scale back)."""
    streak = 0
    n_active = 0
    try:
        from settings_svc import get_settings
        import tasks.svc as _tdb
        streak = get_settings(user_id).get("streak", 0) or 0
        n_active = len([t for t in _tdb.list_tasks(user_id) if " — Step " not in t.get("title", "")])
    except Exception:
        pass
    win = f"They have a {streak}-day streak going — remind them that still counts. " if streak > 1 else ""
    flirt = ("Tone: warm and a little playfully flirty, like a charming friend who believes in them. "
             if persona == "flirty" else "Tone: warm, real, like a close friend. ")
    prompt = (
        "You are Learnix, a habit/study coach on Telegram. The user just said they're "
        f"struggling or failing: \"{text}\".\n\n"
        f"{flirt}"
        "Validate the feeling in 1-2 sentences (no 'just stay positive!', no lecturing). "
        f"{win}"
        "Do NOT propose solutions — a separate line handles that. "
        "Never shame. Under 40 words. 1 emoji max. Just the message, no preamble."
    )
    try:
        body = claude_svc._ask(prompt, max_tokens=140)
    except Exception:
        body = "Hey — a rough patch doesn't undo your progress."
    # Always attach a concrete offer (the actionable help is the whole point — never
    # leave the user with only sympathy).
    offer = "\n\nWant me to lighten the load? I can *pause a habit*, *push today's reminders to tomorrow*, or *scale a goal back* — just say which. 💛"
    return body.rstrip() + offer
