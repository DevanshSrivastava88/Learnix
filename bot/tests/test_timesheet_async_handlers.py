"""
Tests for async handlers in tasks/timesheet_handlers.py:
cmd_timesheet, ts_plan, and _cancel.

All Supabase, Gemini, and skip_time_parser calls are mocked.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

with patch("supabase_svc.create_client"):
    from tasks.timesheet_handlers import cmd_timesheet, ts_plan, _cancel, TS_PLAN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(text: str = "", user_id: int = 7) -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id
    return update


def _make_ctx(user_data: dict = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    return ctx


HABITS = [
    {"id": "h1", "title": "Morning Workout", "task_type": "habit"},
    {"id": "h2", "title": "Read 10 Pages", "task_type": "habit"},
]

TASKS_WITH_NON_HABITS = HABITS + [
    {"id": "t1", "title": "Submit report", "task_type": "milestone"},
]

FUTURE_DT = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# cmd_timesheet
# ---------------------------------------------------------------------------

class TestCmdTimesheet:
    @pytest.mark.asyncio
    async def test_no_habits_sends_message_and_ends(self):
        update = _make_update()
        ctx = _make_ctx()

        with patch("tasks.timesheet_handlers.db.list_tasks", return_value=[]):
            result = await cmd_timesheet(update, ctx)

        assert result == ConversationHandler.END
        update.message.reply_text.assert_awaited_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "no active habits" in reply.lower()

    @pytest.mark.asyncio
    async def test_no_habits_filters_non_habit_tasks(self):
        update = _make_update()
        ctx = _make_ctx()

        non_habit_tasks = [{"id": "t1", "title": "Report", "task_type": "milestone"}]
        with patch("tasks.timesheet_handlers.db.list_tasks", return_value=non_habit_tasks):
            result = await cmd_timesheet(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_with_habits_stores_in_user_data(self):
        update = _make_update()
        ctx = _make_ctx()

        with patch("tasks.timesheet_handlers.db.list_tasks", return_value=HABITS):
            await cmd_timesheet(update, ctx)

        assert ctx.user_data["timesheet_habits"] == HABITS

    @pytest.mark.asyncio
    async def test_with_habits_returns_ts_plan_state(self):
        update = _make_update()
        ctx = _make_ctx()

        with patch("tasks.timesheet_handlers.db.list_tasks", return_value=HABITS):
            result = await cmd_timesheet(update, ctx)

        assert result == TS_PLAN

    @pytest.mark.asyncio
    async def test_with_habits_reply_contains_habit_names(self):
        update = _make_update()
        ctx = _make_ctx()

        with patch("tasks.timesheet_handlers.db.list_tasks", return_value=HABITS):
            await cmd_timesheet(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Morning Workout" in reply
        assert "Read 10 Pages" in reply

    @pytest.mark.asyncio
    async def test_with_habits_only_stores_habit_type(self):
        update = _make_update()
        ctx = _make_ctx()

        with patch("tasks.timesheet_handlers.db.list_tasks", return_value=TASKS_WITH_NON_HABITS):
            await cmd_timesheet(update, ctx)

        stored = ctx.user_data["timesheet_habits"]
        assert all(h["task_type"] == "habit" for h in stored)
        assert len(stored) == 2


# ---------------------------------------------------------------------------
# ts_plan
# ---------------------------------------------------------------------------

class TestTsPlan:
    @pytest.mark.asyncio
    async def test_no_matches_replies_error_and_ends(self):
        update = _make_update("gibberish at whenever")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value={}):
            result = await ts_plan(update, ctx)

        assert result == ConversationHandler.END
        reply = update.message.reply_text.call_args[0][0]
        assert "couldn't parse" in reply.lower() or "try" in reply.lower()

    @pytest.mark.asyncio
    async def test_clears_timesheet_habits_from_user_data(self):
        update = _make_update("workout at 8am")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value={}):
            await ts_plan(update, ctx)

        assert "timesheet_habits" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_one_valid_habit_schedules_and_ends(self):
        update = _make_update("workout at 8am")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        parsed = {"Morning Workout": "8am"}
        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value=parsed), \
             patch("tasks.timesheet_handlers.stp.parse_time_expression", return_value=FUTURE_DT), \
             patch("tasks.timesheet_handlers.db.reschedule_task") as mock_reschedule:
            result = await ts_plan(update, ctx)

        assert result == ConversationHandler.END
        mock_reschedule.assert_called_once_with("h1", FUTURE_DT)

    @pytest.mark.asyncio
    async def test_reply_contains_scheduled_habit_title(self):
        update = _make_update("workout at 8am")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        parsed = {"Morning Workout": "8am"}
        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value=parsed), \
             patch("tasks.timesheet_handlers.stp.parse_time_expression", return_value=FUTURE_DT), \
             patch("tasks.timesheet_handlers.db.reschedule_task"):
            await ts_plan(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Morning Workout" in reply

    @pytest.mark.asyncio
    async def test_unmatched_habit_listed_in_reply(self):
        update = _make_update("unknown at 8am")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        parsed = {"Morning Workout": "8am", "unknown_habit": "9am"}
        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value=parsed), \
             patch("tasks.timesheet_handlers.stp.parse_time_expression", return_value=FUTURE_DT), \
             patch("tasks.timesheet_handlers.db.reschedule_task"):
            await ts_plan(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "unknown_habit" in reply or "Couldn't schedule" in reply

    @pytest.mark.asyncio
    async def test_bad_time_string_listed_as_unmatched(self):
        update = _make_update("workout at badtime")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        parsed = {"Morning Workout": "badtime"}
        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value=parsed), \
             patch("tasks.timesheet_handlers.stp.parse_time_expression", return_value=None), \
             patch("tasks.timesheet_handlers.db.reschedule_task") as mock_reschedule:
            result = await ts_plan(update, ctx)

        mock_reschedule.assert_not_called()
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_two_valid_habits_both_scheduled(self):
        update = _make_update("workout at 8am, read at 10pm")
        ctx = _make_ctx({"timesheet_habits": HABITS})

        parsed = {"Morning Workout": "8am", "Read 10 Pages": "10pm"}
        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value=parsed), \
             patch("tasks.timesheet_handlers.stp.parse_time_expression", return_value=FUTURE_DT), \
             patch("tasks.timesheet_handlers.db.reschedule_task") as mock_reschedule:
            await ts_plan(update, ctx)

        assert mock_reschedule.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_habits_in_user_data_all_unmatched(self):
        update = _make_update("workout at 8am")
        ctx = _make_ctx({"timesheet_habits": []})

        parsed = {"workout": "8am"}
        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value=parsed), \
             patch("tasks.timesheet_handlers.stp.parse_time_expression", return_value=FUTURE_DT), \
             patch("tasks.timesheet_handlers.db.reschedule_task") as mock_reschedule:
            result = await ts_plan(update, ctx)

        mock_reschedule.assert_not_called()
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_uses_user_id_from_update(self):
        update = _make_update("workout at 8am", user_id=99)
        ctx = _make_ctx({"timesheet_habits": HABITS})

        with patch("tasks.timesheet_handlers._parse_timesheet_input", return_value={}):
            await ts_plan(update, ctx)

        # Should not raise and should complete without using wrong uid
        update.message.reply_text.assert_awaited_once()


# ---------------------------------------------------------------------------
# _cancel
# ---------------------------------------------------------------------------

class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_clears_user_data(self):
        update = _make_update()
        ctx = _make_ctx({"timesheet_habits": HABITS, "other_key": "value"})

        result = await _cancel(update, ctx)

        assert ctx.user_data == {}
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancel_sends_cancelled_message(self):
        update = _make_update()
        ctx = _make_ctx()

        await _cancel(update, ctx)

        update.message.reply_text.assert_awaited_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "cancelled" in reply.lower()

    @pytest.mark.asyncio
    async def test_cancel_returns_conversation_end(self):
        update = _make_update()
        ctx = _make_ctx()

        result = await _cancel(update, ctx)

        assert result == ConversationHandler.END
