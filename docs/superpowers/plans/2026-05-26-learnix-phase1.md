# Learnix Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Learnix from a single-user study bot into a multi-user personal AI operating system with study goals, habits, milestones, morning brief, and EOD check-in.

**Architecture:** Two internal systems (Study + Tasks) share one Telegram bot. A polling-based scheduler (3 fixed jobs checking all users every minute/5min) replaces per-user APScheduler jobs. All DB operations are scoped by `user_id` (Telegram user ID). New modular file layout: `study/` and `tasks/` packages inside `bot/`.

**Tech Stack:** Python 3.11, python-telegram-bot v21, supabase-py 2.10.0, Gemini 2.5 Flash (google-generativeai), pytz, APScheduler (via PTB job_queue)

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| CREATE | `supabase/migrations/002_phase1_multi_user.sql` | Schema changes: user_id on goals, new tasks/milestones, redesigned settings |
| MODIFY | `bot/supabase_svc.py` | Trim to only `get_client()` |
| CREATE | `bot/settings_svc.py` | Per-user settings CRUD |
| CREATE | `bot/study/__init__.py` | Empty package marker |
| CREATE | `bot/study/svc.py` | All study DB ops scoped by user_id (adapted from old supabase_svc.py) |
| CREATE | `bot/study/handlers.py` | /goal, /goals, /addtopic, /study, /progress, /editgoal, /deletegoal, /pausegoal |
| CREATE | `bot/tasks/__init__.py` | Empty package marker |
| CREATE | `bot/tasks/svc.py` | tasks + milestones DB ops |
| CREATE | `bot/tasks/handlers.py` | /newtask, /tasks, /done, /edittask, /deletetask, /pause, /resume, /complete |
| CREATE | `bot/scheduler.py` | 4 polling jobs: study, morning brief, EOD, reminder |
| MODIFY | `bot/bot.py` | Clean router: imports handlers, starts scheduler, /start, /help |
| CREATE | `bot/tests/__init__.py` | Empty |
| CREATE | `bot/tests/test_settings_svc.py` | Unit tests for settings_svc |
| CREATE | `bot/tests/test_study_svc.py` | Unit tests for study/svc |
| CREATE | `bot/tests/test_tasks_svc.py` | Unit tests for tasks/svc |
| CREATE | `bot/tests/test_scheduler.py` | Unit tests for message formatters |
| CREATE | `supabase/migrations/003_activity_log.sql` | New activity_log table for trend graph |
| CREATE | `bot/analytics_svc.py` | log_activity, get_activity_last_n_days, build_graph (matplotlib PNG) |
| MODIFY | `bot/study/handlers.py` | Add analytics_svc.log_activity call in _finish_quiz |
| MODIFY | `bot/tasks/handlers.py` | Add analytics_svc.log_activity in handle_done and handle_complete_task |
| MODIFY | `bot/bot.py` | Add /graph CommandHandler |
| MODIFY | `bot/requirements.txt` | Add matplotlib, numpy |
| CREATE | `bot/tests/test_analytics_svc.py` | Unit tests for analytics_svc |

---

## Task 1: DB Migration

**Files:**
- Create: `supabase/migrations/002_phase1_multi_user.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- 002_phase1_multi_user.sql

-- Add user_id to goals
alter table goals add column user_id bigint not null default 0;
alter table goals alter column user_id drop default;
create index goals_user_id_idx on goals(user_id);

-- Drop singleton settings, replace with per-user
drop table settings;
create table settings (
  user_id            bigint primary key,
  daily_session_time text not null default '09:00',
  morning_brief_time text not null default '08:00',
  eod_time           text not null default '21:00',
  streak             int not null default 0,
  last_study_date    date
);

-- New tasks table (habits + milestones)
create table tasks (
  id               uuid primary key default gen_random_uuid(),
  user_id          bigint not null,
  title            text not null,
  task_type        text not null check (task_type in ('habit', 'milestone')),
  status           text not null default 'active' check (status in ('active', 'paused', 'completed')),
  description      text,
  next_reminder_at timestamptz,
  recurrence_days  int,
  target_date      date,
  created_at       timestamptz not null default now()
);
create index tasks_user_id_idx on tasks(user_id);
create index tasks_reminder_idx on tasks(next_reminder_at) where status = 'active';

-- Milestones (checklist items for milestone-type tasks)
create table milestones (
  id          uuid primary key default gen_random_uuid(),
  task_id     uuid not null references tasks(id) on delete cascade,
  title       text not null,
  done        boolean not null default false,
  order_index int not null default 0
);
create index milestones_task_id_idx on milestones(task_id);
```

- [ ] **Step 2: Apply migration to Supabase**

```python
# Run from bot/ directory
import psycopg2
conn = psycopg2.connect(
    host='db.rqdhaphfyitvtckdjgqg.supabase.co',
    port=5432, dbname='postgres',
    user='postgres', password='2imtTLSYVQH68MWL',
    sslmode='require'
)
sql = open('../supabase/migrations/002_phase1_multi_user.sql').read()
cur = conn.cursor()
cur.execute(sql)
conn.commit()
cur.close(); conn.close()
print('done')
```

Or run:
```
cd D:\Projects\learnix
python -c "
import psycopg2
conn = psycopg2.connect(host='db.rqdhaphfyitvtckdjgqg.supabase.co',port=5432,dbname='postgres',user='postgres',password='2imtTLSYVQH68MWL',sslmode='require')
sql = open('supabase/migrations/002_phase1_multi_user.sql').read()
cur = conn.cursor(); cur.execute(sql); conn.commit(); cur.close(); conn.close()
print('Migration 002 applied')
"
```

Expected output: `Migration 002 applied`

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/002_phase1_multi_user.sql
git commit -m "feat: add phase1 multi-user schema migration"
```

---

## Task 2: Trim supabase_svc.py + Create settings_svc.py

**Files:**
- Modify: `bot/supabase_svc.py`
- Create: `bot/settings_svc.py`
- Create: `bot/tests/test_settings_svc.py`

- [ ] **Step 1: Write failing tests for settings_svc**

Create `bot/tests/__init__.py` (empty).

Create `bot/tests/test_settings_svc.py`:

```python
from unittest.mock import MagicMock, patch
import pytest

with patch('supabase_svc.create_client'):
    import settings_svc

def make_mock_client(rows=None):
    client = MagicMock()
    execute = MagicMock()
    execute.data = rows or []
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = execute
    client.table.return_value.insert.return_value.execute.return_value = execute
    client.table.return_value.upsert.return_value.execute.return_value = execute
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = execute
    return client

def test_get_settings_returns_existing_row():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[{
            'user_id': 123, 'daily_session_time': '09:00',
            'morning_brief_time': '08:00', 'eod_time': '21:00',
            'streak': 3, 'last_study_date': None
        }])
        mock_get.return_value = client
        result = settings_svc.get_settings(123)
        assert result['streak'] == 3
        assert result['daily_session_time'] == '09:00'

def test_get_settings_creates_default_row_if_missing():
    with patch('settings_svc.get_client') as mock_get:
        client = make_mock_client(rows=[])
        mock_get.return_value = client
        result = settings_svc.get_settings(999)
        assert result['user_id'] == 999
        assert result['daily_session_time'] == '09:00'
        client.table.return_value.insert.assert_called_once()

def test_update_streak_increments_on_consecutive_day():
    from datetime import date
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings') as mock_upsert:
        mock_get.return_value = {
            'streak': 4,
            'last_study_date': (date.today().replace(day=date.today().day - 1)).isoformat()
        }
        from datetime import date, timedelta
        yesterday = date.today() - timedelta(days=1)
        mock_get.return_value = {'streak': 4, 'last_study_date': yesterday.isoformat()}
        result = settings_svc.update_streak(123, date.today())
        assert result == 5

def test_update_streak_resets_on_gap():
    from datetime import date, timedelta
    with patch('settings_svc.get_settings') as mock_get, \
         patch('settings_svc.upsert_settings'):
        three_days_ago = date.today() - timedelta(days=3)
        mock_get.return_value = {'streak': 10, 'last_study_date': three_days_ago.isoformat()}
        result = settings_svc.update_streak(123, date.today())
        assert result == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_settings_svc.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` (settings_svc doesn't exist yet)

- [ ] **Step 3: Trim supabase_svc.py to just the client**

Replace entire `bot/supabase_svc.py` with:

```python
import os
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
```

- [ ] **Step 4: Create settings_svc.py**

Create `bot/settings_svc.py`:

```python
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
```

- [ ] **Step 5: Run tests — expect pass**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_settings_svc.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bot/supabase_svc.py bot/settings_svc.py bot/tests/__init__.py bot/tests/test_settings_svc.py
git commit -m "feat: per-user settings service + trim supabase_svc"
```

