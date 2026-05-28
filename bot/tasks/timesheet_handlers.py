"""timesheet_handlers.py — /timesheet: plan today's habit schedule interactively."""

import logging
from typing import Optional

import pytz
from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

import tasks.svc as db
import claude_svc
import skip_time_parser as stp

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

TS_PLAN = 50


async def cmd_timesheet(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    habits = [t for t in db.list_tasks(uid) if t["task_type"] == "habit"]
    if not habits:
        await update.message.reply_text(
            "You have no active habits yet. Use /newtask to add some first!"
        )
        return ConversationHandler.END

    ctx.user_data["timesheet_habits"] = habits
    lines = ["Here are your active habits:\n"]
    for h in habits:
        lines.append(f"  • *{h['title']}*")
    lines.append(
        "\nTell me when you want to do each one today.\n"
        "_Example: 'workout at 8am, reading at 10pm, pushups in 30 mins'_"
    )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return TS_PLAN


async def ts_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    habits = ctx.user_data.get("timesheet_habits", [])
    text = update.message.text.strip()

    habit_names = [h["title"] for h in habits]
    parsed = _parse_timesheet_input(text, habit_names)

    scheduled = []
    unmatched = []

    for raw_name, time_str in parsed.items():
        task = _find_habit(raw_name, habits)
        if not task:
            unmatched.append(raw_name)
            continue
        dt = stp.parse_time_expression(time_str)
        if dt is None:
            unmatched.append(f"{raw_name} (bad time: {time_str})")
            continue
        db.reschedule_task(task["id"], dt)
        scheduled.append((task["title"], dt))

    ctx.user_data.pop("timesheet_habits", None)

    if not scheduled:
        await update.message.reply_text(
            "Couldn't parse any times from that. Try: `workout at 8am, reading at 10pm`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    lines = ["📅 *Today's plan:*\n"]
    for title, dt in sorted(scheduled, key=lambda x: x[1]):
        ist_time = dt.astimezone(IST).strftime("%I:%M %p")
        lines.append(f"  • *{title}* at {ist_time}")

    if unmatched:
        lines.append(f"\n_Couldn't schedule: {', '.join(unmatched)}_")

    lines.append("\nI'll remind you at each time. 🎯")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def _parse_timesheet_input(text: str, habit_names: list) -> dict:
    """Use Gemini to extract {habit_name: time_string} from free-form text."""
    prompt = (
        f"The user has these habits: {habit_names}\n\n"
        f"Extract the schedule from this message: \"{text}\"\n\n"
        "Return a JSON object mapping habit name (use exact name from the list above) "
        "to time string. Time strings should be like '8am', '10:30pm', 'in 2 hours'.\n"
        "Only include habits the user explicitly mentioned.\n"
        "Example: {\"Morning workout\": \"8am\", \"Read 10 pages\": \"10pm\"}"
    )
    try:
        result = claude_svc._ask_json(prompt)
        if isinstance(result, dict):
            return result
    except Exception as e:
        logger.error(f"Timesheet parse failed: {e}")
    return {}


def _find_habit(name: str, habits: list) -> Optional[dict]:
    """Case-insensitive substring match."""
    name_lower = name.lower()
    for h in habits:
        if name_lower in h["title"].lower() or h["title"].lower() in name_lower:
            return h
    return None


async def _cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def get_handlers():
    timesheet_conv = ConversationHandler(
        entry_points=[CommandHandler("timesheet", cmd_timesheet)],
        states={
            TS_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ts_plan)],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            MessageHandler(filters.Regex(r"^Cancel$"), _cancel),
        ],
    )
    return [timesheet_conv]
