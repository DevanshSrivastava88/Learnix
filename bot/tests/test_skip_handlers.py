"""
Tests for handle_skip_task and handle_skip_response in tasks/handlers.py.

All Supabase, telegram, and skip_time_parser calls are mocked.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

with patch("supabase_svc.create_client"):
    from tasks.handlers import handle_skip_task, handle_skip_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(text: str, user_id: int = 42) -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id
    return update


def _make_ctx(user_data: dict = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    return ctx


# ---------------------------------------------------------------------------
# handle_skip_task
# ---------------------------------------------------------------------------

TASK = {"id": "abc123", "title": "Morning Workout", "recurrence_days": 1}


@pytest.mark.asyncio
async def test_skip_task_found_sets_pending_and_replies():
    update = _make_update("/skip_abc")
    ctx = _make_ctx()

    with patch("tasks.handlers.db.list_tasks", return_value=[TASK]):
        await handle_skip_task(update, ctx)

    assert ctx.user_data["pending_skip"] == TASK
    update.message.reply_text.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply


@pytest.mark.asyncio
async def test_skip_task_not_found_replies_error():
    update = _make_update("/skip_xyz")
    ctx = _make_ctx()

    with patch("tasks.handlers.db.list_tasks", return_value=[TASK]):
        await handle_skip_task(update, ctx)

    assert "pending_skip" not in ctx.user_data
    update.message.reply_text.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "can't find" in reply.lower()


@pytest.mark.asyncio
async def test_skip_task_matches_prefix_of_id():
    # short_id is the prefix — "abc" should match "abc123"
    update = _make_update("/skip_abc")
    ctx = _make_ctx()

    with patch("tasks.handlers.db.list_tasks", return_value=[TASK]):
        await handle_skip_task(update, ctx)

    assert ctx.user_data["pending_skip"]["id"] == "abc123"


# ---------------------------------------------------------------------------
# handle_skip_response — no pending skip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_response_returns_false_when_no_pending():
    update = _make_update("skip")
    ctx = _make_ctx()

    result = await handle_skip_response(update, ctx)

    assert result is False
    update.message.reply_text.assert_not_awaited()


# ---------------------------------------------------------------------------
# handle_skip_response — "skip" keyword → log outright skip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_response_outright_skip_logs_and_reschedules():
    update = _make_update("skip")
    ctx = _make_ctx({"pending_skip": dict(TASK)})

    with patch("tasks.handlers.db.log_skip") as mock_log, \
         patch("tasks.handlers.db.reschedule_task") as mock_reschedule:
        result = await handle_skip_response(update, ctx)

    assert result is True
    mock_log.assert_called_once_with(42, "abc123", note="outright")
    mock_reschedule.assert_called_once()
    assert "pending_skip" not in ctx.user_data
    update.message.reply_text.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply


@pytest.mark.asyncio
async def test_skip_response_outright_skip_uses_recurrence_days():
    task = dict(TASK, recurrence_days=3)
    update = _make_update("skip")
    ctx = _make_ctx({"pending_skip": task})

    with patch("tasks.handlers.db.log_skip"), \
         patch("tasks.handlers.db.reschedule_task") as mock_reschedule:
        await handle_skip_response(update, ctx)

    _, next_at = mock_reschedule.call_args[0]
    # next_at should be approximately 3 days from now
    delta = next_at - datetime.now(timezone.utc)
    assert 2 < delta.total_seconds() / 86400 < 4


@pytest.mark.asyncio
async def test_skip_response_case_insensitive_skip_keyword():
    update = _make_update("SKIP")
    ctx = _make_ctx({"pending_skip": dict(TASK)})

    with patch("tasks.handlers.db.log_skip"), \
         patch("tasks.handlers.db.reschedule_task"):
        result = await handle_skip_response(update, ctx)

    assert result is True


# ---------------------------------------------------------------------------
# handle_skip_response — parsed time → reschedule
# ---------------------------------------------------------------------------

FUTURE_DT = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_skip_response_valid_time_reschedules_to_parsed_dt():
    update = _make_update("3pm")
    ctx = _make_ctx({"pending_skip": dict(TASK)})

    with patch("skip_time_parser.parse_time_expression", return_value=FUTURE_DT) as mock_parse, \
         patch("tasks.handlers.db.set_custom_time") as mock_set, \
         patch("tasks.handlers.db.log_skip") as mock_log:
        result = await handle_skip_response(update, ctx)

    assert result is True
    mock_parse.assert_called_once_with("3pm")
    mock_set.assert_called_once_with("abc123", FUTURE_DT)
    mock_log.assert_called_once()
    log_note = mock_log.call_args[1]["note"]
    assert "rescheduled_to" in log_note
    assert "pending_skip" not in ctx.user_data
    update.message.reply_text.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "Morning Workout" in reply


@pytest.mark.asyncio
async def test_skip_response_valid_time_reply_contains_time_string():
    update = _make_update("in 2 hours")
    ctx = _make_ctx({"pending_skip": dict(TASK)})

    with patch("skip_time_parser.parse_time_expression", return_value=FUTURE_DT), \
         patch("tasks.handlers.db.set_custom_time"), \
         patch("tasks.handlers.db.log_skip"):
        await handle_skip_response(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    # time string should be something like "08:00 PM IST" or "03:00 PM IST"
    assert "IST" in reply


# ---------------------------------------------------------------------------
# handle_skip_response — unparseable time → re-prompts and keeps pending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_response_invalid_time_re_prompts_and_keeps_pending():
    update = _make_update("sometime next century")
    ctx = _make_ctx({"pending_skip": dict(TASK)})

    with patch("skip_time_parser.parse_time_expression", return_value=None):
        result = await handle_skip_response(update, ctx)

    assert result is True
    assert ctx.user_data["pending_skip"] == TASK
    update.message.reply_text.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "didn't get that" in reply.lower() or "try" in reply.lower()


@pytest.mark.asyncio
async def test_skip_response_invalid_time_does_not_log_skip():
    update = _make_update("blah")
    ctx = _make_ctx({"pending_skip": dict(TASK)})

    with patch("skip_time_parser.parse_time_expression", return_value=None), \
         patch("tasks.handlers.db.log_skip") as mock_log, \
         patch("tasks.handlers.db.set_custom_time") as mock_set:
        await handle_skip_response(update, ctx)

    mock_log.assert_not_called()
    mock_set.assert_not_called()