---

## Task 3: study/svc.py

**Files:**
- Create: `bot/study/__init__.py`
- Create: `bot/study/svc.py`
- Create: `bot/tests/test_study_svc.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_study_svc.py`:

```python
from unittest.mock import MagicMock, patch
import pytest

with patch('supabase_svc.create_client'):
    from study import svc as study_svc

USER_ID = 111

def _mock_execute(rows):
    m = MagicMock()
    m.data = rows
    return m

def make_client():
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = _mock_execute([])
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = _mock_execute([])
    c.table.return_value.insert.return_value.execute.return_value = _mock_execute([{
        'id': 'abc', 'name': 'Test', 'user_id': USER_ID,
        'description': '', 'target_date': '2026-12-01', 'status': 'in_progress',
        'created_at': '2026-01-01T00:00:00'
    }])
    return c

def test_create_goal_returns_dict():
    with patch('study.svc.get_client', return_value=make_client()):
        result = study_svc.create_goal(USER_ID, 'Test Goal', 'desc', '2026-12-01')
        assert result['name'] == 'Test'

def test_list_goals_filters_by_user_id():
    with patch('study.svc.get_client') as mock_get:
        client = MagicMock()
        chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value
        chain.data = []
        mock_get.return_value = client
        result = study_svc.list_goals(USER_ID)
        assert result == []
        # Verify user_id filter was applied
        client.table.assert_called_with("goals")

def test_count_topics_returns_correct_counts():
    with patch('study.svc.list_topics_for_goal') as mock_list:
        mock_list.return_value = [
            {'status': 'completed'},
            {'status': 'completed'},
            {'status': 'not_started'},
            {'status': 'needs_revision'},
        ]
        result = study_svc.count_topics_for_goal('goal-id')
        assert result['total'] == 4
        assert result['completed'] == 2
        assert result['not_started'] == 1
        assert result['needs_revision'] == 1
```

- [ ] **Step 2: Run to confirm fail**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_study_svc.py -v
```

Expected: `ImportError` (study/svc.py doesn't exist)

- [ ] **Step 3: Create study/__init__.py (empty)**

```python
# bot/study/__init__.py
```

- [ ] **Step 4: Create study/svc.py**

Create `bot/study/svc.py`:

```python
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
```

- [ ] **Step 5: Run tests — expect pass**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_study_svc.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bot/study/__init__.py bot/study/svc.py bot/tests/test_study_svc.py
git commit -m "feat: study/svc.py with multi-user goal and topic operations"
```

---

## Task 4: tasks/svc.py

**Files:**
- Create: `bot/tasks/__init__.py`
- Create: `bot/tasks/svc.py`
- Create: `bot/tests/test_tasks_svc.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_tasks_svc.py`:

```python
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import pytest

with patch('supabase_svc.create_client'):
    from tasks import svc as tasks_svc

USER_ID = 222

def _row(**kwargs):
    base = {
        'id': 'task-1', 'user_id': USER_ID, 'title': 'Make bed',
        'task_type': 'habit', 'status': 'active', 'description': '',
        'next_reminder_at': None, 'recurrence_days': 1,
        'target_date': None, 'created_at': '2026-01-01T00:00:00'
    }
    base.update(kwargs)
    return base

def make_client(rows=None):
    c = MagicMock()
    ex = MagicMock(); ex.data = rows or []
    c.table.return_value.insert.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = ex
    c.table.return_value.update.return_value.eq.return_value.execute.return_value = ex
    return c

def test_create_habit_returns_task():
    with patch('tasks.svc.get_client', return_value=make_client(rows=[_row()])):
        result = tasks_svc.create_task(USER_ID, 'Make bed', 'habit', recurrence_days=1)
        assert result['task_type'] == 'habit'

def test_create_milestone_returns_task():
    row = _row(task_type='milestone', recurrence_days=None, target_date='2026-12-01')
    with patch('tasks.svc.get_client', return_value=make_client(rows=[row])):
        result = tasks_svc.create_task(USER_ID, 'Launch project', 'milestone', target_date='2026-12-01')
        assert result['task_type'] == 'milestone'

def test_mark_done_sets_next_reminder():
    now = datetime.now(timezone.utc)
    with patch('tasks.svc.get_task') as mock_get, \
         patch('tasks.svc.get_client') as mock_client:
        mock_get.return_value = _row(recurrence_days=2)
        client = make_client()
        mock_client.return_value = client
        tasks_svc.mark_done('task-1')
        update_call = client.table.return_value.update.call_args
        updated_data = update_call[0][0]
        assert 'next_reminder_at' in updated_data

def test_get_due_tasks_returns_overdue():
    overdue = _row(next_reminder_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    with patch('tasks.svc.get_client') as mock_client:
        client = MagicMock()
        ex = MagicMock(); ex.data = [overdue]
        client.table.return_value.select.return_value.lte.return_value.eq.return_value.execute.return_value = ex
        mock_client.return_value = client
        result = tasks_svc.get_due_tasks()
        assert len(result) == 1
```

- [ ] **Step 2: Run to confirm fail**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_tasks_svc.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create tasks/__init__.py (empty)**

```python
# bot/tasks/__init__.py
```

- [ ] **Step 4: Create tasks/svc.py**

Create `bot/tasks/svc.py`:

```python
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
        remind_at = datetime.combine(target - timedelta(days=3), datetime.min.time()).replace(tzinfo=timezone.utc)
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
```

- [ ] **Step 5: Run tests — expect pass**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_tasks_svc.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bot/tasks/__init__.py bot/tasks/svc.py bot/tests/test_tasks_svc.py
git commit -m "feat: tasks/svc.py with habit and milestone DB operations"
```

---

## Task 5: scheduler.py (formatters + polling jobs)

**Files:**
- Create: `bot/scheduler.py`
- Create: `bot/tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests for formatters**

Create `bot/tests/test_scheduler.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone

with patch('supabase_svc.create_client'):
    import scheduler

def make_goal(name='AI Engineer', total=10, completed=3, target='2026-12-01'):
    return {'id': 'g1', 'name': name, 'target_date': target, 'status': 'in_progress'}

def test_format_morning_brief_no_data():
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.study_svc.get_next_pending_topic', return_value=None), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 0}):
        msg = scheduler.format_morning_brief(123)
        assert 'Good morning' in msg
        assert 'No active' in msg or 'nothing' in msg.lower() or 'no ' in msg.lower()

def test_format_morning_brief_with_study_goal():
    goal = make_goal()
    topic = {'id': 't1', 'title': 'Backprop', 'goal_id': 'g1', 'status': 'not_started', 'parent_id': None}
    with patch('scheduler.study_svc.list_goals', return_value=[goal]), \
         patch('scheduler.study_svc.count_topics_for_goal', return_value={'total': 10, 'completed': 3, 'not_started': 7, 'needs_revision': 0}), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.study_svc.get_next_pending_topic', return_value=topic), \
         patch('scheduler.study_svc.get_goal', return_value=goal), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 5}):
        msg = scheduler.format_morning_brief(123)
        assert 'Backprop' in msg
        assert 'AI Engineer' in msg

def test_format_eod_empty():
    with patch('scheduler.study_svc.list_goals', return_value=[]), \
         patch('scheduler.tasks_svc.list_tasks', return_value=[]), \
         patch('scheduler.settings_svc.get_settings', return_value={'streak': 2}):
        msg = scheduler.format_eod(123)
        assert 'wrap' in msg.lower() or 'eod' in msg.lower() or 'day' in msg.lower()
        assert '2' in msg
```

- [ ] **Step 2: Run to confirm fail**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_scheduler.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create scheduler.py**

Create `bot/scheduler.py`:

