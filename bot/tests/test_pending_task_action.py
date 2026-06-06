"""Tests for the pending_task_action disambiguation state machine."""
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# ---------------------------------------------------------------------------
# Build a complete stub dict for patch.dict — auto-cleaned up by context manager
# ---------------------------------------------------------------------------

def _make_stubs():
    stubs = {}

    def stub(name):
        m = types.ModuleType(name)
        stubs[name] = m
        return m

    dotenv = stub("dotenv")
    dotenv.load_dotenv = lambda: None

    tg = stub("telegram")
    tg.Update = MagicMock
    tg.KeyboardButton = MagicMock
    tg.ReplyKeyboardMarkup = MagicMock
    tg.ReplyKeyboardRemove = MagicMock

    tg_const = stub("telegram.constants")
    tg_const.ParseMode = MagicMock()
    tg_const.ParseMode.MARKDOWN = "Markdown"

    tg_ext = stub("telegram.ext")
    tg_ext.Application = MagicMock
    tg_ext.CommandHandler = MagicMock
    tg_ext.MessageHandler = MagicMock
    ctx_types = MagicMock()
    ctx_types.DEFAULT_TYPE = MagicMock()
    tg_ext.ContextTypes = ctx_types
    tg_ext.filters = MagicMock()

    settings = stub("settings_svc")
    settings.update_streak = MagicMock()
    settings.get_settings = MagicMock()

    twilio = stub("twilio_svc")
    twilio.is_twilio_enabled = MagicMock(return_value=False)

    analytics = stub("analytics_svc")
    analytics.log_activity = MagicMock()

    tasks_pkg = stub("tasks")
    tasks_svc_stub = stub("tasks.svc")
    for fn in ["list_tasks", "mark_done", "log_skip", "reschedule_task",
               "delete_task", "update_task", "mark_important"]:
        setattr(tasks_svc_stub, fn, MagicMock())
    tasks_pkg.svc = tasks_svc_stub

    tasks_handlers = stub("tasks.handlers")
    tasks_handlers.get_handlers = lambda: []

    study_pkg = stub("study")
    study_svc_stub = stub("study.svc")
    study_pkg.svc = study_svc_stub

    study_handlers = stub("study.handlers")
    study_handlers.get_handlers = lambda: []

    scheduler = stub("scheduler")
    scheduler.register_jobs = lambda app: None

    supabase = stub("supabase_svc")

    return stubs


_STUBS = _make_stubs()

# Import bot once under the stubs — use patch.dict so sys.modules is restored automatically
with patch.dict(sys.modules, _STUBS), \
     patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test"}):
    # Remove bot from sys.modules if cached from another test file
    sys.modules.pop("bot", None)
    import bot  # noqa: E402  (module-level import inside context is intentional)

# After the with block, sys.modules is restored to pre-stub state.
# bot is now imported and its functions reference the stub objects captured at import time.
# That is fine — the tests only call bot functions and patch the stubs in _STUBS directly.


# ---------------------------------------------------------------------------
# _fuzzy_match_task — unit tests (no async, no mocks needed)
# ---------------------------------------------------------------------------

TASKS = [
    {"id": "1", "title": "Morning workout"},
    {"id": "2", "title": "Morning workout — Step 1: Warmup"},
    {"id": "3", "title": "Evening run"},
]


def test_fuzzy_exact_substring():
    matches = bot._fuzzy_match_task("Morning workout", TASKS)
    assert any(t["id"] == "1" for t in matches)


def test_fuzzy_returns_step_task_too():
    matches = bot._fuzzy_match_task("Morning workout", TASKS)
    ids = {t["id"] for t in matches}
    assert "1" in ids and "2" in ids


def test_fuzzy_no_match_returns_empty():
    matches = bot._fuzzy_match_task("completely unrelated thing xyz", TASKS)
    assert matches == []


