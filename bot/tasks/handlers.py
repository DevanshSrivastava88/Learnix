"""Task handlers: /newtask, /tasks, /done_<id>, /edittask, /deletetask, /pause, /resume, /complete"""

import asyncio
import logging
import os

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
        "What do you want to track? Just say it naturally.\n\n"
        "_e.g. 'remind me to game in 20 mins' or 'workout every day'_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return NT_DESCRIBE


async def nt_describe(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    import claude_svc
    return await _parse_and_respond(update, ctx, update.message.text.strip(), claude_svc)


async def _parse_and_respond(update, ctx, text: str, claude_svc, context: str = "") -> int:
    try:
        parsed = claude_svc.parse_task(text, context=context)
    except Exception as e:
        logger.error(f"parse_task failed: {e}")
        await update.message.reply_text("Hmm, didn't catch that — say it again?")
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
            await update.message.reply_text(
                'When should I remind you? (e.g. \'in 30 mins\', \'at 6pm\', \'in 2 hours\')'
            )
            ctx.user_data["partial_task"] = parsed
            return NT_DESCRIBE
        uid = update.effective_user.id
        ctx.job_queue.run_once(
            _reminder_fire,
            when=delay * 60,
            data={"user_id": uid, "title": title, "task_id": ""},
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
            data={"user_id": uid, "title": title, "task_id": "", "interval_minutes": interval},
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
    import twilio_svc
    if twilio_svc.is_twilio_enabled(data["user_id"]):
        railway_url = os.environ.get("RAILWAY_URL", "")
        task_id = data.get("task_id", "")
        asyncio.get_running_loop().run_in_executor(
            None, twilio_svc.make_reminder_call,
            data["user_id"], task_id, data["title"], railway_url
        )


async def nt_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    parsed = ctx.user_data.get("parsed_task", {})

    if "Cancel" in text or text.lower() == "cancel":
        await update.message.reply_text("No worries, cancelled! 👋", reply_markup=ReplyKeyboardRemove())
        ctx.user_data.clear()
        return ConversationHandler.END

    if "Edit" in text:
        await update.message.reply_text(
            "Sure! Describe it again and I'll re-parse it:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return NT_DESCRIBE

    uid = update.effective_user.id
    recur = parsed.get("recurrence_days", 1)
    try:
        task = db.create_task(
            user_id=uid,
            title=parsed.get("title", "Task"),
            task_type="habit",
            description=parsed.get("description", ""),
            recurrence_days=recur,
            target_date=None,
        )
    except Exception as e:
        logger.error(f"nt_confirm create_task failed: {e}")
        await update.message.reply_text("Something went wrong saving that. Try again!", reply_markup=ReplyKeyboardRemove())
        ctx.user_data.clear()
        return ConversationHandler.END
    freq = "every day" if recur == 1 else f"every {recur} days"
    await update.message.reply_text(
        f"Added! 🎉 I'll remind you about *{task['title']}* {freq}.",
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
    # Filter out breakdown step tasks — they clutter the tasks view
    tasks = [t for t in all_tasks if " — Step " not in t.get("title", "")]
    if not tasks:
        await update.message.reply_text("No tasks yet! Just tell me what you want to track.")
        return
    lines = ["<b>Here's what you're tracking:</b>\n"]
    for t in tasks:
        recur = t.get("recurrence_days", 1)
        freq = "daily" if recur == 1 else f"every {recur}d"
        lines.append(f"  • {t['title']} ({freq})")
    lines.append('\nSay "done with [task]" or "skip [task]" — or use /deletetask, /pause to manage.')
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


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
        await update.message.reply_text("Hmm, can't find that task. Try /tasks to see what's active.")
        return
    db.mark_done(task["id"])
    import analytics_svc
    import settings_svc
    analytics_svc.log_activity(uid, "habit", note=task["title"])
    settings_svc.update_streak(uid, __import__("datetime").date.today())
    settings = settings_svc.get_settings(uid)
    streak = settings.get("streak", 0) or 0
    recur = task.get("recurrence_days", 1)
    streak_line = f"🔥 {streak} day streak!" if streak > 1 else "Nice, keep it up!"
    await update.message.reply_text(
        f"Done! ✅ *{task['title']}*  {streak_line}\nI'll remind you again in {recur} day(s).",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /deletetask
# ---------------------------------------------------------------------------

async def cmd_deletetask(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    if not tasks:
        await update.message.reply_text("Nothing to delete — you've got no tasks right now.")
        return ConversationHandler.END
    ctx.user_data["tasks_list"] = tasks
    buttons = [[t["title"]] for t in tasks] + [["Cancel"]]
    await update.message.reply_text(
        "Which one do you want to delete?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DT_SELECT


async def deletetask_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    tasks = ctx.user_data.get("tasks_list", [])
    task = next((t for t in tasks if t["title"] == chosen), None)
    if not task:
        await update.message.reply_text("Hmm, couldn't find that task.")
        return ConversationHandler.END
    ctx.user_data["deleting_task"] = task
    buttons = [["Yes, delete it"], ["Cancel"]]
    await update.message.reply_text(
        f"⚠️ Delete *{task['title']}*? This can't be undone.",
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
            f"Gone! 🗑️ *{task['title']}* deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("No worries, kept it! 👍", reply_markup=ReplyKeyboardRemove())
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /pause and /resume
# ---------------------------------------------------------------------------

async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    tasks = db.list_tasks(uid, status="active")
    if not tasks:
        await update.message.reply_text("No active tasks to pause right now.")
        return
    lines = ["<b>Which one do you want to pause?</b>\n"]
    for t in tasks:
        lines.append(f"⏸ /pause_{t['id'][:8]} — {t['title']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_pause_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/pause_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Hmm, can't find that task.")
        return
    db.update_task(task["id"], status="paused")
    await update.message.reply_text(f"Paused ⏸️ *{task['title']}*. Resume it whenever you're ready.", parse_mode=ParseMode.MARKDOWN)


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    tasks = db.list_tasks(uid, status="paused")
    if not tasks:
        await update.message.reply_text("Nothing's paused right now!")
        return
    lines = ["<b>Which one do you want to resume?</b>\n"]
    for t in tasks:
        lines.append(f"▶️ /resume_{t['id'][:8]} — {t['title']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_resume_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/resume_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid, status="paused")
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Hmm, can't find that task.")
        return
    db.update_task(task["id"], status="active")
    await update.message.reply_text(f"Back on! ▶️ *{task['title']}* is active again.", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /complete — mark milestone complete
# ---------------------------------------------------------------------------

async def cmd_complete(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    milestones = [t for t in db.list_tasks(uid) if t["task_type"] == "milestone"]
    if not milestones:
        await update.message.reply_text("No active milestones to complete right now.")
        return
    lines = ["<b>Which milestone did you knock out?</b>\n"]
    for m in milestones:
        lines.append(f"✅ /complete_{m['id'][:8]} — {m['title']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_complete_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/complete_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Hmm, can't find that task.")
        return
    db.update_task(task["id"], status="completed")
    import analytics_svc
    analytics_svc.log_activity(uid, "milestone", note=task["title"])
    await update.message.reply_text(f"Let's go! 🎉 *{task['title']}* — done!", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /settings
# ---------------------------------------------------------------------------

async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import settings_svc
    import twilio_svc
    uid = update.effective_user.id
    s = settings_svc.get_settings(uid)
    twilio_on = twilio_svc.is_twilio_enabled(uid)
    twilio_status = "ON ✅" if twilio_on else "OFF ⏸"
    await update.message.reply_text(
        f"*⚙️ Your settings*\n\n"
        f"📖 Study time: *{s['daily_session_time']}* IST — /settime\n"
        f"🌅 Morning brief: *{s['morning_brief_time']}* IST — /setmorning\n"
        f"🌙 EOD check-in: *{s['eod_time']}* IST — /seteod\n"
        f"📞 Call reminders: *{twilio_status}* — /twilio on \\| /twilio off",
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
        MessageHandler(filters.Regex(r"^/skip_"), handle_skip_task),
    ]


async def handle_skip_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /skip_<short_id> — asks user to reschedule or outright skip."""
    text = update.message.text.strip()
    short_id = text.replace("/skip_", "")
    uid = update.effective_user.id
    tasks = db.list_tasks(uid)
    task = next((t for t in tasks if t["id"].startswith(short_id)), None)
    if not task:
        await update.message.reply_text("Hmm, can't find that task.")
        return
    ctx.user_data["pending_skip"] = task
    await update.message.reply_text(
        f"Reschedule *{task['title']}*? When should I remind you?\n\n"
        "Try `3pm`, `in 2 hours`, `tomorrow 9am` — or just say `skip` to log it and move on.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_skip_response(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from bot.py handle_text. Returns True if message was consumed."""
    task = ctx.user_data.get("pending_skip")
    if not task:
        return False

    text = update.message.text.strip()
    uid = update.effective_user.id
    ctx.user_data.pop("pending_skip")

    if text.lower() == "skip":
        db.log_skip(uid, task["id"], note="outright")
        from datetime import datetime, timezone, timedelta
        next_at = datetime.now(timezone.utc) + timedelta(days=task.get("recurrence_days", 1))
        db.reschedule_task(task["id"], next_at)
        await update.message.reply_text(
            f"Logged! I'll remind you about *{task['title']}* again in {task.get('recurrence_days', 1)} day(s).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    import skip_time_parser as stp
    parsed_dt = stp.parse_time_expression(text)
    if parsed_dt is None:
        await update.message.reply_text(
            "Hmm, didn't get that. Try `3pm`, `in 2 hours`, or just say `skip`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        ctx.user_data["pending_skip"] = task
        return True

    db.reschedule_task(task["id"], parsed_dt)
    db.log_skip(uid, task["id"], note=f"rescheduled_to:{parsed_dt.isoformat()}")
    time_str = parsed_dt.astimezone(IST).strftime("%I:%M %p IST")
    await update.message.reply_text(
        f"Done! I'll remind you about *{task['title']}* at {time_str}. 🕐",
        parse_mode=ParseMode.MARKDOWN,
    )
    return True


async def _cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled! 👋", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