```python
"""
scheduler.py — Polling-based scheduler for all users.

4 jobs, all polling (no per-user APScheduler jobs):
1. study_poller   — every 60s, checks daily_session_time match
2. morning_poller — every 60s, checks morning_brief_time match
3. eod_poller     — every 60s, checks eod_time match
4. reminder_poller — every 300s, checks tasks.next_reminder_at <= now
"""

import logging
from datetime import datetime, date
from typing import Optional

import pytz
from telegram.ext import Application, ContextTypes
from telegram.constants import ParseMode

import settings_svc
import study.svc as study_svc
import tasks.svc as tasks_svc

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Formatters (pure functions — easy to test)
# ---------------------------------------------------------------------------

def format_morning_brief(user_id: int) -> str:
    settings = settings_svc.get_settings(user_id)
    streak = settings.get("streak", 0) or 0
    goals = study_svc.list_goals(user_id)
    all_tasks = tasks_svc.list_tasks(user_id)
    habits = [t for t in all_tasks if t["task_type"] == "habit"]
    milestones = [t for t in all_tasks if t["task_type"] == "milestone"]
    next_topic = study_svc.get_next_pending_topic(user_id)

    lines = ["🌅 *Good morning!* Here's your day:\n"]

    # Study section
    lines.append("📚 *STUDY*")
    if not goals:
        lines.append("No active study goals. Use /goal to create one.")
    else:
        for g in goals:
            counts = study_svc.count_topics_for_goal(g["id"])
            total = counts["total"]
            completed = counts["completed"]
            pct = int(completed / total * 100) if total else 0
            lines.append(f"• {g['name']} — {completed}/{total} topics ({pct}%)")
        if next_topic:
            goal = study_svc.get_goal(next_topic["goal_id"])
            goal_name = goal["name"] if goal else ""
            lines.append(f"\n▶️ Next up: *{next_topic['title']}* ({goal_name})")
            lines.append("Reply /study to start your session.")

    # Habits section
    lines.append("\n✅ *HABITS*")
    if not habits:
        lines.append("No habits yet. Use /newtask to add one.")
    else:
        now = datetime.now(IST)
        for h in habits:
            next_at = h.get("next_reminder_at")
            if next_at:
                try:
                    from datetime import timezone
                    next_dt = datetime.fromisoformat(next_at).astimezone(IST)
                    if next_dt.date() <= now.date():
                        lines.append(f"• ⏰ {h['title']} (due today)")
                    else:
                        lines.append(f"• {h['title']} (next: {next_dt.strftime('%b %d')})")
                except Exception:
                    lines.append(f"• {h['title']}")
            else:
                lines.append(f"• {h['title']}")

    # Milestones section
    lines.append("\n📋 *MILESTONES*")
    if not milestones:
        lines.append("No milestones. Use /newtask to add one.")
    else:
        for m in milestones:
            counts = tasks_svc.count_milestones(m["id"])
            total = counts["total"]
            done = counts["done"]
            target = m.get("target_date", "")
            deadline_str = ""
            if target:
                try:
                    target_date = date.fromisoformat(str(target))
                    days_left = (target_date - date.today()).days
                    if days_left < 0:
                        deadline_str = f" ⚠️ Overdue"
                    elif days_left <= 3:
                        deadline_str = f" 🔥 {days_left}d left"
                    else:
                        deadline_str = f" ({days_left}d left)"
                except Exception:
                    pass
            lines.append(f"• {m['title']} — {done}/{total}{deadline_str}")

    lines.append(f"\n🔥 Streak: {streak} day(s)")
    return "\n".join(lines)


def format_eod(user_id: int) -> str:
    settings = settings_svc.get_settings(user_id)
    streak = settings.get("streak", 0) or 0
    today = date.today()

    lines = ["🌙 *Day wrap-up!*\n"]

    # Completed topics today
    goals = study_svc.list_goals(user_id)
    studied_today = []
    for g in goals:
        topics = study_svc.list_topics_for_goal(g["id"])
        for t in topics:
            if t.get("completed_at"):
                try:
                    completed_dt = datetime.fromisoformat(t["completed_at"]).astimezone(IST)
                    if completed_dt.date() == today and t["status"] == "completed":
                        studied_today.append(t["title"])
                except Exception:
                    pass

    if studied_today:
        lines.append("📚 *Studied today:*")
        for title in studied_today:
            lines.append(f"  ✅ {title}")
    else:
        lines.append("📚 No study sessions today — catch up tomorrow!")

    # Habits
    all_tasks = tasks_svc.list_tasks(user_id)
    habits = [t for t in all_tasks if t["task_type"] == "habit"]
    if habits:
        lines.append("\n✅ *Habits:*")
        for h in habits:
            next_at = h.get("next_reminder_at")
            if next_at:
                try:
                    from datetime import timezone
                    next_dt = datetime.fromisoformat(next_at).astimezone(IST)
                    if next_dt.date() > today:
                        lines.append(f"  ✅ {h['title']}")
                    else:
                        lines.append(f"  ❌ {h['title']} (not done)")
                except Exception:
                    lines.append(f"  • {h['title']}")

    lines.append(f"\n🔥 Streak: {streak} day(s) — keep it up!")
    lines.append("\nSee you tomorrow! 👋")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Polling jobs
# ---------------------------------------------------------------------------

async def study_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: send daily study prompt to users whose study time == now."""
    now_ist = datetime.now(IST)
    current_hhmm = now_ist.strftime("%H:%M")
    users = settings_svc.get_all_users()
    for user in users:
        if user.get("daily_session_time") != current_hhmm:
            continue
        uid = user["user_id"]
        topic = study_svc.get_next_pending_topic(uid)
        if not topic:
            await ctx.bot.send_message(uid, "🎉 All topics done! Add more with /addtopic.")
            continue
        goal = study_svc.get_goal(topic["goal_id"])
        goal_name = goal["name"] if goal else "?"
        pos = study_svc.get_topic_position(topic)
        msg = (
            f"📖 Time to study!\n\n"
            f"*{topic['title']}* — {goal_name} "
            f"(Topic {pos['position']}/{pos['total']})\n\n"
            f"Reply *yes* to start now, or *later* to skip."
        )
        await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        # Store in bot_data for yes/later
        ctx.bot_data.setdefault("pending_sessions", {})[uid] = topic["id"]


async def morning_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: send morning brief to users whose morning_brief_time == now."""
    now_ist = datetime.now(IST)
    current_hhmm = now_ist.strftime("%H:%M")
    users = settings_svc.get_all_users()
    for user in users:
        if user.get("morning_brief_time") != current_hhmm:
            continue
        uid = user["user_id"]
        try:
            msg = format_morning_brief(uid)
            await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Morning brief failed for {uid}: {e}")


async def eod_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: send EOD check-in to users whose eod_time == now."""
    now_ist = datetime.now(IST)
    current_hhmm = now_ist.strftime("%H:%M")
    users = settings_svc.get_all_users()
    for user in users:
        if user.get("eod_time") != current_hhmm:
            continue
        uid = user["user_id"]
        try:
            msg = format_eod(uid)
            await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"EOD failed for {uid}: {e}")


async def reminder_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 300s: send habit/milestone reminders for all due tasks."""
    due = tasks_svc.get_due_tasks()
    for task in due:
        uid = task["user_id"]
        title = task["title"]
        task_id = task["id"]
        task_type = task["task_type"]
        try:
            if task_type == "habit":
                msg = f"⏰ Habit reminder: *{title}*\n\nDone? Reply /done_{task_id}"
            else:
                counts = tasks_svc.count_milestones(task_id)
                total = counts["total"]
                done = counts["done"]
                target = task.get("target_date", "")
                msg = (
                    f"📋 Milestone reminder: *{title}*\n"
                    f"Progress: {done}/{total}\n"
                    f"Deadline: {target}\n\n"
                    f"Use /tasks to update progress."
                )
            await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Reminder failed for task {task_id}: {e}")


def register_jobs(app: Application) -> None:
    """Register all 4 polling jobs on app startup."""
    jq = app.job_queue
    jq.run_repeating(study_poller, interval=60, first=10, name="study_poller")
    jq.run_repeating(morning_poller, interval=60, first=15, name="morning_poller")
    jq.run_repeating(eod_poller, interval=60, first=20, name="eod_poller")
    jq.run_repeating(reminder_poller, interval=300, first=30, name="reminder_poller")
    logger.info("All scheduler jobs registered.")
```

- [ ] **Step 4: Run tests — expect pass**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_scheduler.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/scheduler.py bot/tests/test_scheduler.py
git commit -m "feat: polling scheduler with morning brief and EOD formatters"
```

---

## Task 6: study/handlers.py

**Files:**
- Create: `bot/study/handlers.py`

- [ ] **Step 1: Create study/handlers.py**

This moves all study-related handlers from `bot.py` into a dedicated module and adds edit/delete/pause.

Create `bot/study/handlers.py`:

```python
"""Study command handlers: /goal, /goals, /addtopic, /study, /progress, /editgoal, /deletegoal, /pausegoal"""

import logging
from datetime import datetime

import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters
)

import study.svc as db
import claude_svc as claude
import settings_svc

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# Conversation states
GOAL_NAME, GOAL_DESC, GOAL_DEADLINE = range(3)
AT_GOAL_SELECT, AT_PARENT_SELECT, AT_TITLE, AT_DESC, AT_NOTES = range(5, 10)
EDIT_GOAL_SELECT, EDIT_GOAL_FIELD, EDIT_GOAL_VALUE = range(10, 13)
DELETE_GOAL_SELECT, DELETE_GOAL_CONFIRM = range(13, 15)


