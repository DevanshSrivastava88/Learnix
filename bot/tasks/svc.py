from datetime import datetime, timezone, timedelta
from typing import Optional
from supabase_svc import get_client


def create_task(user_id: int, title: str, task_type: str,
                description: str = "", recurrence_days: Optional[int] = None,
                target_date: Optional[str] = None) -> dict:
    row = {
        "user_id": user_id,
        "title": title,
        "task_type": task_type,
        "description": description,
        "status": "active",
        "recurrence_days": recurrence_days,
        "target_date": target_date,
    }
    if task_type == "habit" and recurrence_days:
        row["next_reminder_at"] = datetime.now(timezone.utc).isoformat()
    elif task_type == "milestone" and target_date:
        from datetime import date
        target = date.fromisoformat(target_date)
        remind_at = datetime.combine(
            target - timedelta(days=3),
            datetime.min.time()
        ).replace(tzinfo=timezone.utc)
        row["next_reminder_at"] = remind_at.isoformat()
    res = get_client().table("tasks").insert(row).execute()
    return res.data[0]


def list_tasks(user_id: int, status: str = "active") -> list[dict]:
    res = (get_client().table("tasks")
           .select("*")
           .eq("user_id", user_id)
           .eq("status", status)
           .order("created_at")
           .execute())
    return res.data or []


def get_task(task_id: str) -> Optional[dict]:
    res = get_client().table("tasks").select("*").eq("id", task_id).execute()
    return res.data[0] if res.data else None


def update_task(task_id: str, **kwargs) -> None:
    get_client().table("tasks").update(kwargs).eq("id", task_id).execute()


def delete_task(task_id: str) -> None:
    get_client().table("tasks").delete().eq("id", task_id).execute()


def mark_done(task_id: str) -> None:
    """Mark habit done and auto-schedule next reminder."""
    task = get_task(task_id)
    if not task:
        return
    recurrence = task.get("recurrence_days", 1) or 1
    next_at = datetime.now(timezone.utc) + timedelta(days=recurrence)
    update_task(task_id, next_reminder_at=next_at.isoformat())


def get_due_tasks() -> list[dict]:
    """Return all active tasks whose next_reminder_at is <= now (all users)."""
    now = datetime.now(timezone.utc).isoformat()
    res = (get_client().table("tasks")
           .select("*")
           .lte("next_reminder_at", now)
           .eq("status", "active")
           .execute())
    return res.data or []


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

def create_milestone(task_id: str, title: str, order_index: int = 0) -> dict:
    res = get_client().table("milestones").insert({
        "task_id": task_id,
        "title": title,
        "done": False,
        "order_index": order_index,
    }).execute()
    return res.data[0]


def list_milestones(task_id: str) -> list[dict]:
    res = (get_client().table("milestones")
           .select("*")
           .eq("task_id", task_id)
           .order("order_index")
           .execute())
    return res.data or []


def toggle_milestone(milestone_id: str, done: bool) -> None:
    get_client().table("milestones").update({"done": done}).eq("id", milestone_id).execute()


def count_milestones(task_id: str) -> dict:
    items = list_milestones(task_id)
    return {"total": len(items), "done": sum(1 for m in items if m["done"])}
