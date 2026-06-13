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
# Context engine — pull the user's REAL history so messages reference actual
# tasks, days, and wins instead of generic coach lines. Every field is
# best-effort: any query that fails degrades to a safe default, never raises.
# ---------------------------------------------------------------------------

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _most_avoided_task(user_id: int, skip_rows: list) -> str | None:
    """Title of the task skipped most often in the window, or None."""
    from collections import Counter
    import tasks.svc as _tdb
    counts = Counter(r["task_id"] for r in skip_rows if r.get("task_id"))
    if not counts:
        return None
    top_id, _ = counts.most_common(1)[0]
    try:
        task = _tdb.get_task(top_id)
    except Exception:
        return None
    title = (task or {}).get("title") or None
    # Strip subtask suffix so the name reads naturally.
    if title and " — Step " in title:
        title = title.split(" — Step ")[0]
    return title


def _busiest_weekday(iso_dates: list) -> str | None:
    """Weekday name that appears most across the given list of date objects."""
    from collections import Counter
    if not iso_dates:
        return None
    counts = Counter(d.weekday() for d in iso_dates)
    return _WEEKDAYS[counts.most_common(1)[0][0]]


def _recent_wins(user_id: int, limit: int = 3) -> list:
    """Most recent completed-task titles (habit/study/milestone), newest first.
    Reads activity_log.note directly since the analytics helper drops notes."""
    try:
        res = (
            get_client().table("activity_log")
            .select("note, event_type, event_date")
            .eq("user_id", user_id)
            .in_("event_type", ["habit", "study", "milestone"])
            .order("event_date", desc=True)
            .limit(20)
            .execute()
        )
    except Exception:
        return []
    wins = []
    for row in res.data or []:
        note = (row.get("note") or "").strip()
        if not note or note.startswith("auto_skip:") or note in wins:
            continue
        wins.append(note)
        if len(wins) >= limit:
            break
    return wins


def gather_user_context(user_id: int) -> dict:
    """Best-effort snapshot of the user's real history for message personalization.
    Never raises — each field degrades to a safe default on error."""
    streak = 0
    persona = "default"
    try:
        from settings_svc import get_settings
        s = get_settings(user_id) or {}
        streak = s.get("streak", 0) or 0
        persona = s.get("persona") or "default"
    except Exception:
        pass

    n_active = 0
    try:
        import tasks.svc as _tdb
        n_active = len([t for t in _tdb.list_tasks(user_id)
                        if " — Step " not in (t.get("title") or "")])
    except Exception:
        pass

    skip_rows, done_rows = [], []
    try:
        import analytics_svc
        skip_rows = analytics_svc.get_skips_last_n_days(user_id, 30) or []
        done_rows = analytics_svc.get_done_counts_last_n_days(user_id, 30) or []
    except Exception:
        pass

    skip_days, done_days = [], []
    for r in skip_rows:
        try:
            skip_days.append(datetime.fromisoformat(r["skipped_at"]).astimezone(IST).date())
        except Exception:
            continue
    for r in done_rows:
        try:
            done_days.append(date.fromisoformat(str(r["event_date"])))
        except Exception:
            continue

    try:
        skip_rate = _skip_rate_last_7_days(user_id)
    except Exception:
        skip_rate = 0.0
    try:
        days_since = _days_since_any_activity(user_id)
    except Exception:
        days_since = 999

    return {
        "streak": streak,
        "persona": persona,
        "n_active_habits": n_active,
        "skip_rate_7d": skip_rate,
        "days_since_active": days_since,
        "most_avoided_task": _most_avoided_task(user_id, skip_rows),
        "best_weekday": _busiest_weekday(done_days),
        "worst_weekday": _busiest_weekday(skip_days),
        "recent_wins": _recent_wins(user_id),
    }


def _context_brief(ctx: dict) -> str:
    """Render the context dict into a compact prompt block. Only includes fields
    that carry real signal — empty data produces no line, so the LLM never
    invents specifics it doesn't have."""
    lines = []
    if ctx.get("streak", 0) > 1:
        lines.append(f"- Current streak: {ctx['streak']} days (this is real progress — name it).")
    if ctx.get("most_avoided_task"):
        lines.append(f"- Task they keep avoiding: \"{ctx['most_avoided_task']}\".")
    if ctx.get("best_weekday"):
        lines.append(f"- Their strongest day is {ctx['best_weekday']} (they show up most then).")
    if ctx.get("worst_weekday") and ctx.get("worst_weekday") != ctx.get("best_weekday"):
        lines.append(f"- They skip most on {ctx['worst_weekday']}.")
    wins = ctx.get("recent_wins") or []
    if wins:
        lines.append(f"- Recent wins to reference by name: {', '.join(wins)}.")
    if ctx.get("n_active_habits"):
        lines.append(f"- They are tracking {ctx['n_active_habits']} active habit(s).")
    if not lines:
        return "No history yet — keep it warm and general, do NOT invent specifics."
    return "Real data about this user (use specifics, never invent):\n" + "\n".join(lines)


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


_IDENTITY_RULE = (
    "Frame around identity, not the gap: 'you're someone who shows up', not 'do your task'. "
    "One slip never erases what they built — forgive instantly, then push forward. "
    "Weave in ONE real specific from the data below (a task name, their best day, a recent win) "
    "so it's clearly about THEM. Never invent specifics that aren't given."
)


def generate_motivation_message(trigger_type: str, ctx: dict | None = None) -> str:
    # The poller always passes a gathered ctx; an absent ctx just means no
    # personalization data — degrade to a warm, general message.
    ctx = ctx or {}
    tone = _TONE_GUIDES.get(trigger_type, "Send a brief, warm encouraging message. Under 60 words.")
    prompt = (
        "You are Learnix, a friendly habit coach on Telegram.\n\n"
        f"Situation: {tone}\n\n"
        f"{_IDENTITY_RULE}\n\n"
        f"{_context_brief(ctx or {})}\n\n"
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
        ctx = gather_user_context(user_id)
        msg = generate_motivation_message(trigger_type, ctx)
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
    try:
        ctx = gather_user_context(user_id)
    except Exception:
        ctx = {}
    if persona == "default":
        persona = ctx.get("persona", "default")
    flirt = ("Tone: warm and a little playfully flirty, like a charming friend who believes in them. "
             if persona == "flirty" else "Tone: warm, real, like a close friend. ")
    prompt = (
        "You are Learnix, a habit/study coach on Telegram. The user just said they're "
        f"struggling or failing: \"{text}\".\n\n"
        f"{flirt}"
        "Validate the feeling in 1-2 sentences (no 'just stay positive!', no lecturing). "
        "If the data shows a real win or streak, name it so they remember it still counts. "
        f"{_context_brief(ctx)}\n\n"
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
