"""
Tests for cmd_deletetask, deletetask_select, deletetask_confirm,
cmd_settings, and cmd_persona in tasks/handlers.py.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

with patch("supabase_svc.create_client"):
    from tasks.handlers import (
        cmd_deletetask,
        deletetask_select,
        deletetask_confirm,
        cmd_settings,
        cmd_persona,
        DT_SELECT,
        DT_CONFIRM,
    )
from telegram.ext import ConversationHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(text: str, user_id: int = 5) -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id
    return update


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


TASK_A = {"id": "aaa11111", "title": "Walk the dog", "task_type": "habit"}
TASK_B = {"id": "bbb22222", "title": "Read 10 pages", "task_type": "habit"}


# ---------------------------------------------------------------------------
# cmd_deletetask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_deletetask_no_tasks_replies_empty():
    update = _make_update("/deletetask")
    with patch("tasks.handlers.db.list_tasks", return_value=[]):
        result = await cmd_deletetask(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "no tasks" in reply.lower()
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_cmd_deletetask_shows_task_titles():
    update = _make_update("/deletetask")
    ctx = _make_ctx()
    with patch("tasks.handlers.db.list_tasks", return_value=[TASK_A, TASK_B]):
        result = await cmd_deletetask(update, ctx)
    assert result == DT_SELECT
    assert ctx.user_data["tasks_list"] == [TASK_A, TASK_B]


@pytest.mark.asyncio
async def test_cmd_deletetask_stores_tasks_in_user_data():
    update = _make_update("/deletetask", user_id=42)
    ctx = _make_ctx()
    with patch("tasks.handlers.db.list_tasks", return_value=[TASK_A]) as mock_list:
        await cmd_deletetask(update, ctx)
    mock_list.assert_called_once_with(42)
    assert ctx.user_data["tasks_list"] == [TASK_A]


# ---------------------------------------------------------------------------
# deletetask_select
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deletetask_select_found_stores_task_and_asks_confirm():
    update = _make_update("Walk the dog")
    ctx = _make_ctx()
    ctx.user_data["tasks_list"] = [TASK_A, TASK_B]
    result = await deletetask_select(update, ctx)
    assert result == DT_CONFIRM
    assert ctx.user_data["deleting_task"] == TASK_A
    reply = update.message.reply_text.call_args[0][0]
    assert "Walk the dog" in reply


@pytest.mark.asyncio
async def test_deletetask_select_not_found_replies_error():
    update = _make_update("Nonexistent task")
    ctx = _make_ctx()
    ctx.user_data["tasks_list"] = [TASK_A]
    result = await deletetask_select(update, ctx)
    assert result == ConversationHandler.END
    reply = update.message.reply_text.call_args[0][0]
    assert "find" in reply.lower()


@pytest.mark.asyncio
async def test_deletetask_select_empty_list_replies_error():
    update = _make_update("Walk the dog")
    ctx = _make_ctx()
    ctx.user_data["tasks_list"] = []
    result = await deletetask_select(update, ctx)
    assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# deletetask_confirm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deletetask_confirm_yes_deletes_task():
    update = _make_update("Yes, delete it")
    ctx = _make_ctx()
    ctx.user_data["deleting_task"] = TASK_A
    with patch("tasks.handlers.db.delete_task") as mock_delete:
        result = await deletetask_confirm(update, ctx)
    mock_delete.assert_called_once_with("aaa11111")
    assert result == ConversationHandler.END
    assert ctx.user_data == {}


@pytest.mark.asyncio
async def test_deletetask_confirm_yes_reply_contains_title():
    update = _make_update("Yes, delete it")
    ctx = _make_ctx()
    ctx.user_data["deleting_task"] = TASK_A
    with patch("tasks.handlers.db.delete_task"):
        await deletetask_confirm(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "Walk the dog" in reply


@pytest.mark.asyncio
async def test_deletetask_confirm_cancel_keeps_task():
    update = _make_update("Cancel")
    ctx = _make_ctx()
    ctx.user_data["deleting_task"] = TASK_A
    with patch("tasks.handlers.db.delete_task") as mock_delete:
        result = await deletetask_confirm(update, ctx)
    mock_delete.assert_not_called()
    assert result == ConversationHandler.END
    assert ctx.user_data == {}


@pytest.mark.asyncio
async def test_deletetask_confirm_cancel_replies_kept():
    update = _make_update("Cancel")
    ctx = _make_ctx()
    ctx.user_data["deleting_task"] = TASK_A
    with patch("tasks.handlers.db.delete_task"):
        await deletetask_confirm(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "kept" in reply.lower() or "no worries" in reply.lower()


# ---------------------------------------------------------------------------
# cmd_settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_settings_shows_all_fields():
    update = _make_update("/settings")
    s = {
        "daily_session_time": "08:00",
        "morning_brief_time": "07:00",
        "eod_time": "22:00",
        "persona": "default",
    }
    with patch("settings_svc.get_settings", return_value=s), \
         patch("twilio_svc.is_twilio_enabled", return_value=False):
        await cmd_settings(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "08:00" in reply
    assert "07:00" in reply
    assert "22:00" in reply


@pytest.mark.asyncio
async def test_cmd_settings_twilio_on_shows_on():
    update = _make_update("/settings")
    s = {"daily_session_time": "09:00", "morning_brief_time": "07:00",
         "eod_time": "21:00", "persona": "default"}
    with patch("settings_svc.get_settings", return_value=s), \
         patch("twilio_svc.is_twilio_enabled", return_value=True):
        await cmd_settings(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "ON" in reply


@pytest.mark.asyncio
async def test_cmd_settings_twilio_off_shows_off():
    update = _make_update("/settings")
    s = {"daily_session_time": "09:00", "morning_brief_time": "07:00",
         "eod_time": "21:00", "persona": "flirty"}
    with patch("settings_svc.get_settings", return_value=s), \
         patch("twilio_svc.is_twilio_enabled", return_value=False):
        await cmd_settings(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "OFF" in reply


@pytest.mark.asyncio
async def test_cmd_settings_flirty_persona_shows_flirty_label():
    update = _make_update("/settings")
    s = {"daily_session_time": "08:00", "morning_brief_time": "07:30",
         "eod_time": "22:00", "persona": "flirty"}
    with patch("settings_svc.get_settings", return_value=s), \
         patch("twilio_svc.is_twilio_enabled", return_value=False):
        await cmd_settings(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "Flirty" in reply


# ---------------------------------------------------------------------------
# cmd_persona
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_persona_flirty_sets_flirty():
    update = _make_update("/persona flirty", user_id=9)
    with patch("settings_svc.set_persona") as mock_set:
        await cmd_persona(update, _make_ctx())
    mock_set.assert_called_once_with(9, "flirty")
    reply = update.message.reply_text.call_args[0][0]
    assert "flirt" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_persona_sexy_sets_flirty():
    update = _make_update("/persona sexy", user_id=9)
    with patch("settings_svc.set_persona") as mock_set:
        await cmd_persona(update, _make_ctx())
    mock_set.assert_called_once_with(9, "flirty")


@pytest.mark.asyncio
async def test_cmd_persona_normal_sets_default():
    update = _make_update("/persona normal", user_id=11)
    with patch("settings_svc.set_persona") as mock_set:
        await cmd_persona(update, _make_ctx())
    mock_set.assert_called_once_with(11, "default")
    reply = update.message.reply_text.call_args[0][0]
    assert "friendly" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_persona_friendly_sets_default():
    update = _make_update("/persona friendly", user_id=11)
    with patch("settings_svc.set_persona") as mock_set:
        await cmd_persona(update, _make_ctx())
    mock_set.assert_called_once_with(11, "default")


@pytest.mark.asyncio
async def test_cmd_persona_no_arg_shows_current_flirty():
    update = _make_update("/persona", user_id=3)
    with patch("settings_svc.get_persona", return_value="flirty"):
        await cmd_persona(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "flirty" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_persona_no_arg_shows_current_friendly():
    update = _make_update("/persona", user_id=3)
    with patch("settings_svc.get_persona", return_value="default"):
        await cmd_persona(update, _make_ctx())
    reply = update.message.reply_text.call_args[0][0]
    assert "friendly" in reply.lower()


@pytest.mark.asyncio
async def test_cmd_persona_unknown_arg_shows_current():
    update = _make_update("/persona randomword", user_id=3)
    with patch("settings_svc.get_persona", return_value="default") as mock_get:
        await cmd_persona(update, _make_ctx())
    mock_get.assert_called_once_with(3)