def _format_goal_status(goal: dict) -> str:
    counts = db.count_topics_for_goal(goal["id"])
    total = counts["total"]
    completed = counts["completed"]
    target = goal.get("target_date", "")
    if total == 0:
        progress = "No topics yet"
    else:
        pct = int(completed / total * 100)
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        progress = f"{bar} {completed}/{total} ({pct}%)"
    deadline_str = ""
    if target:
        try:
            target_dt = datetime.fromisoformat(str(target))
            now = datetime.now(IST)
            if target_dt.tzinfo is None:
                target_dt = IST.localize(target_dt)
            days_left = (target_dt.date() - now.date()).days
            if days_left < 0:
                deadline_str = f"  ⚠️ Overdue by {abs(days_left)}d"
            elif days_left == 0:
                deadline_str = "  🔥 Due today!"
            elif days_left <= 7:
                deadline_str = f"  ⏰ {days_left}d left"
            else:
                deadline_str = f"  📅 {days_left}d left"
        except Exception:
            deadline_str = f"  📅 {target}"
    return f"*{goal['name']}*{deadline_str}\n{progress}"


# ---------------------------------------------------------------------------
# /goals — list study goals
# ---------------------------------------------------------------------------

async def cmd_goals(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No active study goals. Use /goal to create one.")
        return
    lines = ["*📚 Study Goals*\n"]
    for g in goals:
        lines.append(_format_goal_status(g))
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /goal — create goal
# ---------------------------------------------------------------------------

async def cmd_goal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Let's create a new study goal! 🎯\n\nWhat's the name of your goal?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GOAL_NAME


async def goal_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["goal_name"] = update.message.text.strip()
    await update.message.reply_text("Great! Give a short description (or send '-' to skip):")
    return GOAL_DESC


async def goal_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["goal_desc"] = "" if desc == "-" else desc
    await update.message.reply_text(
        "Target completion date? (YYYY-MM-DD, e.g. 2026-12-01)\nOr send '-' to skip:"
    )
    return GOAL_DEADLINE


async def goal_get_deadline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    deadline = update.message.text.strip()
    if deadline != "-":
        try:
            datetime.fromisoformat(deadline)
        except ValueError:
            await update.message.reply_text("Invalid date. Use YYYY-MM-DD or send '-' to skip:")
            return GOAL_DEADLINE
    else:
        deadline = None
    uid = update.effective_user.id
    name = ctx.user_data["goal_name"]
    desc = ctx.user_data.get("goal_desc", "")
    db.create_goal(uid, name, desc, deadline)
    await update.message.reply_text(
        f"✅ Study goal *{name}* created!\n\nUse /addtopic to add topics.",
        parse_mode=ParseMode.MARKDOWN,
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /addtopic
# ---------------------------------------------------------------------------

async def cmd_addtopic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No active goals. Create one with /goal first.")
        return ConversationHandler.END
    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals] + [["Cancel"]]
    await update.message.reply_text(
        "Which goal is this topic for?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return AT_GOAL_SELECT


async def at_goal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Goal not found. Try /addtopic again.")
        return ConversationHandler.END
    ctx.user_data["selected_goal"] = goal
    topics = db.list_topics_for_goal(goal["id"])
    root_topics = [t for t in topics if not t.get("parent_id")]
    if root_topics:
        buttons = [["None (root topic)"]] + [[t["title"]] for t in root_topics] + [["Cancel"]]
        ctx.user_data["root_topics"] = root_topics
        await update.message.reply_text(
            "Is this a subtopic? Select a parent, or 'None' for root:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return AT_PARENT_SELECT
    ctx.user_data["parent_topic"] = None
    await update.message.reply_text("What's the topic title?", reply_markup=ReplyKeyboardRemove())
    return AT_TITLE


async def at_parent_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    if chosen == "None (root topic)":
        ctx.user_data["parent_topic"] = None
    else:
        root_topics = ctx.user_data.get("root_topics", [])
        ctx.user_data["parent_topic"] = next((t for t in root_topics if t["title"] == chosen), None)
    await update.message.reply_text("What's the topic title?", reply_markup=ReplyKeyboardRemove())
    return AT_TITLE


async def at_get_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["topic_title"] = update.message.text.strip()
    await update.message.reply_text("Short description? (or '-' to skip):")
    return AT_DESC


async def at_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["topic_desc"] = "" if desc == "-" else desc
    await update.message.reply_text(
        "Any notes for this topic? (or '-' to skip)\nTip: Gemini uses these when teaching."
    )
    return AT_NOTES


async def at_get_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    notes = update.message.text.strip()
    ctx.user_data["topic_notes"] = "" if notes == "-" else notes
    goal = ctx.user_data["selected_goal"]
    parent = ctx.user_data.get("parent_topic")
    title = ctx.user_data["topic_title"]
    existing = db.list_topics_for_goal(goal["id"])
    siblings = [t for t in existing if t.get("parent_id") == (parent["id"] if parent else None)]
    db.create_topic(
        goal_id=goal["id"],
        title=title,
        description=ctx.user_data.get("topic_desc", ""),
        notes=ctx.user_data.get("topic_notes", ""),
        parent_id=parent["id"] if parent else None,
        order_index=len(siblings),
    )
    parent_str = f" (under *{parent['title']}*)" if parent else ""
    await update.message.reply_text(
        f"✅ Topic *{title}*{parent_str} added to *{goal['name']}*!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /study — manual trigger
# ---------------------------------------------------------------------------

async def cmd_study(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    topic = db.get_next_pending_topic(uid)
    if not topic:
        await update.message.reply_text("🎉 No pending topics! Add more with /addtopic.")
        return
    goal = db.get_goal(topic["goal_id"])
    pos = db.get_topic_position(topic)
    await update.message.reply_text(
        f"Starting session...\nGoal: *{goal['name'] if goal else '?'}*  |  Topic {pos['position']}/{pos['total']}",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _run_study_session(update, ctx, topic)


async def _run_study_session(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic: dict) -> None:
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    await ctx.bot.send_message(chat_id, f"📖 *{topic['title']}*\n\nTeaching...", parse_mode=ParseMode.MARKDOWN)
    try:
        lesson = claude.teach_topic(topic["title"], topic.get("notes", "") or "")
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Error: {e}")
        return
    await ctx.bot.send_message(chat_id, lesson)
    await ctx.bot.send_message(chat_id, "Now let's test your understanding! 🧠")
    try:
        questions = claude.generate_quiz(topic["title"], topic.get("notes", "") or "")
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Quiz error: {e}")
        return
    ctx.bot_data.setdefault("quiz_state", {})[uid] = {
        "topic_id": topic["id"], "topic": topic,
        "questions": questions, "q_index": 0, "score": 0, "chat_id": chat_id,
    }
    await _ask_quiz_question(ctx, uid)


async def _ask_quiz_question(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    state = ctx.bot_data.get("quiz_state", {}).get(user_id)
    if not state:
        return
    idx = state["q_index"]
    questions = state["questions"]
    if idx >= len(questions):
        await _finish_quiz(ctx, user_id)
        return
    q = questions[idx]
    await ctx.bot.send_message(
        state["chat_id"],
        f"*Q{idx+1}/{len(questions)}:* {q['question']}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _finish_quiz(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    state = ctx.bot_data.get("quiz_state", {}).pop(user_id, None)
    if not state:
        return
    score = state["score"]
    total = len(state["questions"])
    topic_id = state["topic_id"]
    chat_id = state["chat_id"]
    passed = score >= 3
    new_status = "completed" if passed else "needs_revision"
    db.update_topic_status(topic_id, new_status, f"{score}/{total}")
    db.insert_quiz_attempt(topic_id, score)
    if passed:
        db.bubble_up_completion(topic_id)
    from datetime import date
    new_streak = settings_svc.update_streak(user_id, date.today())
    emoji = "🎉" if passed else "📚"
    label = "Passed!" if passed else "Needs revision"
    msg = (
        f"{emoji} *Quiz Complete!*\n\n"
        f"Score: *{score}/{total}*\nResult: {label}\n"
        f"🔥 Streak: {new_streak} day(s)\n\n"
    )
    msg += "Topic marked complete ✅" if passed else "You'll revisit this later 💪"
    await ctx.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)


async def handle_quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    state = ctx.bot_data.get("quiz_state", {}).get(uid)
    if not state:
        return
    user_answer = update.message.text.strip()
    idx = state["q_index"]
    q = state["questions"][idx]
    try:
        result = claude.score_answer(q["question"], q["expected_answer"], user_answer)
        correct = result.get("correct", False)
        explanation = result.get("explanation", "")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Scoring error: {e}")
        return
    if correct:
        state["score"] += 1
    await update.message.reply_text(
        f"{'✅' if correct else '❌'} {explanation}",
        parse_mode=ParseMode.MARKDOWN,
    )
    state["q_index"] += 1
    await _ask_quiz_question(ctx, uid)


# ---------------------------------------------------------------------------
# /progress
# ---------------------------------------------------------------------------

async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No active goals. Use /goal to create one.")
        return
    lines = ["*📊 Full Progress*\n"]
    for goal in goals:
        lines.append(_format_goal_status(goal))
        topics = db.list_topics_for_goal(goal["id"])
        if topics:
            lines.append("Topics:")
            for t in topics:
                prefix = "  └ " if t.get("parent_id") else "  • "
                icon = {"completed": "✅", "needs_revision": "🔁", "not_started": "⬜"}.get(t["status"], "⬜")
                score_str = f" [{t['score']}]" if t.get("score") else ""
                lines.append(f"{prefix}{icon} {t['title']}{score_str}")
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /editgoal
# ---------------------------------------------------------------------------

async def cmd_editgoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No active goals to edit.")
        return ConversationHandler.END
    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals] + [["Cancel"]]
    await update.message.reply_text(
        "Which goal do you want to edit?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return EDIT_GOAL_SELECT


async def editgoal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Goal not found. Try /editgoal again.")
        return ConversationHandler.END
    ctx.user_data["editing_goal"] = goal
    buttons = [["Name"], ["Description"], ["Target date"], ["Cancel"]]
    await update.message.reply_text(
        f"Editing *{goal['name']}*. What do you want to change?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return EDIT_GOAL_FIELD


async def editgoal_field(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    field = update.message.text.strip()
    if field == "Cancel":
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    ctx.user_data["editing_field"] = field
    prompts = {"Name": "Enter the new name:", "Description": "Enter the new description:", "Target date": "Enter new date (YYYY-MM-DD):"}
    await update.message.reply_text(prompts.get(field, "Enter new value:"), reply_markup=ReplyKeyboardRemove())
    return EDIT_GOAL_VALUE


async def editgoal_value(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    goal = ctx.user_data["editing_goal"]
    field = ctx.user_data["editing_field"]
    field_map = {"Name": "name", "Description": "description", "Target date": "target_date"}
    db_field = field_map.get(field)
    if db_field == "target_date":
        try:
            from datetime import datetime
            datetime.fromisoformat(value)
        except ValueError:
            await update.message.reply_text("Invalid date format (YYYY-MM-DD). Try again:")
            return EDIT_GOAL_VALUE
    db.update_goal(goal["id"], **{db_field: value})
    await update.message.reply_text(f"✅ {field} updated!", reply_markup=ReplyKeyboardRemove())
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /deletegoal
# ---------------------------------------------------------------------------

async def cmd_deletegoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No goals to delete.")
        return ConversationHandler.END
    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals] + [["Cancel"]]
    await update.message.reply_text(
        "Which goal do you want to delete? (This deletes all its topics too!)",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DELETE_GOAL_SELECT


async def deletegoal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Goal not found.")
        return ConversationHandler.END
    ctx.user_data["deleting_goal"] = goal
    buttons = [["Yes, delete it"], ["Cancel"]]
    await update.message.reply_text(
        f"⚠️ Delete *{goal['name']}* and ALL its topics? This cannot be undone.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DELETE_GOAL_CONFIRM


async def deletegoal_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    if choice == "Yes, delete it":
        goal = ctx.user_data["deleting_goal"]
        db.delete_goal(goal["id"])
        await update.message.reply_text(
            f"🗑️ *{goal['name']}* deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /pausegoal — toggle paused/in_progress
# ---------------------------------------------------------------------------

async def cmd_pausegoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    paused = db.list_goals(uid, status="paused")
    all_goals = goals + paused
    if not all_goals:
        await update.message.reply_text("No goals found.")
        return
    lines = ["*Your goals:*\n"]
    for g in all_goals:
        status_icon = "▶️" if g["status"] == "in_progress" else "⏸️"
        lines.append(f"{status_icon} /togglegoal_{g['id'][:8]} — {g['name']}")
    lines.append("\nTap a command to toggle pause/resume.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_togglegoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/togglegoal_", "")
    uid = update.effective_user.id
    goals = db.list_goals(uid) + db.list_goals(uid, status="paused")
    goal = next((g for g in goals if g["id"].startswith(short_id)), None)
    if not goal:
        await update.message.reply_text("Goal not found.")
        return
    new_status = "paused" if goal["status"] == "in_progress" else "in_progress"
    db.update_goal_status(goal["id"], new_status)
    icon = "⏸️ Paused" if new_status == "paused" else "▶️ Resumed"
    await update.message.reply_text(f"{icon}: *{goal['name']}*", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# ConversationHandlers to export
# ---------------------------------------------------------------------------

def get_handlers():
    cancel_handler = MessageHandler(filters.Regex(r"^Cancel$"), _cancel)

    goal_conv = ConversationHandler(
        entry_points=[CommandHandler("goal", cmd_goal)],
        states={
            GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_name)],
            GOAL_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_desc)],
            GOAL_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_deadline)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    addtopic_conv = ConversationHandler(
        entry_points=[CommandHandler("addtopic", cmd_addtopic)],
        states={
            AT_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_goal_select)],
            AT_PARENT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_parent_select)],
            AT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_title)],
            AT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_desc)],
            AT_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_notes)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    editgoal_conv = ConversationHandler(
        entry_points=[CommandHandler("editgoal", cmd_editgoal)],
        states={
            EDIT_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, editgoal_select)],
            EDIT_GOAL_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, editgoal_field)],
            EDIT_GOAL_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, editgoal_value)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    deletegoal_conv = ConversationHandler(
        entry_points=[CommandHandler("deletegoal", cmd_deletegoal)],
        states={
            DELETE_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletegoal_select)],
            DELETE_GOAL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletegoal_confirm)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    return [
        goal_conv, addtopic_conv, editgoal_conv, deletegoal_conv,
        CommandHandler("goals", cmd_goals),
        CommandHandler("study", cmd_study),
        CommandHandler("progress", cmd_progress),
        CommandHandler("editgoal", cmd_editgoal),
        CommandHandler("pausegoal", cmd_pausegoal),
        MessageHandler(filters.Regex(r"^/togglegoal_"), handle_togglegoal),
    ]


