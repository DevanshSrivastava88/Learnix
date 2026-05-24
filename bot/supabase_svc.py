"""
supabase_svc.py — All Supabase DB operations for Learnix bot.
"""

import os
from datetime import date, datetime, timezone
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_settings() -> dict:
    """Return the single settings row (id=1), creating it if missing."""
    sb = get_client()
    res = sb.table("settings").select("*").eq("id", 1).execute()
    if res.data:
        return res.data[0]
    # create default row
    row = {
        "id": 1,
        "daily_session_time": "09:00",
        "telegram_user_id": None,
        "streak": 0,
        "last_study_date": None,
    }
    sb.table("settings").insert(row).execute()
    return row


def upsert_settings(**kwargs) -> dict:
    """Patch the settings row with provided kwargs."""
    sb = get_client()
    kwargs["id"] = 1
    res = sb.table("settings").upsert(kwargs).execute()
    return res.data[0] if res.data else {}


def set_daily_time(time_str: str) -> None:
    """Set daily_session_time (HH:MM format)."""
    upsert_settings(daily_session_time=time_str)


def set_telegram_user_id(uid: int) -> None:
    upsert_settings(telegram_user_id=uid)


def update_streak(study_date: date) -> int:
    """Increment streak if consecutive day, reset otherwise. Returns new streak."""
    settings = get_settings()
    last = settings.get("last_study_date")
    current_streak = settings.get("streak", 0) or 0

    if last is None:
        new_streak = 1
    else:
        if isinstance(last, str):
            last = date.fromisoformat(last)
        delta = (study_date - last).days
        if delta == 1:
            new_streak = current_streak + 1
        elif delta == 0:
            new_streak = current_streak  # same day, no change
        else:
            new_streak = 1  # streak broken

    upsert_settings(streak=new_streak, last_study_date=study_date.isoformat())
    return new_streak


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def create_goal(name: str, description: str, target_date: str) -> dict:
    """Insert a goal. target_date: YYYY-MM-DD string."""
    sb = get_client()
    res = sb.table("goals").insert({
        "name": name,
        "description": description,
        "target_date": target_date,
        "status": "in_progress",
    }).execute()
    return res.data[0]


def list_goals(status: str = "in_progress") -> list[dict]:
    sb = get_client()
    res = sb.table("goals").select("*").eq("status", status).order("created_at").execute()
    return res.data or []


def get_goal(goal_id: str) -> Optional[dict]:
    sb = get_client()
    res = sb.table("goals").select("*").eq("id", goal_id).execute()
    return res.data[0] if res.data else None


def update_goal_status(goal_id: str, status: str) -> None:
    sb = get_client()
    sb.table("goals").update({"status": status}).eq("id", goal_id).execute()


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def create_topic(goal_id: str, title: str, description: str = "",
                 notes: str = "", parent_id: Optional[str] = None,
                 order_index: int = 0) -> dict:
    sb = get_client()
    row = {
        "goal_id": goal_id,
        "title": title,
        "description": description,
        "notes": notes,
        "parent_id": parent_id,
        "order_index": order_index,
        "status": "not_started",
    }
    res = sb.table("topics").insert(row).execute()
    return res.data[0]


def list_topics_for_goal(goal_id: str) -> list[dict]:
    """Return all topics (flat) for a goal, ordered by order_index."""
    sb = get_client()
    res = (sb.table("topics")
           .select("*")
           .eq("goal_id", goal_id)
           .order("order_index")
           .execute())
    return res.data or []


def get_topic(topic_id: str) -> Optional[dict]:
    sb = get_client()
    res = sb.table("topics").select("*").eq("id", topic_id).execute()
    return res.data[0] if res.data else None