# ---------------------------------------------------------------------------
# handle_task_action_freetext — stores pending_task_action on ambiguous match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_task_action_freetext_stores_pending_on_ambiguous():
    # Both titles must survive the "— Step " filter in handle_task_action_freetext
    # and both must fuzzy-match "morning workout" to trigger the ambiguous path.
    tasks_in_db = [
        {"id": "1", "title": "Morning workout", "recurrence_days": 1},
        {"id": "2", "title": "Morning workout at home", "recurrence_days": 1},
    ]

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42

    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = {}

    fake_claude = MagicMock()
    fake_claude.extract_task_name_from_message.return_value = "morning workout"

    _STUBS["tasks.svc"].list_tasks = MagicMock(return_value=tasks_in_db)

    with patch.dict(sys.modules, _STUBS):
        await bot.handle_task_action_freetext(update, ctx, "done morning workout", "done", fake_claude)

    assert "pending_task_action" in ctx.user_data
    pending = ctx.user_data["pending_task_action"]
    assert pending["action"] == "done"
    assert len(pending["candidates"]) == 2
    candidate_ids = {c["id"] for c in pending["candidates"]}
    assert "1" in candidate_ids and "2" in candidate_ids
    update.message.reply_text.assert_awaited_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Which task" in msg


# ---------------------------------------------------------------------------
# _resolve_pending_task_action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_pending_done_action():
    full_tasks = [
        {"id": "1", "title": "Morning workout", "recurrence_days": 1},
        {"id": "2", "title": "Evening run", "recurrence_days": 1},
    ]

    update = MagicMock()
    update.message.text = "Morning workout"
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42

    ctx = MagicMock()
    ctx.user_data = {
        "pending_task_action": {
            "action": "done",
            "candidates": [
                {"id": "1", "title": "Morning workout"},
                {"id": "2", "title": "Evening run"},
            ],
        }
    }
    ctx.bot_data = {}

    _STUBS["tasks.svc"].list_tasks = MagicMock(return_value=full_tasks)
    _STUBS["tasks.svc"].mark_done = MagicMock()
    _STUBS["settings_svc"].get_settings = MagicMock(return_value={"streak": 3})

    with patch.dict(sys.modules, _STUBS):
        consumed = await bot._resolve_pending_task_action(update, ctx)

    assert consumed is True
    assert "pending_task_action" not in ctx.user_data
    _STUBS["tasks.svc"].mark_done.assert_called_once_with("1")
    update.message.reply_text.assert_awaited_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Morning workout" in msg


@pytest.mark.asyncio
async def test_resolve_pending_no_match_re_asks():
    update = MagicMock()
    update.message.text = "something totally different"
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42

    pending = {
        "action": "done",
        "candidates": [
            {"id": "1", "title": "Morning workout"},
            {"id": "2", "title": "Evening run"},
        ],
    }
    ctx = MagicMock()
    ctx.user_data = {"pending_task_action": pending}

    consumed = await bot._resolve_pending_task_action(update, ctx)

    assert consumed is True
    assert "pending_task_action" in ctx.user_data
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_returns_false_when_no_pending():
    update = MagicMock()
    ctx = MagicMock()
    ctx.user_data = {}

    result = await bot._resolve_pending_task_action(update, ctx)
    assert result is False


# ---------------------------------------------------------------------------
# handle_mark_important_freetext
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_mark_important_stores_pending_on_ambiguous():
    tasks_in_db = [
        {"id": "1", "title": "Morning workout"},
        {"id": "2", "title": "Morning workout — Step 1: Warmup"},
    ]

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42

    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = {}

    fake_claude = MagicMock()
    fake_claude.extract_task_name_from_message.return_value = "morning workout"

    _STUBS["tasks.svc"].list_tasks = MagicMock(return_value=tasks_in_db)

    with patch.dict(sys.modules, _STUBS):
        await bot.handle_mark_important_freetext(update, ctx, "mark morning workout important", fake_claude)

    assert "pending_task_action" in ctx.user_data
    assert ctx.user_data["pending_task_action"]["action"] == "mark_important"


# ---------------------------------------------------------------------------
# handle_reschedule_task_freetext
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_reschedule_stores_pending_on_ambiguous():
    tasks_in_db = [
        {"id": "1", "title": "Morning workout"},
        {"id": "2", "title": "Morning workout — Step 1: Warmup"},
    ]

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42

    ctx = MagicMock()
    ctx.user_data = {}

    fake_claude = MagicMock()
    fake_claude.extract_reschedule_info.return_value = {"task_name": "morning workout", "time": "06:00"}

    _STUBS["tasks.svc"].list_tasks = MagicMock(return_value=tasks_in_db)

    with patch.dict(sys.modules, _STUBS):
        await bot.handle_reschedule_task_freetext(update, ctx, "reschedule morning workout to 6am", fake_claude)

    assert "pending_task_action" in ctx.user_data
    pending = ctx.user_data["pending_task_action"]
    assert pending["action"] == "reschedule_task"
    assert pending["time_str"] == "06:00"
