"""Task handlers: /newtask, /tasks, /done_<id>, /edittask, /deletetask, /pause, /resume, /complete"""

import logging

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
NT_DESCRIBE, NT_CONFIRM = range(20, 22)
DT_SELECT, DT_CONFIRM = range(30, 32)


# ---------------------------------------------------------------------------
# /newtask — create habit or milestone
# ---------------------------------------------------------------------------

async def cmd_newtask(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    import claude_svc
    text = update.message.text.strip()
    inline = text.replace("/newtask", "").strip()
    if inline:
        return await _parse_and_respond(update, ctx, inline, claude_svc)
    await update.message.reply_text(
        "What do you want to track? Just say it.\n\n"
        "_e.g. 'remind me to game in 20 mins' or 'workout every day'_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return NT_DESCRIBE


async def nt_describe(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    import claude_svc
    return await _parse_and_respond(update, ctx, update.message.text.strip(), claude_svc)


async def _parse_and_respond(update, ctx, text: str, claude_svc) -> int:
    try:
        parsed = claude_svc.parse_task(text)
    except Exception as e:
        logger.error(f"parse_task failed: {e}")
        await update.message.reply_text("Didn't catch that, say it again?")
        return NT_DESCRIBE

    if parsed.get("clarify"):
        await update.message.reply_text(parsed["clarify"])
        ctx.user_data["partial_task"] = parsed
        return NT_DESCRIBE

    task_type = parsed.get("type", "habit")
    title = parsed.get("title", "")
    desc = parsed.get("description", "")

    # One-time reminder — schedule a job, no DB needed
    if task_type == "reminder":
        delay = parsed.get("delay_minutes") or 0
        if delay <= 0:
            await update.message.reply_text("How many minutes from now?")
            ctx.user_data["partial_task"] = parsed
            return NT_DESCRIBE
        uid = update.effective_user.id
        ctx.job_queue.run_once(
            _reminder_fire,
            when=delay * 60,
            data={"user_id": uid, "title": title},
            name=f"onetime_{uid}_{title}",
        )
        time_str = f"{delay} min" if delay < 60 else f"{delay // 60}h {delay % 60}m".replace(" 0m", "")
        await update.message.reply_text(f"⏰ Got it! I'll remind you about *{title}* in {time_str}.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # Interval reminder — repeating every X minutes
    if task_type == "interval_reminder":
        interval = parsed.get("interval_minutes") or 60
        uid = update.effective_user.id
        ctx.job_queue.run_repeating(
            _reminder_fire,
            interval=interval * 60,
            first=interval * 60,
            data={"user_id": uid, "title": title},
            name=f"interval_{uid}_{title[:20]}",
        )
        if interval < 60:
            interval_str = f"every {interval} min"
        elif interval == 60:
            interval_str = "every hour"
        else:
            interval_str = f"every {interval // 60}h" + (f" {interval % 60}m" if interval % 60 else "")
        await update.message.reply_text(
            f"⏰ Got it! I'll remind you about *{title}* {interval_str}.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    # Habit
    ctx.user_data["parsed_task"] = parsed
    ctx.user_data["freetext_task_state"] = "confirm"
    recur = parsed.get("recurrence_days", 1)
    freq = "every day" if recur == 1 else f"every {recur} days"
    summary = f"*{title}* — {freq}"
    if desc:
        summary += f"\n_{desc}_"

    buttons = [["✅ Yeah, add it"], ["✏️ Edit"], ["❌ Cancel"]]
    await update.message.reply_text(
        f"Got it:\n\n{summary}\n\nLook right?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return NT_CONFIRM


async def _reminder_fire(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = ctx.job.data
    await ctx.bot.send_message(data["user_id"], f"⏰ Hey! Don't forget: *{data['title']}*", parse_mode=ParseMode.MARKDOWN)


async def nt_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    parsed = ctx.user_data.get("parsed_task", {})

    if "Cancel" in text or text.lower() == "cancel":
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        ctx.user_data.clear()
        return ConversationHandler.END

    if "Edit" in text:
        await update.message.reply_text(
            "Describe it again with corrections:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return NT_DESCRIBE

    uid = update.effective_user.id
    recur = parsed.get("recurrence_days", 1)
    task = db.create_task(
        user_id=uid,
        title=parsed.get("title", "Task"),
        task_type="habit",
        description=parsed.get("description", ""),
        recurrence_days=recur,
        target_date=None,
    )
    freq = "every day" if recur == 1 else f"every {recur} days"
    await update.message.reply_text(
        f"✅ *{task['title']}* added! I'll remind you {freq}.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /tasks — list all active tasks
# ---------------------------------------------------------------------------

async def cmd_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    all_tasks = db.list_tasks(uid)
    if not all_tasks:
        await update.message.reply_text("No tasks yet. Just tell me what you want to track!")
        return
    lines = ["*Your tasks:*\n"]
    for t in all_tasks:
        recur = t.get("recurrence_days", 1)
        freq = "daily" if recur == 1 else f"every {recur}d"
        lines.append(f"  • {t['title']} ({freq}) — /done_{t['id'][:8]}")
    lines.append("\n/deletetask or /pause to manage.")
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
            NT_DESCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_describe)],
            NT_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, nt_confirm)],
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
