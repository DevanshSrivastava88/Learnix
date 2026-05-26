from datetime import datetime, timezone
from typing import Optional
from supabase_svc import get_client


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def create_goal(user_id: int, name: str, description: str, target_date: str) -> dict:
    res = get_client().table("goals").insert({
        "user_id": user_id,
        "name": name,
        "description": description,
        "target_date": target_date,
        "status": "in_progress",
    }).execute()
    return res.data[0]


def list_goals(user_id: int, status: str = "in_progress") -> list[dict]:
    res = (get_client().table("goals")
           .select("*")
           .eq("user_id", user_id)
           .eq("status", status)
           .order("created_at")
           .execute())
    return res.data or []


def get_goal(goal_id: str) -> Optional[dict]:
    res = get_client().table("goals").select("*").eq("id", goal_id).execute()
    return res.data[0] if res.data else None


def update_goal(goal_id: str, **kwargs) -> None:
    get_client().table("goals").update(kwargs).eq("id", goal_id).execute()


def update_goal_status(goal_id: str, status: str) -> None:
    update_goal(goal_id, status=status)


def delete_goal(goal_id: str) -> None:
    get_client().table("goals").delete().eq("id", goal_id).execute()


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def create_topic(goal_id: str, title: str, description: str = "",
                 notes: str = "", parent_id: Optional[str] = None,
                 order_index: int = 0) -> dict:
    res = get_client().table("topics").insert({
        "goal_id": goal_id,
        "title": title,
        "description": description,
        "notes": notes,
        "parent_id": parent_id,
        "order_index": order_index,
        "status": "not_started",
    }).execute()
    return res.data[0]


def list_topics_for_goal(goal_id: str) -> list[dict]:
    res = (get_client().table("topics")
           .select("*")
           .eq("goal_id", goal_id)
           .order("order_index")
           .execute())
    return res.data or []


def get_topic(topic_id: str) -> Optional[dict]:
    res = get_client().table("topics").select("*").eq("id", topic_id).execute()
    return res.data[0] if res.data else None


def get_next_pending_topic(user_id: int) -> Optional[dict]:
    goals = list_goals(user_id, "in_progress")
    if not goals:
        return None
    goal_ids = [g["id"] for g in goals]
    res = (get_client().table("topics")
           .select("*")
           .in_("goal_id", goal_ids)
           .in_("status", ["not_started", "needs_revision"])
           .order("order_index")
           .execute())
    topics = res.data or []
    if not topics:
        return None
    ids_with_pending_children = {t["parent_id"] for t in topics if t.get("parent_id")}
    leaves = [t for t in topics if t["id"] not in ids_with_pending_children]
    return leaves[0] if leaves else topics[0]


def update_topic_status(topic_id: str, status: str, score: Optional[str] = None) -> None:
    update = {"status": status}
    if score is not None:
        update["score"] = score
    if status in ("completed", "needs_revision"):
        update["completed_at"] = datetime.now(timezone.utc).isoformat()
    get_client().table("topics").update(update).eq("id", topic_id).execute()


def bubble_up_completion(topic_id: str) -> None:
    topic = get_topic(topic_id)
    if not topic or not topic.get("parent_id"):
        return
    parent_id = topic["parent_id"]
    siblings = (get_client().table("topics")
                .select("status")
                .eq("parent_id", parent_id)
                .execute()).data or []
    if all(s["status"] == "completed" for s in siblings):
        update_topic_status(parent_id, "completed")
        bubble_up_completion(parent_id)


def count_topics_for_goal(goal_id: str) -> dict:
    topics = list_topics_for_goal(goal_id)
    return {
        "total": len(topics),
        "completed": sum(1 for t in topics if t["status"] == "completed"),
        "not_started": sum(1 for t in topics if t["status"] == "not_started"),
        "needs_revision": sum(1 for t in topics if t["status"] == "needs_revision"),
    }


def get_topic_position(topic: dict) -> dict:
    goal_id = topic["goal_id"]
    parent_id = topic.get("parent_id")
    q = get_client().table("topics").select("id, order_index").eq("goal_id", goal_id)
    if parent_id:
        q = q.eq("parent_id", parent_id)
    else:
        q = q.is_("parent_id", "null")
    siblings = q.order("order_index").execute().data or []
    ids = [s["id"] for s in siblings]
    position = ids.index(topic["id"]) + 1 if topic["id"] in ids else 1
    return {"position": position, "total": len(ids)}


# ---------------------------------------------------------------------------
# Quiz attempts
# ---------------------------------------------------------------------------

def insert_quiz_attempt(topic_id: str, score: int) -> None:
    get_client().table("quiz_attempts").insert({
        "topic_id": topic_id,
        "score": score,
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_attempts_for_topic(topic_id: str) -> list[dict]:
    res = (get_client().table("quiz_attempts")
           .select("*")
           .eq("topic_id", topic_id)
           .order("attempted_at", desc=True)
           .execute())
    return res.data or []
