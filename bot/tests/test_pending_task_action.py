"""Tests for the pending_task_action disambiguation state machine.

Strategy: test the _fuzzy_match_task helper directly (no DB needed),
then test the state-storage and resolution logic via bot.py handlers
with all external deps mocked out.
"""
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# ---------------------------------------------------------------------------
# Minimal stubs so bot.py can be imported without live services
# ---------------------------------------------------------------------------

def _make_stub(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


for _name in [
    "dotenv", "telegram", "telegram.constants", "telegram.ext",
    "settings_svc", "twilio_svc", "study.handlers",
    "tasks", "tasks.handlers", "tasks.svc",
    "study", "study.svc",
    "analytics_svc",
    "scheduler", "supabase_svc",
]:
    if _name not in sys.modules:
        _make_stub(_name)

# Wire sub-modules onto parent stubs so patch("tasks.svc.list_tasks") resolves
sys.modules["tasks"].svc = sys.modules["tasks.svc"]
sys.modules["study"].svc = sys.modules["study.svc"]

# Pre-populate stub functions so patch() can replace them (create=True alternative)
for _fn in ["list_tasks", "mark_done", "log_skip", "reschedule_task",
            "delete_task", "update_task", "mark_important"]:
    setattr(sys.modules["tasks.svc"], _fn, MagicMock())

for _fn in ["log_activity"]:
    setattr(sys.modules["analytics_svc"], _fn, MagicMock())

for _fn in ["update_streak", "get_settings"]:
    setattr(sys.modules["settings_svc"], _fn, MagicMock())

# telegram stubs need a few attributes bot.py references at import time
tg = sys.modules["telegram"]
tg.Update = MagicMock
tg.KeyboardButton = MagicMock
tg.ReplyKeyboardMarkup = MagicMock
tg.ReplyKeyboardRemove = MagicMock
tg_const = sys.modules["telegram.constants"]
tg_const.ParseMode = MagicMock()
tg_const.ParseMode.MARKDOWN = "Markdown"
tg_ext = sys.modules["telegram.ext"]
tg_ext.Application = MagicMock
tg_ext.CommandHandler = MagicMock
tg_ext.MessageHandler = MagicMock
_ctx_types = MagicMock()
_ctx_types.DEFAULT_TYPE = MagicMock()
tg_ext.ContextTypes = _ctx_types
tg_ext.filters = MagicMock()
sys.modules["dotenv"].load_dotenv = lambda: None
sys.modules["study.handlers"].get_handlers = lambda: []
sys.modules["tasks.handlers"].get_handlers = lambda: []
sys.modules["scheduler"].register_jobs = lambda app: None

# Now import the module under test
with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test"}):
    import importlib
    import bot


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
    """When multiple tasks match, pending_task_action must be set before asking."""

    tasks_in_db = [
        {"id": "1", "title": "Morning workout", "recurrence_days": 1},
        {"id": "2", "title": "Morning workout — Step 1: Warmup", "recurrence_days": 1},
    ]

    # Build fake update + ctx
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42

    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = {}

    fake_claude = MagicMock()
    fake_claude.extract_task_name_from_message.return_value = "morning workout"

    with patch("tasks.svc.list_tasks", return_value=tasks_in_db):
        await bot.handle_task_action_freetext(update, ctx, "done morning workout", "done", fake_claude)

    assert "pending_task_action" in ctx.user_data
    pending = ctx.user_data["pending_task_action"]
    assert pending["action"] == "done"
    assert len(pending["candidates"]) == 2
    candidate_ids = {c["id"] for c in pending["candidates"]}
    assert "1" in candidate_ids and "2" in candidate_ids

    # Bot should have asked a disambiguation question
    update.message.reply_text.assert_awaited_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Which task" in msg


# ---------------------------------------------------------------------------
# _resolve_pending_task_action — resolves correctly when user replies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_pending_done_action():
    """After storing pending_task_action, replying with the task name should mark it done."""

    # Use clearly distinct candidate titles so fuzzy match picks exactly one
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

    fake_settings = {"streak": 3}

    with patch("tasks.svc.list_tasks", return_value=full_tasks), \
         patch("tasks.svc.mark_done") as mock_mark_done, \
         patch("analytics_svc.log_activity"), \
         patch("settings_svc.update_streak"), \
         patch("settings_svc.get_settings", return_value=fake_settings):

        consumed = await bot._resolve_pending_task_action(update, ctx)

    assert consumed is True
    # pending state must be cleared
    assert "pending_task_action" not in ctx.user_data
    # mark_done called with the matched task id
    mock_mark_done.assert_called_once_with("1")
    # confirmation sent
    update.message.reply_text.assert_awaited_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Morning workout" in msg


@pytest.mark.asyncio
async def test_resolve_pending_no_match_re_asks():
    """When the reply doesn't match any candidate, bot re-asks without clearing state."""

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
    # State must NOT be cleared — still waiting for a valid answer
    assert "pending_task_action" in ctx.user_data
    # Bot re-asks
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_returns_false_when_no_pending():
    update = MagicMock()
    ctx = MagicMock()
    ctx.user_data = {}

    result = await bot._resolve_pending_task_action(update, ctx)
    assert result is False


# ---------------------------------------------------------------------------
# handle_mark_important_freetext — stores pending on ambiguous match
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

    with patch("tasks.svc.list_tasks", return_value=tasks_in_db):
        await bot.handle_mark_important_freetext(update, ctx, "mark morning workout important", fake_claude)

    assert "pending_task_action" in ctx.user_data
    assert ctx.user_data["pending_task_action"]["action"] == "mark_important"


# ---------------------------------------------------------------------------
# handle_reschedule_task_freetext — stores pending on ambiguous match
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

    with patch("tasks.svc.list_tasks", return_value=tasks_in_db):
        await bot.handle_reschedule_task_freetext(update, ctx, "reschedule morning workout to 6am", fake_claude)

    assert "pending_task_action" in ctx.user_data
    pending = ctx.user_data["pending_task_action"]
    assert pending["action"] == "reschedule_task"
    assert pending["time_str"] == "06:00"