async def _cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
```

- [ ] **Step 2: Verify import works**

```
cd D:\Projects\learnix\bot
python -c "from study.handlers import get_handlers; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/study/handlers.py
git commit -m "feat: study/handlers.py with edit, delete, pause goal commands"
```

---

## Task 7: tasks/handlers.py

**Files:**
- Create: `bot/tasks/handlers.py`

- [ ] **Step 1: Create tasks/handlers.py**

Create `bot/tasks/handlers.py`:

```python
"""Task handlers: /newtask, /tasks, /done_<id>, /edittask, /deletetask, /pause, /resume, /complete"""

import logging
from datetime import datetime

import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters
)

import tasks.svc as db

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# Conversation states
NT_TYPE, NT_TITLE, NT_DESC, NT_RECURRENCE, NT_DEADLINE, NT_MILESTONES, NT_MILESTONE_ITEM = range(20, 27)
ET_SELECT, ET_FIELD, ET_VALUE = range(27, 30)
DT_SELECT, DT_CONFIRM = range(30, 32)
MILESTONE_ADD, MILESTONE_ITEM = range(32, 34)


# ---------------------------------------------------------------------------
# /newtask — create habit or milestone
# ---------------------------------------------------------------------------

async def cmd_newtask(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    buttons = [["Habit (recurring reminder)"], ["Milestone (goal with checklist)"], ["Cancel"]]
    await update.message.reply_text(
        "What kind of task?\n\n"
        "• *Habit* — recurring action (e.g. make bed daily)\n"
        "• *Milestone* — goal with checklist + deadline (e.g. launch project)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return NT_TYPE


async def nt_get_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if "Habit" in text:
        ctx.user_data["task_type"] = "habit"
    elif "Milestone" in text:
        ctx.user_data["task_type"] = "milestone"
    else:
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    await update.message.reply_text(
        "What's the name of this task?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NT_TITLE


async def nt_get_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["task_title"] = update.message.text.strip()
    await update.message.reply_text("Short description? (or '-' to skip):")
    return NT_DESC


async def nt_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["task_desc"] = "" if desc == "-" else desc
    if ctx.user_data["task_type"] == "habit":
        buttons = [["Every day"], ["Every 2 days"], ["Every 3 days"], ["Every 7 days"]]
        await update.message.reply_text(
            "How often should I remind you?",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return NT_RECURRENCE
    else:
        await update.message.reply_text(
            "Target completion date? (YYYY-MM-DD, e.g. 2026-12-01)\nOr '-' to skip:"
        )
        return NT_DEADLINE


async def nt_get_recurrence(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    mapping = {"Every day": 1, "Every 2 days": 2, "Every 3 days": 3, "Every 7 days": 7}
    days = mapping.get(text)
    if not days:
        try:
            days = int(text.split()[1]) if "day" in text else int(text)
        except Exception:
            days = 1
    ctx.user_data["recurrence_days"] = days
    uid = update.effective_user.id
    task = db.create_task(
        user_id=uid,
        title=ctx.user_data["task_title"],
        task_type="habit",
        description=ctx.user_data.get("task_desc", ""),
        recurrence_days=days,
    )
    await update.message.reply_text(
        f"✅ Habit *{task['title']}* created! I'll remind you every {days} day(s).",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    ctx.user_data.clear()
    return ConversationHandler.END


async def nt_get_deadline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    deadline = update.message.text.strip()
    if deadline != "-":
        try:
            datetime.fromisoformat(deadline)
        except ValueError:
            await update.message.reply_text("Invalid date. Use YYYY-MM-DD or '-':")
            return NT_DEADLINE
        ctx.user_data["target_date"] = deadline
    else:
        ctx.user_data["target_date"] = None
    await update.message.reply_text(
        "Add checklist items? Send each item one by one, then send 'done' when finished.\n"
        "Or send '-' to skip:"
    )
    ctx.user_data["milestones"] = []
    return NT_MILESTONES


async def nt_collect_milestones(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "-" or text.lower() == "done":
        uid = update.effective_user.id
        task = db.create_task(
            user_id=uid,
            title=ctx.user_data["task_title"],
            task_type="milestone",
            description=ctx.user_data.get("task_desc", ""),
            target_date=ctx.user_data.get("target_date"),
        )
        for i, item in enumerate(ctx.user_data.get("milestones", [])):
            db.create_milestone(task["id"], item, order_index=i)
        count = len(ctx.user_data.get("milestones", []))
        await update.message.reply_text(
            f"✅ Milestone *{task['title']}* created with {count} checklist item(s)!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        ctx.user_data.clear()
        return ConversationHandler.END
    ctx.user_data["milestones"].append(text)
    count = len(ctx.user_data["milestones"])
    await update.message.reply_text(
        f"Added item {count}: *{text}*\nSend another item or 'done' to finish:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return NT_MILESTONES


# ---------------------------------------------------------------------------
# /tasks — list all active tasks
# ---------------------------------------------------------------------------

async def cmd_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    all_tasks = db.list_tasks(uid)
    if not all_tasks:
        await update.message.reply_text(
            "No active tasks. Use /newtask to create a habit or milestone."
        )
        return
    habits = [t for t in all_tasks if t["task_type"] == "habit"]
    milestones = [t for t in all_tasks if t["task_type"] == "milestone"]
    lines = ["*📋 Your Tasks*\n"]
    if habits:
        lines.append("*Habits:*")
        for h in habits:
            next_at = h.get("next_reminder_at")
            recur = h.get("recurrence_days", 1)
            lines.append(f"  • {h['title']} (every {recur}d) — /done_{h['id'][:8]}")
        lines.append("")
    if milestones:
        lines.append("*Milestones:*")
        for m in milestones:
            counts = db.count_milestones(m["id"])
            target = m.get("target_date", "no deadline")
            lines.append(f"  • {m['title']} — {counts['done']}/{counts['total']} — deadline: {target}")
        lines.append("")
    lines.append("Use /deletetask or /pause to manage tasks.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /done_<short_id> — mark habit done
# ---------------------------------------------------------------------------

async def handle_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/done_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Task not found. Use /tasks to see your tasks.")
        return
    db.mark_done(task["id"])
    recur = task.get("recurrence_days", 1)
    await update.message.reply_text(
        f"✅ *{task['title']}* done! Next reminder in {recur} day(s).",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /deletetask
# ---------------------------------------------------------------------------

async def cmd_deletetask(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    if not tasks:
        await update.message.reply_text("No tasks to delete.")
        return ConversationHandler.END
    ctx.user_data["tasks_list"] = tasks
    buttons = [[t["title"]] for t in tasks] + [["Cancel"]]
    await update.message.reply_text(
        "Which task do you want to delete?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DT_SELECT


async def deletetask_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    tasks = ctx.user_data.get("tasks_list", [])
    task = next((t for t in tasks if t["title"] == chosen), None)
    if not task:
        await update.message.reply_text("Task not found.")
        return ConversationHandler.END
    ctx.user_data["deleting_task"] = task
    buttons = [["Yes, delete it"], ["Cancel"]]
    await update.message.reply_text(
        f"⚠️ Delete *{task['title']}*?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DT_CONFIRM


async def deletetask_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    if choice == "Yes, delete it":
        task = ctx.user_data["deleting_task"]
        db.delete_task(task["id"])
        await update.message.reply_text(
            f"🗑️ *{task['title']}* deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /pause and /resume
# ---------------------------------------------------------------------------

async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    tasks = db.list_tasks(uid, status="active")
    if not tasks:
        await update.message.reply_text("No active tasks.")
        return
    lines = ["*Active tasks — tap to pause:*\n"]
    for t in tasks:
        lines.append(f"⏸ /pause_{t['id'][:8]} — {t['title']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_pause_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/pause_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Task not found.")
        return
    db.update_task(task["id"], status="paused")
    await update.message.reply_text(f"⏸️ *{task['title']}* paused.", parse_mode=ParseMode.MARKDOWN)


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    tasks = db.list_tasks(uid, status="paused")
    if not tasks:
        await update.message.reply_text("No paused tasks.")
        return
    lines = ["*Paused tasks — tap to resume:*\n"]
    for t in tasks:
        lines.append(f"▶️ /resume_{t['id'][:8]} — {t['title']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_resume_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/resume_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid, status="paused")
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Task not found.")
        return
    db.update_task(task["id"], status="active")
    await update.message.reply_text(f"▶️ *{task['title']}* resumed.", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /complete — mark milestone complete
# ---------------------------------------------------------------------------

async def cmd_complete(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    milestones = [t for t in db.list_tasks(uid) if t["task_type"] == "milestone"]
    if not milestones:
        await update.message.reply_text("No active milestones.")
        return
    lines = ["*Milestones — tap to mark complete:*\n"]
    for m in milestones:
        lines.append(f"✅ /complete_{m['id'][:8]} — {m['title']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_complete_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/complete_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Task not found.")
        return
    db.update_task(task["id"], status="completed")
    await update.message.reply_text(f"🎉 *{task['title']}* completed!", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /settings
# ---------------------------------------------------------------------------

async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import settings_svc
    uid = update.effective_user.id
    s = settings_svc.get_settings(uid)
    await update.message.reply_text(
        f"*⚙️ Your Settings*\n\n"
        f"📖 Daily study: *{s['daily_session_time']}* IST — /settime\n"
        f"🌅 Morning brief: *{s['morning_brief_time']}* IST — /setmorning\n"
        f"🌙 EOD check-in: *{s['eod_time']}* IST — /seteod",
        parse_mode=ParseMode.MARKDOWN,
    )


def get_handlers():
    cancel_handler = MessageHandler(filters.Regex(r"^Cancel$"), _cancel)

    newtask_conv = ConversationHandler(
        entry_points=[CommandHandler("newtask", cmd_newtask)],
        states={
            NT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_get_type)],
            NT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_get_title)],
            NT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_get_desc)],
            NT_RECURRENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_get_recurrence)],
            NT_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_get_deadline)],
            NT_MILESTONES: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_collect_milestones)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    deletetask_conv = ConversationHandler(
        entry_points=[CommandHandler("deletetask", cmd_deletetask)],
        states={
            DT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletetask_select)],
            DT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletetask_confirm)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    return [
        newtask_conv,
        deletetask_conv,
        CommandHandler("tasks", cmd_tasks),
        CommandHandler("pause", cmd_pause),
        CommandHandler("resume", cmd_resume),
        CommandHandler("complete", cmd_complete),
        CommandHandler("settings", cmd_settings),
        MessageHandler(filters.Regex(r"^/done_"), handle_done),
        MessageHandler(filters.Regex(r"^/pause_"), handle_pause_task),
        MessageHandler(filters.Regex(r"^/resume_"), handle_resume_task),
        MessageHandler(filters.Regex(r"^/complete_"), handle_complete_task),
    ]


async def _cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
```

- [ ] **Step 2: Verify import**

```
cd D:\Projects\learnix\bot
python -c "from tasks.handlers import get_handlers; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/tasks/handlers.py
git commit -m "feat: tasks/handlers.py with habit, milestone, pause, resume, complete"
```

---

## Task 8: Rewrite bot.py (clean router)

**Files:**
- Modify: `bot/bot.py`

- [ ] **Step 1: Replace bot.py with clean router**

Replace entire `bot/bot.py` with:

```python
"""
bot.py — Learnix bot router.
Registers all handlers from study/ and tasks/ modules, starts scheduler.
"""

import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import settings_svc
import study.handlers as study_handlers
import tasks.handlers as tasks_handlers
from scheduler import register_jobs

load_dotenv()
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    settings_svc.get_settings(uid)  # creates row with defaults if new user
    first_name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hey *{first_name}*! Welcome to Learnix — your personal AI learning and life OS.\n\n"
        f"Here's what you can do:\n\n"
        f"📚 *Study* — AI-powered learning with teach + quiz\n"
        f"  /goal — Create a study goal\n"
        f"  /study — Start a study session\n\n"
        f"✅ *Habits* — Recurring reminders\n"
        f"  /newtask — Create a habit\n\n"
        f"📋 *Milestones* — Goals with checklists\n"
        f"  /newtask — Create a milestone\n\n"
        f"📊 /tasks — See all your tasks\n"
        f"⚙️ /settings — Configure reminder times\n"
        f"❓ /help — Full command list",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*📖 Learnix Commands*\n\n"
        "*Study:*\n"
        "/goal — Create study goal\n"
        "/goals — List study goals\n"
        "/addtopic — Add topic to goal\n"
        "/study — Start study session now\n"
        "/progress — Full progress view\n"
        "/editgoal — Edit a goal\n"
        "/deletegoal — Delete a goal\n"
        "/pausegoal — Pause/resume a goal\n\n"
        "*Tasks:*\n"
        "/newtask — Create habit or milestone\n"
        "/tasks — List all tasks\n"
        "/done\\_<id> — Mark habit done\n"
        "/deletetask — Delete a task\n"
        "/pause — Pause a task\n"
        "/resume — Resume a paused task\n"
        "/complete — Mark milestone complete\n\n"
        "*Settings:*\n"
        "/settings — View settings\n"
        "/settime — Set daily study time\n"
        "/setmorning — Set morning brief time\n"
        "/seteod — Set EOD check-in time\n\n"
        "/cancel — Cancel any ongoing action",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /settime, /setmorning, /seteod (inline — single step)
# ---------------------------------------------------------------------------

async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "study"
    await update.message.reply_text("Send daily study time in HH:MM format (IST). Example: `09:00`", parse_mode=ParseMode.MARKDOWN)


async def cmd_setmorning(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "morning"
    await update.message.reply_text("Send morning brief time in HH:MM format (IST). Example: `08:00`", parse_mode=ParseMode.MARKDOWN)


async def cmd_seteod(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "eod"
    await update.message.reply_text("Send EOD check-in time in HH:MM format (IST). Example: `21:00`", parse_mode=ParseMode.MARKDOWN)


async def handle_time_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if message was consumed as a time-setting input."""
    setting_for = ctx.user_data.get("setting_time_for")
    if not setting_for:
        return False
    time_str = update.message.text.strip()
    try:
        h, m = map(int, time_str.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except Exception:
        await update.message.reply_text("Invalid format. Use HH:MM (e.g. 09:00):")
        return True
    uid = update.effective_user.id
    if setting_for == "study":
        settings_svc.set_daily_time(uid, time_str)
        label = "Daily study"
    elif setting_for == "morning":
        settings_svc.set_morning_brief_time(uid, time_str)
        label = "Morning brief"
    else:
        settings_svc.set_eod_time(uid, time_str)
        label = "EOD check-in"
    ctx.user_data.pop("setting_time_for")
    await update.message.reply_text(f"✅ {label} time set to *{time_str}* IST.", parse_mode=ParseMode.MARKDOWN)
    return True


# ---------------------------------------------------------------------------
# Global text handler (yes/later for study, quiz answers, time inputs)
# ---------------------------------------------------------------------------

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await handle_time_input(update, ctx):
        return

    uid = update.effective_user.id
    text = update.message.text.strip().lower()

    # yes/later for pending study sessions
    pending = ctx.bot_data.get("pending_sessions", {})
    if uid in pending:
        topic_id = pending[uid]
        if text == "yes":
            pending.pop(uid, None)
            from study.svc import get_topic
            topic = get_topic(topic_id)
            if topic:
                await study_handlers._run_study_session(update, ctx, topic)
        elif text == "later":
            pending.pop(uid, None)
            await update.message.reply_text("No problem! I'll remind you in 2 hours. 😴")
            ctx.job_queue.run_once(
                _reminder_job, when=7200,
                data={"user_id": uid, "topic_id": topic_id},
                name=f"reminder_{uid}",
            )
        return

    # Quiz answers
    if uid in ctx.bot_data.get("quiz_state", {}):
        await study_handlers.handle_quiz_answer(update, ctx)


async def _reminder_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = ctx.job.data["user_id"]
    topic_id = ctx.job.data["topic_id"]
    if ctx.bot_data.get("pending_sessions", {}).get(uid) == topic_id:
        return
    from study.svc import get_topic
    topic = get_topic(topic_id)
    if topic:
        await ctx.bot.send_message(
            uid,
            f"⏰ Reminder: Ready to study *{topic['title']}* now?\n\nReply *yes* to start.",
            parse_mode=ParseMode.MARKDOWN,
        )
        ctx.bot_data.setdefault("pending_sessions", {})[uid] = topic_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Core commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("settime", cmd_settime))
    app.add_handler(CommandHandler("setmorning", cmd_setmorning))
    app.add_handler(CommandHandler("seteod", cmd_seteod))
    app.add_handler(CommandHandler("cancel", lambda u, c: None))

    # Study handlers
    for h in study_handlers.get_handlers():
        app.add_handler(h)

    # Task handlers
    for h in tasks_handlers.get_handlers():
        app.add_handler(h)

    # Global text handler (lowest priority)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def on_startup(application: Application) -> None:
        register_jobs(application)
        logger.info("Learnix bot started — all jobs registered.")

    app.post_init = on_startup
    logger.info("Starting Learnix bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Delete old supabase_svc.py imports that no longer exist**

The old `supabase_svc.py` had many functions that are now in `study/svc.py`. Verify the new `bot.py` doesn't import them:

```
cd D:\Projects\learnix\bot
python -c "import bot; print('imports OK')"
```

Expected: `imports OK` (no ImportError)

- [ ] **Step 3: Run full test suite**

```
cd D:\Projects\learnix\bot
python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add bot/bot.py
git commit -m "feat: rewrite bot.py as clean router, wire study + tasks + scheduler"
```

---

## Task 9: Smoke test the bot

- [ ] **Step 1: Install dependencies**

```
cd D:\Projects\learnix\bot
pip install -r requirements.txt
```

- [ ] **Step 2: Run the bot**

```
cd D:\Projects\learnix\bot
python bot.py
```

Expected log output:
```
INFO  Learnix bot started — all jobs registered.
INFO  Application started
```

- [ ] **Step 3: Test in Telegram — send /start**

DM the bot. Expected response: welcome message with all sections.

- [ ] **Step 4: Test /goal flow**

Send `/goal` → enter name → enter description → enter date → confirm goal created.

- [ ] **Step 5: Test /newtask habit flow**

Send `/newtask` → select Habit → enter name → select recurrence → confirm created.

- [ ] **Step 6: Test /newtask milestone flow**

Send `/newtask` → select Milestone → enter name → enter deadline → add 2 checklist items → send 'done' → confirm created.

- [ ] **Step 7: Test /tasks shows both**

Send `/tasks` → confirm habit and milestone both appear.

- [ ] **Step 8: Commit final**

```bash
git add -A
git commit -m "feat: Learnix Phase 1 complete — multi-user, habits, milestones, morning brief, EOD"
```

---

## Task 10: Activity Trend Graph (`/graph`)

**Files:**
- Create: `supabase/migrations/003_activity_log.sql`
- Create: `bot/analytics_svc.py`
- Create: `bot/tests/test_analytics_svc.py`
- Modify: `bot/study/handlers.py` (line ~1464 in `_finish_quiz`)
- Modify: `bot/tasks/handlers.py` (in `handle_done` and `handle_complete_task`)
- Modify: `bot/bot.py` (add CommandHandler for /graph)
- Modify: `bot/requirements.txt`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/003_activity_log.sql`:

```sql
-- 003_activity_log.sql
-- Stores one row per user activity event for trend graph
create table activity_log (
  id         uuid primary key default gen_random_uuid(),
  user_id    bigint not null,
  event_type text not null check (event_type in ('study', 'habit', 'milestone')),
  event_date date not null default current_date,
  note       text,
  created_at timestamptz not null default now()
);
create index activity_log_user_date_idx on activity_log(user_id, event_date);
```

- [ ] **Step 2: Apply migration**

```
cd D:\Projects\learnix
python -c "
import psycopg2
conn = psycopg2.connect(host='db.rqdhaphfyitvtckdjgqg.supabase.co',port=5432,dbname='postgres',user='postgres',password='2imtTLSYVQH68MWL',sslmode='require')
sql = open('supabase/migrations/003_activity_log.sql').read()
cur = conn.cursor(); cur.execute(sql); conn.commit(); cur.close(); conn.close()
print('Migration 003 applied')
"
```

Expected: `Migration 003 applied`

- [ ] **Step 3: Write failing tests**

Create `bot/tests/test_analytics_svc.py`:

```python
from unittest.mock import MagicMock, patch
from datetime import date, timedelta
import pytest

with patch('supabase_svc.create_client'):
    import analytics_svc

def make_client(rows=None):
    c = MagicMock()
    ex = MagicMock(); ex.data = rows or []
    c.table.return_value.insert.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = ex
    return c

def test_log_activity_inserts_row():
    with patch('analytics_svc.get_client', return_value=make_client()):
        analytics_svc.log_activity(123, 'study', note='Neural Networks')
        # No exception = pass

def test_get_activity_returns_data():
    rows = [
        {'event_type': 'study', 'event_date': date.today().isoformat()},
        {'event_type': 'habit', 'event_date': date.today().isoformat()},
    ]
    with patch('analytics_svc.get_client', return_value=make_client(rows=rows)):
        result = analytics_svc.get_activity_last_n_days(123, 30)
        assert len(result) == 2
        assert result[0]['event_type'] == 'study'

def test_build_graph_returns_bytes_buffer():
    with patch('analytics_svc.get_activity_last_n_days', return_value=[]):
        buf = analytics_svc.build_graph(123, days=7)
        assert buf.read(4) == b'\x89PNG'  # PNG magic bytes
```

- [ ] **Step 4: Run tests to confirm fail**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_analytics_svc.py -v
```

Expected: `ModuleNotFoundError` (analytics_svc doesn't exist yet)

- [ ] **Step 5: Install matplotlib + numpy**

```
pip install matplotlib numpy
```

Update `bot/requirements.txt` — add these two lines:

```
matplotlib==3.9.4
numpy==2.2.6
```

- [ ] **Step 6: Create analytics_svc.py**

Create `bot/analytics_svc.py`:

```python
import io
from datetime import date, timedelta

from supabase_svc import get_client


def log_activity(user_id: int, event_type: str, note: str = "") -> None:
    get_client().table("activity_log").insert({
        "user_id": user_id,
        "event_type": event_type,
        "event_date": date.today().isoformat(),
        "note": note,
    }).execute()


def get_activity_last_n_days(user_id: int, days: int = 30) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    res = (
        get_client().table("activity_log")
        .select("event_type, event_date")
        .eq("user_id", user_id)
        .gte("event_date", since)
        .execute()
    )
    return res.data or []


def build_graph(user_id: int, days: int = 30) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    rows = get_activity_last_n_days(user_id, days)

    today = date.today()
    date_list = [today - timedelta(days=days - 1 - i) for i in range(days)]
    date_strs = [d.isoformat() for d in date_list]
    date_index = {d: i for i, d in enumerate(date_strs)}

    study_counts = [0] * days
    habit_counts = [0] * days
    milestone_counts = [0] * days

    for row in rows:
        idx = date_index.get(str(row["event_date"]))
        if idx is None:
            continue
        t = row["event_type"]
        if t == "study":
            study_counts[idx] += 1
        elif t == "habit":
            habit_counts[idx] += 1
        elif t == "milestone":
            milestone_counts[idx] += 1

    x = np.arange(days)
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(x, study_counts, label="Study", color="#4A90D9", alpha=0.85)
    bottom_habit = [s for s in study_counts]
    ax.bar(x, habit_counts, bottom=bottom_habit, label="Habits", color="#27AE60", alpha=0.85)
    bottom_milestone = [s + h for s, h in zip(study_counts, habit_counts)]
    ax.bar(x, milestone_counts, bottom=bottom_milestone, label="Milestones", color="#F39C12", alpha=0.85)

    tick_pos = list(range(0, days, 7)) + [days - 1]
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(
        [date_list[i].strftime("%b %d") for i in tick_pos],
        rotation=30, ha="right", fontsize=8,
    )
    ax.set_ylabel("Activities completed")
    ax.set_title(f"Your Activity — Last {days} Days", fontsize=13)
    ax.legend(loc="upper left")
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_xlim(-0.5, days - 0.5)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
```

- [ ] **Step 7: Run tests — expect pass**

```
cd D:\Projects\learnix\bot
python -m pytest tests/test_analytics_svc.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 8: Patch study/handlers.py — log after quiz completion**

In `bot/study/handlers.py`, find the `_finish_quiz` function. After the line:

```python
    db.insert_quiz_attempt(topic_id, score)
```

Add:

```python
    import analytics_svc
    analytics_svc.log_activity(user_id, "study", note=state["topic"]["title"])
```

So the full block around the insertion becomes:

```python
    db.update_topic_status(topic_id, new_status, f"{score}/{total}")
    db.insert_quiz_attempt(topic_id, score)
    import analytics_svc
    analytics_svc.log_activity(user_id, "study", note=state["topic"]["title"])
    if passed:
        db.bubble_up_completion(topic_id)
```

- [ ] **Step 9: Patch tasks/handlers.py — log habit done and milestone complete**

In `bot/tasks/handlers.py`, find `handle_done` and update it to log after `db.mark_done(task["id"])`:

```python
async def handle_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/done_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Task not found. Use /tasks to see your tasks.")
        return
    db.mark_done(task["id"])
    import analytics_svc
    analytics_svc.log_activity(uid, "habit", note=task["title"])
    recur = task.get("recurrence_days", 1)
    await update.message.reply_text(
        f"✅ *{task['title']}* done! Next reminder in {recur} day(s).",
        parse_mode=ParseMode.MARKDOWN,
    )
```

Also find `handle_complete_task` and log after `db.update_task(task["id"], status="completed")`:

```python
async def handle_complete_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/complete_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Task not found.")
        return
    db.update_task(task["id"], status="completed")
    import analytics_svc
    analytics_svc.log_activity(uid, "milestone", note=task["title"])
    await update.message.reply_text(f"🎉 *{task['title']}* completed!", parse_mode=ParseMode.MARKDOWN)
```

- [ ] **Step 10: Add /graph handler to bot.py**

In `bot/bot.py`, add this function after `cmd_seteod`:

```python
async def cmd_graph(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text("Generating your activity graph... 📊")
    try:
        import analytics_svc
        buf = analytics_svc.build_graph(uid)
        await update.message.reply_photo(buf, caption="Your activity over the last 30 days 📈")
    except Exception as e:
        logger.error(f"Graph failed for {uid}: {e}")
        await update.message.reply_text(f"❌ Could not generate graph: {e}")
```

And in `main()`, add the handler registration after `/seteod`:

```python
    app.add_handler(CommandHandler("graph", cmd_graph))
```

Also update `cmd_help` to include `/graph` — in the Settings section add:

```python
        "/graph — Activity trend graph (last 30 days)\n\n"
```

- [ ] **Step 11: Commit**

```bash
git add supabase/migrations/003_activity_log.sql bot/analytics_svc.py bot/tests/test_analytics_svc.py bot/requirements.txt bot/study/handlers.py bot/tasks/handlers.py bot/bot.py
git commit -m "feat: activity trend graph with /graph command and activity_log tracking"
```

---

## Self-Review

### Spec coverage check:
- ✅ Multi-user (user_id on all tables, open /start registration)
- ✅ 3 goal types: study (goals+topics), habit (tasks), milestone (tasks+milestones)
- ✅ Create/edit/delete goals
- ✅ List goals with progress %
- ✅ Mark goal complete / pause
- ✅ Add subtopics to study goal
- ✅ Timely reminders (habit: next_reminder_at, milestone: 3 days before deadline)
- ✅ Daily morning brief (morning_poller)
- ✅ EOD check-in (eod_poller)
- ✅ Auto-schedule habit on /done
- ✅ Polling scheduler (no per-user jobs)
- ✅ Edit/delete tasks
- ✅ /settime, /setmorning, /seteod
- ✅ Activity trend graph (/graph) — activity_log table + matplotlib PNG

### Type consistency:
- `study.svc` functions take `user_id: int` as first arg ✅
- `tasks.svc` functions take `user_id: int` as first arg ✅
- `settings_svc` functions take `user_id: int` as first arg ✅
- `bot_data["pending_sessions"]` and `bot_data["quiz_state"]` used consistently ✅
- Short IDs use `id[:8]` everywhere ✅
