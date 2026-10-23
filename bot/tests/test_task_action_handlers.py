"""
Tests for cmd_pause, handle_pause_task, cmd_resume, handle_resume_task,
cmd_complete, handle_complete_task, and handle_done in tasks/handlers.py.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

with patch("supabase_svc.create_client"):
    from tasks.handlers import (
        cmd_pause,
        handle_pause_task,
        cmd_resume,
        handle_resume_task,
        cmd_complete,
        handle_complete_task,
        handle_done,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(text: str, user_id: int = 7) -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id
    return update


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


HABIT = {"id": "abc12345", "title": "Morning Workout", "task_type": "habit", "recurrence_days": 1}
MILESTONE = {"id": "def67890", "title": "Launch MVP", "task_type": "milestone", "recurrence_days": None}


# ---------------------------------------------------------------------------
# cmd_pause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_pause_no_tasks_replies_empty():
    update = _make_update("/pause")
    with patch("tasks.handlers.db.list_tasks", return_value=[]):
        await cmd_pause(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "no active" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_pause_lists_active_tasks_with_shortids():
    update = _make_update("/pause")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]):
        await cmd_pause(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply
    assert "/pause_abc123" in reply  # first 8 chars of "abc12345"


@pytest.mark.asyncio
async def test_cmd_pause_queries_active_status():
    update = _make_update("/pause")
    with patch("tasks.handlers.db.list_tasks", return_value=[]) as mock_list:
        await cmd_pause(update, _make_ctx())
    mock_list.assert_called_once_with(7, status="active")


# ---------------------------------------------------------------------------
# handle_pause_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_pause_task_found_pauses_and_replies():
    update = _make_update("/pause_abc123")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]), \
         patch("tasks.handlers.db.update_task") as mock_update:
        await handle_pause_task(update, _make_ctx())
    mock_update.assert_called_once_with("abc12345", status="paused")
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply


@pytest.mark.asyncio
async def test_handle_pause_task_not_found_replies_error():
    update = _make_update("/pause_xyz00000")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]), \
         patch("tasks.handlers.db.update_task") as mock_update:
        await handle_pause_task(update, _make_ctx())
    mock_update.assert_not_called()
    reply = update.message.reply_text.call_args[0][0]
    assert "can't find" in reply.lower()


@pytest.mark.asyncio
async def test_handle_pause_task_prefix_match():
    update = _make_update("/pause_abc1")  # prefix of "abc12345"
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]), \
         patch("tasks.handlers.db.update_task") as mock_update:
        await handle_pause_task(update, _make_ctx())
    mock_update.assert_called_once_with("abc12345", status="paused")


# ---------------------------------------------------------------------------
# cmd_resume
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_resume_no_paused_replies_empty():
    update = _make_update("/resume")
    with patch("tasks.handlers.db.list_tasks", return_value=[]):
        await cmd_resume(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "nothing" in reply.lower() or "paused" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_resume_lists_paused_tasks():
    update = _make_update("/resume")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]):
        await cmd_resume(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply
    assert "/resume_abc123" in reply


@pytest.mark.asyncio
async def test_cmd_resume_queries_paused_status():
    update = _make_update("/resume")
    with patch("tasks.handlers.db.list_tasks", return_value=[]) as mock_list:
        await cmd_resume(update, _make_ctx())
    mock_list.assert_called_once_with(7, status="paused")


# ---------------------------------------------------------------------------
# handle_resume_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_resume_task_found_activates_and_replies():
    update = _make_update("/resume_abc123")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]), \
         patch("tasks.handlers.db.update_task") as mock_update:
        await handle_resume_task(update, _make_ctx())
    mock_update.assert_called_once_with("abc12345", status="active")
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply


@pytest.mark.asyncio
async def test_handle_resume_task_not_found_replies_error():
    update = _make_update("/resume_xyz00000")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]), \
         patch("tasks.handlers.db.update_task") as mock_update:
        await handle_resume_task(update, _make_ctx())
    mock_update.assert_not_called()
    reply = update.message.reply_text.call_args[0][0]
    assert "can't find" in reply.lower()


# ---------------------------------------------------------------------------
# cmd_complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_complete_no_milestones_replies_empty():
    update = _make_update("/complete")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT]):
        await cmd_complete(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "no active milestones" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_complete_lists_milestones_only():
    update = _make_update("/complete")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT, MILESTONE]):
        await cmd_complete(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "Launch MVP" in reply
    assert "Morning Workout" not in reply  # habits excluded


@pytest.mark.asyncio
async def test_cmd_complete_shows_shortid_links():
    update = _make_update("/complete")
    with patch("tasks.handlers.db.list_tasks", return_value=[MILESTONE]):
        await cmd_complete(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "/complete_def67890" in reply


# ---------------------------------------------------------------------------
# handle_complete_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_complete_task_found_marks_completed():
    update = _make_update("/complete_def6789")
    with patch("tasks.handlers.db.list_tasks", return_value=[MILESTONE]), \
         patch("tasks.handlers.db.update_task") as mock_update, \
         patch("tasks.handlers.analytics_svc.log_activity") if False else \
         patch("analytics_svc.log_activity") as mock_log:
        await handle_complete_task(update, _make_ctx())
    mock_update.assert_called_once_with("def67890", status="completed")


@pytest.mark.asyncio
async def test_handle_complete_task_logs_milestone_activity():
    update = _make_update("/complete_def6789")
    with patch("tasks.handlers.db.list_tasks", return_value=[MILESTONE]), \
         patch("tasks.handlers.db.update_task"), \
         patch("analytics_svc.log_activity") as mock_log:
        await handle_complete_task(update, _make_ctx())
    mock_log.assert_called_once_with(7, "milestone", note="Launch MVP")


@pytest.mark.asyncio
async def test_handle_complete_task_reply_includes_title():
    update = _make_update("/complete_def6789")
    with patch("tasks.handlers.db.list_tasks", return_value=[MILESTONE]), \
         patch("tasks.handlers.db.update_task"), \
         patch("analytics_svc.log_activity"):
        await handle_complete_task(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "Launch MVP" in reply


@pytest.mark.asyncio
async def test_handle_complete_task_not_found_replies_error():
    update = _make_update("/complete_xxxxxx")
    with patch("tasks.handlers.db.list_tasks", return_value=[MILESTONE]), \
         patch("tasks.handlers.db.update_task") as mock_update:
        await handle_complete_task(update, _make_ctx())
    mock_update.assert_not_called()
    reply = update.message.reply_text.call_args[0][0]
    assert "can't find" in reply.lower()


# ---------------------------------------------------------------------------
# handle_done
# ---------------------------------------------------------------------------

HABIT_WITH_RECUR = {"id": "abc12345", "title": "Morning Workout", "task_type": "habit", "recurrence_days": 2}


@pytest.mark.asyncio
async def test_handle_done_marks_task_done():
    update = _make_update("/done_abc123")
    settings = {"streak": 3, "daily_session_time": "09:00"}
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT_WITH_RECUR]), \
         patch("tasks.handlers.db.mark_done") as mock_done, \
         patch("analytics_svc.log_activity"), \
         patch("settings_svc.update_streak"), \
         patch("settings_svc.get_settings", return_value=settings):
        await handle_done(update, _make_ctx())
    mock_done.assert_called_once_with("abc12345")


@pytest.mark.asyncio
async def test_handle_done_logs_habit_activity():
    update = _make_update("/done_abc123")
    settings = {"streak": 1, "daily_session_time": "09:00"}
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT_WITH_RECUR]), \
         patch("tasks.handlers.db.mark_done"), \
         patch("analytics_svc.log_activity") as mock_log, \
         patch("settings_svc.update_streak"), \
         patch("settings_svc.get_settings", return_value=settings):
        await handle_done(update, _make_ctx())
    mock_log.assert_called_once_with(7, "habit", note="Morning Workout")


@pytest.mark.asyncio
async def test_handle_done_reply_shows_recurrence_days():
    update = _make_update("/done_abc123")
    settings = {"streak": 5, "daily_session_time": "09:00"}
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT_WITH_RECUR]), \
         patch("tasks.handlers.db.mark_done"), \
         patch("analytics_svc.log_activity"), \
         patch("settings_svc.update_streak"), \
         patch("settings_svc.get_settings", return_value=settings):
        await handle_done(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "2 day" in reply
    assert "Morning Workout" in reply


@pytest.mark.asyncio
async def test_handle_done_shows_streak_when_greater_than_one():
    update = _make_update("/done_abc123")
    settings = {"streak": 5, "daily_session_time": "09:00"}
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT_WITH_RECUR]), \
         patch("tasks.handlers.db.mark_done"), \
         patch("analytics_svc.log_activity"), \
         patch("settings_svc.update_streak"), \
         patch("settings_svc.get_settings", return_value=settings):
        await handle_done(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "5 day streak" in reply


@pytest.mark.asyncio
async def test_handle_done_no_streak_message_when_streak_is_one():
    update = _make_update("/done_abc123")
    settings = {"streak": 1, "daily_session_time": "09:00"}
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT_WITH_RECUR]), \
         patch("tasks.handlers.db.mark_done"), \
         patch("analytics_svc.log_activity"), \
         patch("settings_svc.update_streak"), \
         patch("settings_svc.get_settings", return_value=settings):
        await handle_done(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "keep it up" in reply.lower()


@pytest.mark.asyncio
async def test_handle_done_not_found_replies_error():
    update = _make_update("/done_xxxxxxxx")
    with patch("tasks.handlers.db.list_tasks", return_value=[HABIT_WITH_RECUR]), \
         patch("tasks.handlers.db.mark_done") as mock_done:
        await handle_done(update, _make_ctx())
    mock_done.assert_not_called()
    reply = update.message.reply_text.call_args[0][0]
    assert "can't find" in reply.lower()
