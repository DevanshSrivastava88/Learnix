from datetime import datetime, timezone, timedelta
from typing import Optional
from supabase_svc import get_client


def create_task(user_id: int, title: str, task_type: str,
                description: str = "", recurrence_days: Optional[int] = None,
                target_date: Optional[str] = None,
                next_reminder_at: Optional[str] = None) -> dict:
    row = {
        "user_id": user_id,
        "title": title,
        "task_type": task_type,
        "description": description,
        "status": "active",
        "recurrence_days": recurrence_days,
        "target_date": target_date,
    }
    if next_reminder_at:
        row["next_reminder_at"] = next_reminder_at
    # Habits with no stated time stay reminder-less (no time = no reminder;
    # the 7pm evening digest mentions them instead)
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
    if not task.get("next_reminder_at") and not task.get("has_custom_time"):
        return  # reminder-less habit stays reminder-less
    recurrence = task.get("recurrence_days", 1) or 1
    if task.get("has_custom_time") and task.get("next_reminder_at"):
        # Preserve the user's chosen clock time — advance whole days, don't
        # reset to "now + N days" (done at 2:52pm was drifting a 9pm habit)
        next_at = datetime.fromisoformat(task["next_reminder_at"]) + timedelta(days=recurrence)
        while next_at <= datetime.now(timezone.utc):
            next_at += timedelta(days=recurrence)
    else:
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


def is_important(task: dict) -> bool:
    """Return True if the task is marked important (via description prefix)."""
    desc = task.get("description", "") or ""
    return desc.startswith("important:true")


def mark_important(task_id: str) -> None:
    """Mark task as important by prepending 'important:true|' to description."""
    task = get_task(task_id)
    if not task:
        return
    desc = task.get("description", "") or ""
    # Already marked — no-op
    if desc.startswith("important:true"):
        return
    new_desc = f"important:true|{desc}"
    update_task(task_id, description=new_desc)


def get_reminder_count(task: dict) -> int:
    """Return how many times this task has been reminded today (stored in description)."""
    desc = task.get("description", "") or ""
    import re
    m = re.search(r"reminded:(\d+)", desc)
    return int(m.group(1)) if m else 0


def increment_reminder_count(task_id: str, task: dict) -> int:
    """Increment the reminded:N counter in description. Returns new count."""
    import re
    desc = task.get("description", "") or ""
    current = get_reminder_count(task)
    new_count = current + 1
    if re.search(r"reminded:\d+", desc):
        new_desc = re.sub(r"reminded:\d+", f"reminded:{new_count}", desc)
    else:
        # Append counter to existing description
        new_desc = desc.rstrip("|") + f"|reminded:{new_count}" if desc else f"reminded:{new_count}"
    update_task(task_id, description=new_desc)
    return new_count


def reset_reminder_count(task_id: str, task: dict) -> None:
    """Reset reminded:N counter in description back to 0 (or remove it)."""
    import re
    desc = task.get("description", "") or ""
    new_desc = re.sub(r"\|?reminded:\d+", "", desc).rstrip("|")
    update_task(task_id, description=new_desc)


def unmark_important(task_id: str) -> None:
    """Remove important flag from task description."""
    task = get_task(task_id)
    if not task:
        return
    desc = task.get("description", "") or ""
    if desc.startswith("important:true|"):
        new_desc = desc[len("important:true|"):]
    elif desc == "important:true":
        new_desc = ""
    else:
        return
    update_task(task_id, description=new_desc)


def log_skip(user_id: int, task_id: str, note: str = "outright") -> dict:
    res = get_client().table("task_skips").insert({
        "user_id": user_id,
        "task_id": task_id,
        "note": note,
    }).execute()
    return res.data[0]


def reschedule_task(task_id: str, new_time_utc) -> None:
    update_task(task_id, next_reminder_at=new_time_utc.isoformat())


def set_custom_time(task_id: str, new_time_utc) -> None:
    """User explicitly picked a reminder time — distinct from auto-advance on done/skip."""
    update_task(task_id, next_reminder_at=new_time_utc.isoformat(), has_custom_time=True)
