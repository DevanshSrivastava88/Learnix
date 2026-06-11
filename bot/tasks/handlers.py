"""Task handlers: /newtask, /tasks, /done_<id>, /edittask, /deletetask, /pause, /resume, /complete"""

import asyncio
import logging
import os
import re

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

# Matches an explicit time/duration in the user's own words — used to catch the model
# hallucinating a delay_minutes when the message actually gave no time at all.
_TIME_EXPR = re.compile(
    r'\b(\d{1,2}(:\d{2})?\s*(am|pm)|in\s+\d+\s*(min(ute)?|hour|hr)s?|at\s+\d|by\s+\d|'
    r'tonight|tomorrow|today|noon|midnight|morning|evening|afternoon|night)\b',
    re.IGNORECASE,
)
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


async def _parse_and_respond(update, ctx, text: str, claude_svc, context: str = "",
                             pre_parsed: dict = None) -> int:
    import asyncio as _asyncio
    if pre_parsed:
        parsed = pre_parsed
    else:
        try:
            parsed = await _asyncio.to_thread(claude_svc.parse_task, text, context)
        except Exception as e:
            logger.error(f"parse_task failed: {e}")
            await update.message.reply_text("Hmm, didn't catch that — say it again?")
            return NT_DESCRIBE

    task_type = parsed.get("type", "reminder")

    if parsed.get("clarify"):
        await update.message.reply_text(parsed["clarify"])
        ctx.user_data["partial_task"] = parsed
        return NT_DESCRIBE

    title = parsed.get("title", "")
    desc = parsed.get("description", "")

    # One-time reminder
    if task_type == "reminder":
        uid = update.effective_user.id
        from datetime import timezone as _tz, datetime as _dt
        if parsed.get("time_minutes") is not None:
            # Unified LLM path — minutes computed by the model
            try:
                delay = max(0, int(parsed["time_minutes"]))
            except (TypeError, ValueError):
                delay = 0
        else:
            # Legacy path (/newtask flow) — LLM-normalized time_str, regex converts
            import skip_time_parser as stp
            time_str = (parsed.get("time_str") or "").strip()
            parsed_dt = stp.parse_time_expression(time_str) if time_str else None
            if parsed_dt:
                delay = max(0, int((parsed_dt - _dt.now(_tz.utc)).total_seconds() / 60))
            else:
                delay = 0
        from datetime import timedelta as _td
        if delay == 0:
            # No time — store unscheduled, ask for time
            task_row = None
            try:
                task_row = db.create_task(
                    user_id=uid, title=title, task_type="task",
                    description=parsed.get("description", ""),
                    recurrence_days=None, target_date=None, next_reminder_at=None,
                )
            except Exception as e:
                logger.error(f"create unscheduled task failed: {e}")
            if task_row is None:
                await update.message.reply_text("Hmm, couldn't save that — try again?")
                return ConversationHandler.END
            ctx.user_data["pending_time_for"] = {"task_id": task_row["id"], "title": title}
            await update.message.reply_text(
                f"Added *{title}*. 📌 Want to set a time? Say `8pm`, `in 2 hours`, or `no`.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END
        # Timed — store with next_reminder_at
        next_at = (_dt.now(_tz.utc) + _td(minutes=delay)).isoformat()
        try:
            db.create_task(
                user_id=uid, title=title, task_type="task",
                description=parsed.get("description", ""),
                recurrence_days=None, target_date=None, next_reminder_at=next_at,
            )
        except Exception as e:
            logger.error(f"create timed task failed: {e}")
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

    buttons = [["⏭ No specific time"], ["✏️ Edit"], ["❌ Cancel"]]
    await update.message.reply_text(
        f"Got it:\n\n{summary}\n\nAny specific time you want to schedule this? (e.g. `8pm`)\nOr press **No specific time**.",
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

    # Try to parse a time from the user's reply before creating the task
    import skip_time_parser as stp
    is_skip = text.lower() in {"no specific time", "⏭ no specific time", "skip time", "skip", "default", "later", "no", "nope", "yeah, add it", "✅ yeah, add it", "yes", "yep", "add it", "sure", "ok", "okay", "add"}
    parsed_time = None if is_skip else stp.parse_time_expression(text)

    # If text is not skip, not a time, and not a confirm word — re-ask
    if not is_skip and parsed_time is None:
        await update.message.reply_text(
            f"Didn't catch that as a time. Try `8pm`, `7:30am` — or press **Skip time** to add without one.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return NT_CONFIRM

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
    ctx.user_data.clear()

    if parsed_time:
        db.set_custom_time(task["id"], parsed_time)
        import pytz
        IST = pytz.timezone("Asia/Kolkata")
        time_label = parsed_time.astimezone(IST).strftime("%I:%M %p").lstrip("0")
        await update.message.reply_text(
            f"Added! 🎉 *{task['title']}* — {freq} at {time_label} IST. 🔔",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text(
            f"Added! 🎉 *{task['title']}* — {freq}.\n"
            f"Set a time anytime: 'move {task['title'].lower()} to 8pm'",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
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

    from datetime import datetime
    timed = [t for t in tasks if t.get("next_reminder_at")]
    untimed = [t for t in tasks if not t.get("next_reminder_at")]
    timed.sort(key=lambda t: t["next_reminder_at"])

    lines = ["<b>📋 Your tasks</b>\n"]
    for t in timed:
        time_label = datetime.fromisoformat(t["next_reminder_at"]).astimezone(IST).strftime("%I:%M%p").lstrip("0").lower().replace(":00", "")
        lines.append(f"  {time_label} → {t['title']}")
    if untimed:
        lines.append("\n________")
        for t in untimed:
            lines.append(f"  • {t['title']}")
        lines.append("\n<i>Unscheduled tasks are often ignored — say \"set [task] to [time]\" to pin one.</i>")

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

    db.set_custom_time(task["id"], parsed_dt)
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
