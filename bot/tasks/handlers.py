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
NT_TYPE, NT_TITLE, NT_DESC, NT_RECURRENCE, NT_DEADLINE, NT_MILESTONES = range(20, 26)
DT_SELECT, DT_CONFIRM = range(30, 32)


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
    await update.message.reply_text("What's the name of this task?", reply_markup=ReplyKeyboardRemove())
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
    import analytics_svc
    analytics_svc.log_activity(uid, "habit", note=task["title"])
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
    import analytics_svc
    analytics_svc.log_activity(uid, "milestone", note=task["title"])
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
