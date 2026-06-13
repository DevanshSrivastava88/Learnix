from datetime import datetime, timezone
from typing import Optional
from supabase_svc import get_client


# ---------------------------------------------------------------------------
# Difficulty helpers (encoded in goal description as |diff:<level>)
# ---------------------------------------------------------------------------

_DIFF_PREFIX = "|diff:"


def _set_difficulty(description: str, difficulty: str) -> str:
    """Append difficulty marker to description string."""
    base = description.split(_DIFF_PREFIX)[0].rstrip()
    return f"{base}{_DIFF_PREFIX}{difficulty}" if difficulty else base


def _get_difficulty(description: str) -> str:
    """Extract difficulty from description string. Returns 'medium' if not found."""
    if _DIFF_PREFIX in (description or ""):
        return description.split(_DIFF_PREFIX, 1)[1].strip()
    return "medium"


def get_goal_difficulty(goal: dict) -> str:
    """Return difficulty from a goal dict."""
    return _get_difficulty(goal.get("description") or "")


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def create_goal(user_id: int, name: str, description: str, target_date: str,
                difficulty: str = "medium") -> dict:
    encoded_desc = _set_difficulty(description or "", difficulty)
    res = get_client().table("goals").insert({
        "user_id": user_id,
        "name": name,
        "description": encoded_desc,
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


def fuzzy_match_topic(name: str, topics: list[dict]) -> Optional[dict]:
    """Return best-matching topic dict or None. Uses substring then difflib."""
    import difflib
    needle = name.lower().strip()
    if not needle:
        return None
    # Exact or substring match
    for t in topics:
        if needle == t["title"].lower() or needle in t["title"].lower() or t["title"].lower() in needle:
            return t
    # Word overlap
    needle_words = set(needle.split())
    for t in topics:
        title_words = set(t["title"].lower().split())
        if needle_words & title_words:
            return t
    # difflib
    scored = []
    for t in topics:
        ratio = difflib.SequenceMatcher(None, needle, t["title"].lower()).ratio()
        if ratio > 0.4:
            scored.append((ratio, t))
    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]
    return None


def skip_topic(topic_id: str) -> None:
    """Mark a topic as skipped."""
    get_client().table("topics").update({"status": "skipped"}).eq("id", topic_id).execute()


def bulk_create_topics(goal_id: str, titles: list[str]) -> list[dict]:
    """Create multiple topics in order, appended after existing ones."""
    existing = list_topics_for_goal(goal_id)
    base_order = max((t["order_index"] for t in existing), default=-1) + 1
    created = []
    for i, title in enumerate(titles):
        topic = create_topic(goal_id=goal_id, title=title, order_index=base_order + i)
        created.append(topic)
    return created


def get_study_progress(user_id: int) -> Optional[dict]:
    """Return progress summary dict for the user's current active goal.
    Returns None if no goals or no topics.
    Dict keys: goal_name, goal_id, pct, position, total, current_topic_title, current_topic_id
    """
    goals = list_goals(user_id, "in_progress")
    if not goals:
        return None
    goal = goals[0]
    topics = list_topics_for_goal(goal["id"])
    root_topics = [t for t in topics if not t.get("parent_id")]
    if not root_topics:
        return None
    total = len(root_topics)
    completed = sum(1 for t in root_topics if t["status"] == "completed")
    pct = int(completed / total * 100) if total else 0
    next_topic = get_next_pending_topic(user_id)
    if next_topic:
        root_ids = [t["id"] for t in sorted(root_topics, key=lambda x: x["order_index"])]
        position = root_ids.index(next_topic["id"]) + 1 if next_topic["id"] in root_ids else completed + 1
        current_title = next_topic["title"]
        current_id = next_topic["id"]
    else:
        position = total
        current_title = root_topics[-1]["title"] if root_topics else ""
        current_id = root_topics[-1]["id"] if root_topics else None
    return {
        "goal_name": goal["name"],
        "goal_id": goal["id"],
        "pct": pct,
        "position": position,
        "total": total,
        "current_topic_title": current_title,
        "current_topic_id": current_id,
    }


# ---------------------------------------------------------------------------
# Guided study plan — spread root topics across calendar days
# ---------------------------------------------------------------------------

def _plan_offsets(n: int, span: int) -> list[int]:
    """Day-offsets for n topics across `span` days (0 = start day).
    span<=0 (no usable target) → one topic per day: [0,1,2,...]."""
    if n <= 0:
        return []
    if span <= 0:
        return list(range(n))
    if n == 1:
        return [0]
    return [round(i * span / (n - 1)) for i in range(n)]


def generate_plan(goal_id: str, start_date=None) -> list[dict]:
    """Assign each root topic a scheduled_date evenly spread from start_date to the
    goal's target_date (inclusive). One topic per study-day; if there are more topics
    than days, they stack one-per-day from the start. Returns the scheduled root topics."""
    from datetime import date, timedelta

    goal = get_goal(goal_id)
    if not goal:
        return []
    start = start_date or date.today()
    if isinstance(start, str):
        start = date.fromisoformat(start)

    topics = list_topics_for_goal(goal_id)
    roots = sorted([t for t in topics if not t.get("parent_id")],
                   key=lambda t: t["order_index"])
    if not roots:
        return []

    target = None
    if goal.get("target_date"):
        try:
            target = date.fromisoformat(str(goal["target_date"])[:10])
        except (ValueError, TypeError):
            target = None

    n = len(roots)
    span = (target - start).days if (target and target > start) else 0
    offsets = _plan_offsets(n, span)

    update_goal(goal_id, start_date=start.isoformat())
    scheduled = []
    for topic, off in zip(roots, offsets):
        d = (start + timedelta(days=off)).isoformat()
        get_client().table("topics").update({"scheduled_date": d}).eq("id", topic["id"]).execute()
        topic["scheduled_date"] = d
        scheduled.append(topic)
    return scheduled


def get_plan_status(goal_id: str) -> Optional[dict]:
    """On-track snapshot for a planned goal. None if the goal has no plan yet.
    Keys: day, total_days, total, completed, expected, on_track, today_topic, behind_topics."""
    from datetime import date

    goal = get_goal(goal_id)
    if not goal or not goal.get("start_date"):
        return None
    topics = list_topics_for_goal(goal_id)
    roots = sorted([t for t in topics if not t.get("parent_id")],
                   key=lambda t: t["order_index"])
    if not roots:
        return None

    today = date.today()
    start = date.fromisoformat(str(goal["start_date"])[:10])
    target = None
    if goal.get("target_date"):
        try:
            target = date.fromisoformat(str(goal["target_date"])[:10])
        except (ValueError, TypeError):
            target = None

    day = (today - start).days + 1
    total_days = ((target - start).days + 1) if target else len(roots)
    total = len(roots)
    completed = sum(1 for t in roots if t["status"] == "completed")

    def _sched(t):
        return date.fromisoformat(str(t["scheduled_date"])[:10]) if t.get("scheduled_date") else None

    pending = [t for t in roots if t["status"] in ("not_started", "needs_revision")]
    # "Expected by now" = topics whose day has PASSED (strictly before today). Today's
    # topic isn't overdue yet — you have all day — so it doesn't count against on-track.
    expected = sum(1 for t in roots if _sched(t) and _sched(t) < today)
    due = [t for t in pending if _sched(t) and _sched(t) <= today]
    today_topic = (due or pending or [None])[0]
    behind_topics = [t for t in pending if _sched(t) and _sched(t) < today]

    return {
        "goal_name": goal["name"],
        "day": max(day, 1),
        "total_days": total_days,
        "total": total,
        "completed": completed,
        "expected": expected,
        "on_track": completed >= expected,
        "today_topic": today_topic,
        "behind_topics": behind_topics,
    }


def get_weak_topics(goal_id: str, ratio_threshold: float = 0.8) -> list[dict]:
    """Topics due for review: explicitly needs_revision, OR completed but with a
    shaky quiz score (the score field is stored as the string 'correct/total')."""
    weak = []
    for t in list_topics_for_goal(goal_id):
        if t["status"] == "needs_revision":
            weak.append(t)
            continue
        if t["status"] != "completed":
            continue
        score = t.get("score") or ""
        if "/" in score:
            try:
                got, total = (int(x) for x in score.split("/", 1))
                if total and got / total < ratio_threshold:
                    weak.append(t)
            except ValueError:
                pass
    return weak


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
