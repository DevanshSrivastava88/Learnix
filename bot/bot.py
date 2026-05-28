"""
bot.py — Learnix bot router.
Registers all handlers from study/ and tasks/ modules, starts scheduler.
"""

import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import settings_svc
import study.handlers as study_handlers
import tasks.handlers as tasks_handlers
from scheduler import register_jobs

load_dotenv()
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    settings_svc.get_settings(uid)  # creates row with defaults if new user
    first_name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hey *{first_name}*! I'm your AI life OS — just talk to me naturally.\n\n"
        f"📚 *Study* — /goal, /study\n"
        f"✅ *Tasks* — just say what you want to track, or use /newtask\n"
        f"⏰ *Reminders* — say 'remind me to X in Y mins'\n"
        f"📊 /tasks — see everything\n"
        f"📈 /graph — activity graph\n"
        f"⚙️ /settings — tweak reminder times",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Learnix Commands*\n\n"
        "*Study:*\n"
        "/goal — Create study goal\n"
        "/goals — List study goals\n"
        "/addtopic — Add topic to goal\n"
        "/study — Start study session\n"
        "/progress — Progress view\n"
        "/editgoal, /deletegoal, /pausegoal — Manage goals\n\n"
        "*Tasks & Reminders:*\n"
        "Just talk naturally — or use /newtask\n"
        "/schedule — Your full day schedule\n"
        "/tasks — List all tasks\n"
        "/done\\_<id> — Mark task done\n"
        "/deletetask — Delete a task\n"
        "/pause, /resume — Pause or resume\n\n"
        "*Analytics:*\n"
        "/graph — Activity graph (last 30 days)\n\n"
        "*Settings:*\n"
        "/settings — View settings\n"
        "/settime, /setmorning, /seteod — Set reminder times\n\n"
        "/cancel — Cancel anything",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /settime, /setmorning, /seteod (inline — single step)
# ---------------------------------------------------------------------------

