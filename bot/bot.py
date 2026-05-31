"""
bot.py — Learnix bot router.
Registers all handlers from study/ and tasks/ modules, starts scheduler.
"""

import os
import logging

from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import settings_svc
import twilio_svc
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
        f"📅 /schedule — your full day view + plan habit times\n"
        f"📊 /tasks — see everything\n"
        f"📈 /graph — activity graph  |  /skipgraph — skip analytics\n"
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
        "/schedule — Full day view; reply with times to plan habits\n"
        "/tasks — List all tasks\n"
        "/skipgraph — Skip patterns graph\n"
        "/done\\_<id> — Mark task done\n"
        "/deletetask — Delete a task\n"
        "/pause, /resume — Pause or resume\n\n"
        "*Analytics:*\n"
        "/graph — Activity graph (last 30 days)\n\n"
        "*Settings:*\n"
        "/settings — View settings\n"
        "/settime, /setmorning, /seteod — Set reminder times\n"
        "/twilio — Missed call notifications\n\n"
        "/cancel — Cancel anything",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /settime, /setmorning, /seteod (inline — single step)
# ---------------------------------------------------------------------------

async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "study"
    await update.message.reply_text(
        "What time should I ping you for study? (HH:MM IST, e.g. `09:00`)",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_setmorning(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "morning"
    await update.message.reply_text(
        "When do you want your morning brief? (HH:MM IST, e.g. `08:00`)",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_seteod(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["setting_time_for"] = "eod"
    await update.message.reply_text(
        "When should I do the EOD check-in? (HH:MM IST, e.g. `21:00`)",
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
        await update.message.reply_text("Hmm, that doesn't look right. Try HH:MM — like `09:00`:", parse_mode=ParseMode.MARKDOWN)
        return True
    uid = update.effective_user.id
    if setting_for == "study":
        settings_svc.set_daily_time(uid, time_str)
        label = "Study time"
    elif setting_for == "morning":
        settings_svc.set_morning_brief_time(uid, time_str)
        label = "Morning brief"
    else:
        settings_svc.set_eod_time(uid, time_str)
        label = "EOD check-in"
    ctx.user_data.pop("setting_time_for")
    await update.message.reply_text(
        f"Done! {label} set to *{time_str}* IST. 🕐",
        parse_mode=ParseMode.MARKDOWN,
    )
    return True


# ---------------------------------------------------------------------------
# /graph — Activity trend graph
# ---------------------------------------------------------------------------

async def cmd_skipgraph(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text("Generating your skip analytics... 📊")
    try:
        import analytics_svc
        buf = analytics_svc.build_skip_graph(uid)
        await update.message.reply_photo(buf, caption="Your skip patterns — last 30 days 📉\nRed bars = most-skipped days. Green line = completion rate.")
    except Exception as e:
        logger.error(f"Skip graph failed for {uid}: {e}")
        await update.message.reply_text(f"Couldn't generate the graph right now: {e}")


async def cmd_graph(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text("Generating your activity graph... 📊")
    try:
        import analytics_svc
        buf = analytics_svc.build_graph(uid)
        await update.message.reply_photo(buf, caption="Your activity over the last 30 days 📈")
    except Exception as e:
        logger.error(f"Graph failed for {uid}: {e}")
        await update.message.reply_text(f"Couldn't generate the graph right now: {e}")


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
            await update.message.reply_text("No worries! I'll nudge you again in 2 hours. 😴")
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

    # Clear confirmation flow
    if await handle_clear_confirm(update, ctx):
        return

    # Schedule timesheet inline reply
    if await handle_schedule_timesheet(update, ctx):
        return

    # Skip reschedule flow
    from tasks.handlers import handle_skip_response
    if await handle_skip_response(update, ctx):
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


async def handle_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Save phone number when user shares contact via /twilio on."""
    contact = update.message.contact
    if not contact:
        return
    uid = update.effective_user.id
    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    twilio_svc.set_phone_number(uid, phone)
    await update.message.reply_text(
        f"✅ Got it! I'll call {phone} for reminders.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def handle_free_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import claude_svc
    from tasks.handlers import _parse_and_respond
    from telegram.constants import ChatAction
    text = update.message.text.strip()

    # Pre-check: ignore emoji-only messages and bare dismissal/reaction phrases
    ascii_text = text.encode("ascii", errors="ignore").decode().strip()
    if not ascii_text:  # emoji-only or symbols with no text
        return
    # Use ascii_text for word check so "❌ Cancel" → "Cancel" → caught
    # Also catches stale keyboard button replies that arrive outside an active flow
    if ascii_text.lower() in {
        "cancel", "back", "stop", "exit", "no", "nope", "nah",
        "never mind", "nevermind", "nm", "forget it", "nothing",
        "wtf", "lol", "lmao", "omg", "damn", "hmm", "hm", "ok",
        "okay", "k", "kk", "fine", "cool", "nice", "great",
        # keyboard button replies that should never reach Gemini
        "yeah, add it", "edit", "yes, delete it",
        "none (root topic)", "name", "description", "target date",
    }:
        await update.message.reply_text("Hey! 👋 What do you want to track? Or /help to see what I can do.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        intent = claude_svc.classify_intent(text)
    except Exception:
        intent = "chat"

    if intent == "task":
        await _parse_and_respond(update, ctx, text, claude_svc)
    elif intent == "breakdown":
        await handle_breakdown(update, ctx, text)
    elif intent == "show_tasks":
        await tasks_handlers.cmd_tasks(update, ctx)
    elif intent == "show_schedule":
        await cmd_schedule(update, ctx)
    elif intent == "show_progress":
        await study_handlers.cmd_progress(update, ctx)
    elif intent == "show_goals":
        await study_handlers.cmd_goals(update, ctx)
    elif intent == "show_graph":
        await cmd_graph(update, ctx)
    elif intent == "show_skipgraph":
        await cmd_skipgraph(update, ctx)
    elif intent == "start_study":
        await study_handlers.cmd_study(update, ctx)
    elif intent == "study":
        await update.message.reply_text(
            "Sounds like you want to learn something! 📚\n\n"
            "Use /goal to set up a learning goal, then /study to start a session.",
        )
    elif intent in ("done", "skip_task", "delete_task", "pause_task"):
        await handle_task_action_freetext(update, ctx, text, intent, claude_svc)
    else:
        # General chat — Learnix responds naturally
        try:
            reply = claude_svc._ask(
                f"You are Learnix, a friendly AI life coach. Reply casually and helpfully in 1-2 sentences.\n\nUser: {text}",
                max_tokens=4096,
            )
            await update.message.reply_text(reply)
        except Exception:
            await update.message.reply_text("I'm here! Try /help to see what I can do.")


def _fuzzy_match_task(task_name: str, tasks: list[dict]) -> list[dict]:
    """Return tasks whose title contains task_name (case-insensitive), or vice versa."""
    needle = task_name.lower().strip()
    if not needle:
        return []
    matches = []
    for t in tasks:
        haystack = t["title"].lower()
        if needle in haystack or haystack in needle:
            matches.append(t)
    # If no substring match, fall back to word-overlap scoring
    if not matches:
        needle_words = set(needle.split())
        scored = []
        for t in tasks:
            words = set(t["title"].lower().split())
            overlap = len(needle_words & words)
            if overlap:
                scored.append((overlap, t))
        scored.sort(key=lambda x: -x[0])
        matches = [t for _, t in scored[:3]]
    return matches


async def handle_task_action_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    intent: str,
    claude_svc,
) -> None:
    """Handle done/skip_task/delete_task/pause_task intents expressed in free text."""
    import tasks.svc as task_db
    import analytics_svc
    import settings_svc as settings_db

    uid = update.effective_user.id
    tasks = task_db.list_tasks(uid)
    if not tasks:
        await update.message.reply_text("You don't have any active tasks right now.")
        return

    # Extract task name from message
    try:
        task_name = claude_svc.extract_task_name_from_message(text)
    except Exception:
        task_name = ""

    if not task_name:
        await update.message.reply_text(
            "Which task do you mean? Try /tasks to see your list."
        )
        return

    matches = _fuzzy_match_task(task_name, tasks)

    if not matches:
        await update.message.reply_text(
            f"Couldn't find a task matching *{task_name}*. Try /tasks to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if len(matches) > 1:
        # Ambiguous — ask which one
        names = "\n".join(f"  • {t['title']}" for t in matches[:3])
        await update.message.reply_text(
            f"Which task did you mean?\n{names}\n\nTap the right one via /tasks and use the command.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    task = matches[0]

    if intent == "done":
        task_db.mark_done(task["id"])
        analytics_svc.log_activity(uid, "habit", note=task["title"])
        settings_db.update_streak(uid, __import__("datetime").date.today())
        settings = settings_db.get_settings(uid)
        streak = settings.get("streak", 0) or 0
        streak_line = f"🔥 {streak} day streak!" if streak > 1 else "Nice, keep it up!"
        recur = task.get("recurrence_days", 1)
        await update.message.reply_text(
            f"Done! ✅ *{task['title']}*  {streak_line}\nI'll remind you again in {recur} day(s).",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif intent == "skip_task":
        from datetime import datetime, timezone, timedelta
        task_db.log_skip(uid, task["id"], note="outright")
        next_at = datetime.now(timezone.utc) + timedelta(days=task.get("recurrence_days", 1))
        task_db.reschedule_task(task["id"], next_at)
        await update.message.reply_text(
            f"Skipped! I'll remind you about *{task['title']}* again in {task.get('recurrence_days', 1)} day(s).",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif intent == "delete_task":
        task_db.delete_task(task["id"])
        await update.message.reply_text(
            f"Gone! 🗑️ *{task['title']}* has been deleted.",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif intent == "pause_task":
        task_db.update_task(task["id"], status="paused")
        await update.message.reply_text(
            f"Paused ⏸️ *{task['title']}*. Use /resume when you're ready to pick it up again.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_breakdown(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle breakdown intent: break a task or study goal into steps."""
    import claude_svc
    import study.svc as study_svc
    import tasks.svc as tasks_svc

    uid = update.effective_user.id

    subject = claude_svc.extract_breakdown_subject(text)

    # Check if subject matches an existing study goal
    goals = study_svc.list_goals(uid, "in_progress")
    matched_goal = None
    subject_lower = subject.lower()
    for g in goals:
        if subject_lower in g["name"].lower() or g["name"].lower() in subject_lower:
            matched_goal = g
            break

    if matched_goal:
        # Study goal breakdown — generate subtopics
        await update.message.reply_text(f"Breaking down *{matched_goal['name']}* into subtopics... 📚", parse_mode=ParseMode.MARKDOWN)
        try:
            subtopics = claude_svc.breakdown_study_goal(matched_goal["name"])
        except Exception as e:
            logger.error(f"breakdown_study_goal failed: {e}")
            await update.message.reply_text("Couldn't generate subtopics right now. Try again in a moment.")
            return

        # Get current max order_index so new topics don't collide
        existing = study_svc.list_topics_for_goal(matched_goal["id"])
        base_order = max((t["order_index"] for t in existing), default=-1) + 1

        created = []
        for i, subtopic in enumerate(subtopics):
            study_svc.create_topic(
                goal_id=matched_goal["id"],
                title=subtopic,
                order_index=base_order + i,
            )
            created.append(subtopic)

        numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(created))
        await update.message.reply_text(
            f"Added {len(created)} topics to *{matched_goal['name']}* 📚\n\n{numbered}\n\n"
            f"Use /study to go through them in order.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        # Task breakdown — generate steps as habit tasks
        await update.message.reply_text(f"Breaking *{subject}* into steps... ⚡", parse_mode=ParseMode.MARKDOWN)
        try:
            steps = claude_svc.breakdown_task(subject)
        except Exception as e:
            logger.error(f"breakdown_task failed: {e}")
            await update.message.reply_text("Couldn't generate steps right now. Try again in a moment.")
            return

        created = []
        for i, step in enumerate(steps, start=1):
            title = f"{subject} — Step {i}: {step}"
            tasks_svc.create_task(
                user_id=uid,
                title=title,
                task_type="habit",
                recurrence_days=1,
            )
            created.append(step)

        bullet_lines = "\n".join(f"• Step {i+1}: {s}" for i, s in enumerate(created))
        await update.message.reply_text(
            f"Done! Created {len(created)} steps for *{subject}* 👇\n\n{bullet_lines}\n\n"
            f"They're now in your /tasks and you'll get reminders like any habit.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *Learnix — Your AI Life OS*\n\n"
        "Just talk to me naturally — or use commands.\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📚 *STUDY*\n"
        "/goal — Create a learning goal\n"
        "/goals — See all your goals\n"
        "/addtopic — Add a topic to a goal\n"
        "/study — Start a study session\n"
        "/progress — See how far you've come\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "✅ *HABITS & TASKS*\n"
        "Just say it — _'I want to run every day'_ and I'll add it\n"
        "/newtask — Add a habit or reminder\n"
        "/tasks — See all active tasks\n"
        "/schedule — Full day view; reply with times to plan habits today\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "⏰ *REMINDERS*\n"
        "Each habit gets 2 reminders/day — tap ✅ Done or ⏭ Skip\n"
        "Skip → reschedule to any time, or just skip for today\n"
        "No response → auto-skipped after 2nd reminder\n"
        "_'remind me to drink water every hour'_ → repeating reminder\n"
        "_'remind me to call mom in 30 mins'_ → one-time reminder\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📊 *INSIGHTS*\n"
        "/graph — Activity over last 30 days\n"
        "/skipgraph — Skip patterns + completion rate\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ *SETTINGS*\n"
        "/settings — View your times\n"
        "/setmorning — Morning brief time\n"
        "/settime — Daily study session time\n"
        "/seteod — Evening check-in time\n"
        "/twilio on|off — Missed call notifications\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🗑 *DATA*\n"
        "/clear — Delete all your data and start fresh\n\n"

        "_Tip: Just talk naturally — I understand plain English!_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data["pending_clear"] = True
    await update.message.reply_text(
        "⚠️ *Heads up — this deletes everything:*\n"
        "goals, topics, tasks, skips, settings, activity history.\n\n"
        "Type `confirm delete` to wipe it all, or anything else to back out.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_clear_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from handle_text. Returns True if consumed."""
    if not ctx.user_data.get("pending_clear"):
        return False
    ctx.user_data.pop("pending_clear")
    if update.message.text.strip().lower() != "confirm delete":
        await update.message.reply_text("All good, nothing was deleted. 👍")
        return True
    uid = update.effective_user.id
    import logging as _log
    _logger = _log.getLogger(__name__)
    sb = __import__("supabase_svc").get_client()
    # topics has no user_id — cascades when goals are deleted
    tables = ["task_skips", "activity_log", "tasks", "goals", "motivation_log", "settings"]
    errors = []
    for table in tables:
        try:
            sb.table(table).delete().eq("user_id", uid).execute()
        except Exception as e:
            errors.append(table)
            _logger.error(f"Clear failed on {table} for {uid}: {e}")
    if errors:
        await update.message.reply_text(f"⚠️ Partial clear — hit some errors on: {', '.join(errors)}. Try again.")
    else:
        await update.message.reply_text("🗑 Done! Everything's wiped.\n\nUse /start to start fresh!")
    return True


_TWILIO_SETUP = (
    "📞 <b>Twilio Missed Call Setup:</b>\n\n"
    "1. Get a Twilio number at twilio.com\n"
    "2. In your Twilio number settings → Voice → set webhook to your server URL\n"
    "3. Set <b>CallStatus callback URL</b> to:\n"
    "   <code>https://your-url/twilio/missed-call</code>\n"
    "4. Add to your <code>.env</code>: <code>TWILIO_AUTH_TOKEN=xxx</code>\n"
    "5. Run: <code>python run_all.py</code>\n\n"
    "When someone calls and you don't answer → I'll notify you here!"
)


async def cmd_twilio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    args = ctx.args

    if not args:
        enabled = twilio_svc.is_twilio_enabled(uid)
        status  = "ON ✅" if enabled else "OFF ⏸"
        await update.message.reply_text(
            f"📞 Missed call notifications: <b>{status}</b>\n\n"
            f"<code>/twilio on</code> or <code>/twilio off</code> to change.",
            parse_mode="HTML",
        )
        return

    arg = args[0].lower()
    if arg == "on":
        twilio_svc.set_twilio_enabled(uid, True)
        # Ask for phone number if not already set
        if not twilio_svc.get_phone_number(uid):
            btn = KeyboardButton("📱 Share my number", request_contact=True)
            await update.message.reply_text(
                "Call reminders <b>on!</b> 📞\n\nShare your number so I know where to call:",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup([[btn]], one_time_keyboard=True, resize_keyboard=True),
            )
        else:
            await update.message.reply_text(
                "Call reminders <b>on!</b> 📞 I'll ring you when it's habit time.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
    elif arg == "off":
        twilio_svc.set_twilio_enabled(uid, False)
        await update.message.reply_text(
            "Got it — call reminders <b>off</b>. ⏸",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "Try <code>/twilio on</code> or <code>/twilio off</code>.",
            parse_mode="HTML",
        )


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
    all_habits = task_db.list_tasks(uid)
    # Filter out breakdown step tasks — they clutter the schedule view
    habits = [t for t in all_habits if " — Step " not in t.get("title", "")]

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

    # Offer to plan habit times inline
    if habits:
        lines.append(
            "\n_Want to plan your day? Reply with times, e.g. 'workout at 8am, pushups in 30 mins'_"
        )
        ctx.user_data["schedule_timesheet_habits"] = habits

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_schedule_timesheet(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from handle_text. Handles inline time-planning reply after /schedule.
    Returns True if consumed."""
    habits = ctx.user_data.get("schedule_timesheet_habits")
    if not habits:
        return False

    text = update.message.text.strip()
    uid = update.effective_user.id

    # Only consume if the message looks like it contains time-scheduling language.
    # We check for specific patterns so random messages (e.g. "how am I doing") don't
    # get swallowed.  "am"/"pm" are only treated as time markers when preceded by a digit.
    import re
    time_patterns = [
        r"\d\s*am\b", r"\d\s*pm\b",          # digit + am/pm  e.g. "8am", "10 pm"
        r"\bat\s+\d",                          # "at 8", "at 10"
        r"\bin\s+\d",                          # "in 30 mins", "in 2 hours"
        r"\bmins?\b", r"\bhours?\b",           # "mins", "hours"
        r"\bmorning\b", r"\bevening\b",
        r"\bnight\b", r"\bnoon\b",
        r"\bmidnight\b", r"\bo'clock\b",
    ]
    lower = text.lower()
    is_time_reply = any(re.search(p, lower) for p in time_patterns)
    if not is_time_reply:
        # Not a scheduling reply — clear the state and let the message fall through.
        ctx.user_data.pop("schedule_timesheet_habits", None)
        return False

    ctx.user_data.pop("schedule_timesheet_habits", None)

    import tasks.svc as task_db
    import skip_time_parser as stp
    import tasks.timesheet_handlers as ts

    habit_names = [h["title"] for h in habits]
    parsed = ts._parse_timesheet_input(text, habit_names)

    scheduled = []
    unmatched = []

    for raw_name, time_str in parsed.items():
        task = ts._find_habit(raw_name, habits)
        if not task:
            unmatched.append(raw_name)
            continue
        dt = stp.parse_time_expression(time_str)
        if dt is None:
            unmatched.append(f"{raw_name} (bad time: {time_str})")
            continue
        task_db.reschedule_task(task["id"], dt)
        scheduled.append((task["title"], dt))

    if not scheduled:
        await update.message.reply_text(
            "Couldn't parse any times from that. Try: `workout at 8am, reading at 10pm`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    lines = ["📅 *Today's plan:*\n"]
    for title, dt in sorted(scheduled, key=lambda x: x[1]):
        ist_time = dt.astimezone(IST).strftime("%I:%M %p")
        lines.append(f"  • *{title}* at {ist_time}")
    if unmatched:
        lines.append(f"\n_Couldn't schedule: {', '.join(unmatched)}_")
    lines.append("\nI'll remind you at each time. 🎯")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    return True


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
            f"⏰ Hey! Ready to study *{topic['title']}*? Reply *yes* to jump in, or *later* to snooze.",
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
    app.add_handler(CommandHandler("skipgraph", cmd_skipgraph))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("twilio", cmd_twilio))
    async def _noop_cancel(u, c): pass
    app.add_handler(CommandHandler("cancel", _noop_cancel))

    # Study handlers
    for h in study_handlers.get_handlers():
        app.add_handler(h)

    # Task handlers
    for h in tasks_handlers.get_handlers():
        app.add_handler(h)

    # Contact sharing handler (for /twilio on phone number collection)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Global text handler (lowest priority)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def on_startup(application: Application) -> None:
        register_jobs(application)
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("info",      "How everything works"),
            BotCommand("schedule",  "Your full day at a glance"),
            BotCommand("tasks",     "List active tasks"),
            BotCommand("graph",     "Activity graph"),
            BotCommand("skipgraph", "Skip patterns graph"),
            BotCommand("settings",  "View & update settings"),
            BotCommand("clear",     "Delete all your data"),
            BotCommand("twilio",    "Missed call notifications"),
        ])
        logger.info("Learnix bot started — all jobs registered.")

    app.post_init = on_startup
    logger.info("Starting Learnix bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