def get_next_pending_topic() -> Optional[dict]:
    """
    Find the next topic to study: not_started or needs_revision,
    ordered across all in-progress goals by goal created_at, then topic order_index.
    Prefers leaf nodes (no children that are not_started).
    """
    sb = get_client()
    # Get all in-progress goal ids
    goals = list_goals("in_progress")
    if not goals:
        return None

    goal_ids = [g["id"] for g in goals]

    # Get all pending topics for these goals
    res = (sb.table("topics")
           .select("*")
           .in_("goal_id", goal_ids)
           .in_("status", ["not_started", "needs_revision"])
           .order("order_index")
           .execute())
    topics = res.data or []
    if not topics:
        return None

    # Prefer topics that have no pending children (leaf work)
    topic_ids_with_pending_children = set()
    for t in topics:
        if t.get("parent_id"):
            topic_ids_with_pending_children.add(t["parent_id"])

    leaves = [t for t in topics if t["id"] not in topic_ids_with_pending_children]
    if leaves:
        return leaves[0]
    return topics[0]


def update_topic_status(topic_id: str, status: str, score: Optional[str] = None) -> None:
    sb = get_client()
    update = {"status": status}
    if score is not None:
        update["score"] = score
    if status in ("completed", "needs_revision"):
        update["completed_at"] = datetime.now(timezone.utc).isoformat()
    sb.table("topics").update(update).eq("id", topic_id).execute()


def bubble_up_completion(topic_id: str) -> None:
    """
    After marking a topic complete, check if all siblings under the same parent
    are also complete. If so, mark the parent complete too (recursively).
    """
    sb = get_client()
    topic = get_topic(topic_id)
    if not topic or not topic.get("parent_id"):
        return

    parent_id = topic["parent_id"]
    # Get all siblings (same parent)
    siblings = (sb.table("topics")
                .select("status")
                .eq("parent_id", parent_id)
                .execute()).data or []

    all_done = all(s["status"] == "completed" for s in siblings)
    if all_done:
        update_topic_status(parent_id, "completed")
        bubble_up_completion(parent_id)  # recurse up


def count_topics_for_goal(goal_id: str) -> dict:
    """Return {total, completed, not_started, needs_revision} counts."""
    topics = list_topics_for_goal(goal_id)
    total = len(topics)
    completed = sum(1 for t in topics if t["status"] == "completed")
    not_started = sum(1 for t in topics if t["status"] == "not_started")
    needs_revision = sum(1 for t in topics if t["status"] == "needs_revision")
    return {
        "total": total,
        "completed": completed,
        "not_started": not_started,
        "needs_revision": needs_revision,
    }


def get_topic_position(topic: dict) -> dict:
    """Return {position, total} of this topic among siblings in same goal."""
    sb = get_client()
    goal_id = topic["goal_id"]
    # Only count root-level or same-parent topics
    parent_id = topic.get("parent_id")
    if parent_id:
        siblings = (sb.table("topics")
                    .select("id, order_index")
                    .eq("goal_id", goal_id)
                    .eq("parent_id", parent_id)
                    .order("order_index")
                    .execute()).data or []
    else:
        siblings = (sb.table("topics")
                    .select("id, order_index")
                    .eq("goal_id", goal_id)
                    .is_("parent_id", "null")
                    .order("order_index")
                    .execute()).data or []

    ids = [s["id"] for s in siblings]
    position = ids.index(topic["id"]) + 1 if topic["id"] in ids else 1
    return {"position": position, "total": len(ids)}


# ---------------------------------------------------------------------------
# Quiz attempts
# ---------------------------------------------------------------------------

def insert_quiz_attempt(topic_id: str, score: int) -> None:
    sb = get_client()
    sb.table("quiz_attempts").insert({
        "topic_id": topic_id,
        "score": score,
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_attempts_for_topic(topic_id: str) -> list[dict]:
    sb = get_client()
    res = (sb.table("quiz_attempts")
           .select("*")
           .eq("topic_id", topic_id)
           .order("attempted_at", desc=True)
           .execute())
    return res.data or []