async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "study"
    await update.message.reply_text(
        "Send daily study time in HH:MM format (IST). Example: `09:00`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_setmorning(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "morning"
    await update.message.reply_text(
        "Send morning brief time in HH:MM format (IST). Example: `08:00`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_seteod(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "eod"
    await update.message.reply_text(
        "Send EOD check-in time in HH:MM format (IST). Example: `21:00`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_time_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if message was consumed as a time-setting input."""
    setting_for = ctx.user_data.get("setting_time_for")
    if not setting_for:
        return False
    time_str = update.message.text.strip()
    try:
        h, m = map(int, time_str.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except Exception:
        await update.message.reply_text("Invalid format. Use HH:MM (e.g. 09:00):")
        return True
    uid = update.effective_user.id
    if setting_for == "study":
        settings_svc.set_daily_time(uid, time_str)
        label = "Daily study"
    elif setting_for == "morning":
        settings_svc.set_morning_brief_time(uid, time_str)
        label = "Morning brief"
    else:
        settings_svc.set_eod_time(uid, time_str)
        label = "EOD check-in"
    ctx.user_data.pop("setting_time_for")
    await update.message.reply_text(
        f"✅ {label} time set to *{time_str}* IST.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return True


# ---------------------------------------------------------------------------
# /graph — Activity trend graph
# ---------------------------------------------------------------------------

async def cmd_graph(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text("Generating your activity graph... 📊")
    try:
        import analytics_svc
        buf = analytics_svc.build_graph(uid)
        await update.message.reply_photo(buf, caption="Your activity over the last 30 days 📈")
    except Exception as e:
        logger.error(f"Graph failed for {uid}: {e}")
        await update.message.reply_text(f"❌ Could not generate graph: {e}")


# ---------------------------------------------------------------------------
# Global text handler (yes/later for study, quiz answers, time inputs)
# ---------------------------------------------------------------------------

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await handle_time_input(update, ctx):
        return

    uid = update.effective_user.id
    text = update.message.text.strip().lower()

    # yes/later for pending study sessions
    pending = ctx.bot_data.get("pending_sessions", {})
    if uid in pending:
        topic_id = pending[uid]
        if text == "yes":
            pending.pop(uid, None)
            from study.svc import get_topic
            topic = get_topic(topic_id)
            if topic:
                await study_handlers._run_study_session(update, ctx, topic)
        elif text == "later":
            pending.pop(uid, None)
            await update.message.reply_text("No problem! I'll remind you in 2 hours. 😴")
            ctx.job_queue.run_once(
                _reminder_job, when=7200,
                data={"user_id": uid, "topic_id": topic_id},
                name=f"reminder_{uid}",
            )
        return

    # Quiz answers
    if uid in ctx.bot_data.get("quiz_state", {}):
        await study_handlers.handle_quiz_answer(update, ctx)
        return

    # Pending task confirm/re-describe from free-text flow
    freetext_state = ctx.user_data.get("freetext_task_state")
    if freetext_state == "confirm":
        from tasks.handlers import nt_confirm, NT_DESCRIBE
        result = await nt_confirm(update, ctx)
        if result == NT_DESCRIBE:
            ctx.user_data["freetext_task_state"] = "describe"
        return
    if freetext_state == "describe":
        import claude_svc as _cs
        from tasks.handlers import _parse_and_respond
        ctx.user_data.pop("freetext_task_state", None)
        await _parse_and_respond(update, ctx, update.message.text.strip(), _cs)
        return

    # Free-form intent routing
    await handle_free_text(update, ctx)


async def handle_free_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import claude_svc
    from tasks.handlers import _parse_and_respond
    text = update.message.text.strip()
    try:
        intent = claude_svc.classify_intent(text)
    except Exception:
        intent = "chat"

    if intent == "task":
        await _parse_and_respond(update, ctx, text, claude_svc)
    elif intent == "study":
        await update.message.reply_text(
            "Sounds like you want to study something! 📚\n\n"
            "Use /goal to set up a learning goal, then /study to start a session.",
        )
    else:
        # General chat — Learnix responds naturally
        try:
            reply = claude_svc._ask(
                f"You are Learnix, a friendly AI life coach. Reply casually and helpfully in 1-2 sentences.\n\nUser: {text}",
                max_tokens=4096,
            )
            await update.message.reply_text(reply)
        except Exception:
            await update.message.reply_text("I'm here! Use /help to see what I can do.")


async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import settings_svc
    import tasks.svc as task_db
    from datetime import datetime, timezone
    import pytz

    uid = update.effective_user.id
    IST = pytz.timezone("Asia/Kolkata")
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    settings = settings_svc.get_settings(uid)
    habits = task_db.list_tasks(uid)

    lines = [f"📅 *Your Day — {now_ist.strftime('%a, %d %b')}*\n"]

    # Daily automatics
    lines.append("🔔 *Automatics*")
    lines.append(f"  🌅 `{settings['morning_brief_time']}` IST  Morning brief")
    lines.append(f"  📚 `{settings['daily_session_time']}` IST  Study session")
    lines.append(f"  🌙 `{settings['eod_time']}` IST  EOD check-in\n")

    # Habits with next-due info
    if habits:
        lines.append(f"✅ *Habits* — {len(habits)} active")
        for t in habits:
            next_at_str = t.get("next_reminder_at")
            recur = t.get("recurrence_days", 1)
            freq = "daily" if recur == 1 else f"every {recur}d"
            if next_at_str:
                next_at = datetime.fromisoformat(next_at_str)
                if next_at.tzinfo is None:
                    next_at = next_at.replace(tzinfo=timezone.utc)
                delta = next_at - now_utc
                secs = delta.total_seconds()
                if secs <= 0:
                    when = "⚡ due now"
                elif secs < 3600:
                    when = f"in {int(secs // 60)}m"
                elif delta.days == 0:
                    when = f"in {int(secs // 3600)}h"
                else:
                    when = f"in {delta.days}d"
            else:
                when = "—"
            lines.append(f"  • *{t['title']}* ({freq})  →  {when}")
        lines.append("")

    # Live reminders from job queue
    live = [j for j in ctx.job_queue.jobs()
            if j.name and (j.name.startswith(f"interval_{uid}_") or
                           j.name.startswith(f"onetime_{uid}_"))]
    if live:
        lines.append("⏰ *Reminders running*")
        for j in live:
            title = (j.data or {}).get("title", "?")
            next_run = j.job.next_run_time
            next_str = next_run.astimezone(IST).strftime("%H:%M IST") if next_run else "?"
            if j.name.startswith(f"interval_{uid}_"):
                mins = (j.data or {}).get("interval_minutes", 60)
                freq_str = "every hour" if mins == 60 else (f"every {mins}m" if mins < 60 else f"every {mins // 60}h")
                lines.append(f"  🔄 *{title}*  →  {freq_str}  (next: {next_str})")
            else:
                lines.append(f"  ⏰ *{title}*  →  fires at {next_str}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _reminder_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = ctx.job.data["user_id"]
    topic_id = ctx.job.data["topic_id"]
    if ctx.bot_data.get("pending_sessions", {}).get(uid) == topic_id:
        return
    from study.svc import get_topic
    topic = get_topic(topic_id)
    if topic:
        await ctx.bot.send_message(
            uid,
            f"⏰ Reminder: Ready to study *{topic['title']}* now?\n\nReply *yes* to start.",
            parse_mode=ParseMode.MARKDOWN,
        )
        ctx.bot_data.setdefault("pending_sessions", {})[uid] = topic_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Core commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("settime", cmd_settime))
    app.add_handler(CommandHandler("setmorning", cmd_setmorning))
    app.add_handler(CommandHandler("seteod", cmd_seteod))
    app.add_handler(CommandHandler("graph", cmd_graph))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("cancel", lambda u, c: None))

    # Study handlers
    for h in study_handlers.get_handlers():
        app.add_handler(h)

    # Task handlers
    for h in tasks_handlers.get_handlers():
        app.add_handler(h)

    # Global text handler (lowest priority)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def on_startup(application: Application) -> None:
        register_jobs(application)
        logger.info("Learnix bot started — all jobs registered.")

    app.post_init = on_startup
    logger.info("Starting Learnix bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
