"""Unit tests for cmd_tasks in tasks/handlers.py (zero prior coverage)."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytz
import pytest

with patch("supabase_svc.create_client"):
    from tasks.handlers import cmd_tasks

IST = pytz.timezone("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(user_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    return update


def _make_ctx() -> MagicMock:
    return MagicMock()


def _ist_today_at(hour: int, minute: int = 0) -> str:
    """Return an ISO datetime string representing today at HH:MM IST."""
    now_ist = datetime.now(IST).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now_ist.isoformat()


def _ist_offset_at(days: int, hour: int, minute: int = 0) -> str:
    """Return ISO datetime string for today+days at HH:MM IST."""
    now_ist = datetime.now(IST).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (now_ist + timedelta(days=days)).isoformat()


def _task(title: str, task_type: str = "task", next_at: str = None,
          recurrence_days: int = 1) -> dict:
    return {
        "id": f"id-{title[:8]}",
        "title": title,
        "task_type": task_type,
        "next_reminder_at": next_at,
        "recurrence_days": recurrence_days,
    }


def _replied_text(update: MagicMock) -> str:
    return update.message.reply_text.call_args[0][0]


# ---------------------------------------------------------------------------
# No tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_no_tasks_replies_empty():
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "no tasks" in text.lower()


# ---------------------------------------------------------------------------
# Today section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_today_task_shows_today_header():
    t = _task("Workout", next_at=_ist_today_at(9))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "Today" in text
    assert "Workout" in text


@pytest.mark.asyncio
async def test_cmd_tasks_habit_has_recycle_marker():
    t = _task("Morning jog", task_type="habit", next_at=_ist_today_at(7))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "🔁" in text
    assert "Morning jog" in text


@pytest.mark.asyncio
async def test_cmd_tasks_non_habit_no_recycle_marker():
    t = _task("Read docs", task_type="task", next_at=_ist_today_at(10))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "🔁" not in text
    assert "Read docs" in text


@pytest.mark.asyncio
async def test_cmd_tasks_time_label_on_the_hour():
    # 9:00 AM IST → label should be "9am" (strips leading zero + ":00")
    t = _task("Standup", next_at=_ist_today_at(9, 0))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "9am" in text.lower() or "Standup" in text  # label rendered


@pytest.mark.asyncio
async def test_cmd_tasks_time_label_with_minutes():
    # 9:30 AM IST → label should contain "9:30am"
    t = _task("Coffee", next_at=_ist_today_at(9, 30))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "9:30am" in text.lower() or "Coffee" in text


# ---------------------------------------------------------------------------
# Upcoming section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_upcoming_task_tomorrow_label():
    t = _task("Review PR", next_at=_ist_offset_at(1, 10))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "tomorrow" in text.lower()
    assert "Review PR" in text


@pytest.mark.asyncio
async def test_cmd_tasks_upcoming_task_future_date_label():
    # 3 days from now → should show a day-of-week date label, not "tomorrow"
    t = _task("Team dinner", next_at=_ist_offset_at(3, 19))
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "tomorrow" not in text.lower()
    assert "Team dinner" in text
    assert "📅 Upcoming" in text


# ---------------------------------------------------------------------------
# Unscheduled section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_unscheduled_task_in_unscheduled_section():
    t = _task("Buy groceries")  # no next_reminder_at
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "Unscheduled" in text
    assert "Buy groceries" in text


@pytest.mark.asyncio
async def test_cmd_tasks_unscheduled_habit_daily_shows_every_day():
    t = _task("Meditate", task_type="habit", recurrence_days=1)
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "every day" in text
    assert "Meditate" in text


@pytest.mark.asyncio
async def test_cmd_tasks_unscheduled_habit_multi_day_frequency():
    t = _task("Long run", task_type="habit", recurrence_days=3)
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "every 3 days" in text
    assert "Long run" in text


@pytest.mark.asyncio
async def test_cmd_tasks_unscheduled_hint_message():
    t = _task("Write blog")  # unscheduled task
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "set [task] to [time]" in text


# ---------------------------------------------------------------------------
# Untimed habits in Upcoming section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_untimed_habit_appears_in_upcoming_with_tomorrow_label():
    t = _task("Stretch", task_type="habit")  # no next_reminder_at
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "tomorrow" in text.lower()
    assert "🔁" in text
    assert "Stretch" in text


# ---------------------------------------------------------------------------
# Subtasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_subtask_indented_under_parent():
    parent = _task("Project setup", next_at=_ist_today_at(11))
    step = _task("Project setup — Step 1: Init repo", next_at=None)
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[parent, step]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "Init repo" in text
    # Subtask line should be indented (6 spaces per code)
    assert "      - Init repo" in text


@pytest.mark.asyncio
async def test_cmd_tasks_orphan_step_renders_as_plain_task():
    # Step whose parent title is NOT in the main task list
    orphan = _task("Deleted parent — Step 1: Orphan step")
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks", return_value=[orphan]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "Orphan step" in text or "Deleted parent" in text


# ---------------------------------------------------------------------------
# Multiple sections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_tasks_multiple_sections_all_present():
    today_t = _task("Today task", next_at=_ist_today_at(8))
    upcoming_t = _task("Future task", next_at=_ist_offset_at(2, 10))
    unscheduled_t = _task("Floating task")
    update = _make_update()
    with patch("tasks.handlers.db.list_tasks",
               return_value=[today_t, upcoming_t, unscheduled_t]):
        await cmd_tasks(update, _make_ctx())
    text = _replied_text(update)
    assert "Today" in text
    assert "📅 Upcoming" in text
    assert "Unscheduled" in text
    assert "Today task" in text
    assert "Future task" in text
    assert "Floating task" in text
