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

async def _resolve_pending_task_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """If user was asked to disambiguate a task action, resolve it now. Returns True if consumed."""
    pending = ctx.user_data.get("pending_task_action")
    if not pending:
        return False

    import tasks.svc as task_db
    import analytics_svc
    import settings_svc as settings_db

    uid = update.effective_user.id
    reply = update.message.text.strip()
    action = pending["action"]
    candidates = pending["candidates"]  # list of {"id": ..., "title": ...}

    # Fuzzy match user's reply against candidate titles
    matched = _fuzzy_match_task(reply, candidates)

    if not matched:
        names = "\n".join(f"  • {c['title']}" for c in candidates)
        await update.message.reply_text(
            f"Which one did you mean?\n{names}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    if len(matched) > 1:
        names = "\n".join(f"  • {t['title']}" for t in matched)
        await update.message.reply_text(
            f"Still a few matches — which one?\n{names}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    # Exact match — perform the action
    ctx.user_data.pop("pending_task_action", None)
    task_id = matched[0]["id"]

    # Fetch full task row (candidates only have id+title)
    all_tasks = task_db.list_tasks(uid)
    task = next((t for t in all_tasks if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text("Couldn't find that task. Try /tasks to see your list.")
        return True

    if action == "done":
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

    elif action == "skip_task":
        from datetime import datetime, timezone, timedelta
        task_db.log_skip(uid, task["id"], note="outright")
        next_at = datetime.now(timezone.utc) + timedelta(days=task.get("recurrence_days", 1))
        task_db.reschedule_task(task["id"], next_at)
        await update.message.reply_text(
            f"Skipped! I'll remind you about *{task['title']}* again in {task.get('recurrence_days', 1)} day(s).",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif action == "delete_task":
        task_db.delete_task(task["id"])
        await update.message.reply_text(
            f"Gone! 🗑️ *{task['title']}* has been deleted.",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif action == "pause_task":
        task_db.update_task(task["id"], status="paused")
        await update.message.reply_text(
            f"Paused ⏸️ *{task['title']}*. Use /resume when you're ready to pick it up again.",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif action == "mark_important":
        task_db.mark_important(task["id"])
        await update.message.reply_text(
            f"Got it — *{task['title']}* is now marked ⚡ important. "
            f"I'll keep reminding you every hour until you do it.",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif action == "reschedule_task":
        # pending also has "time_str" stored at disambiguation time
        time_str = pending.get("time_str", "")
        if not time_str:
            await update.message.reply_text(
                f"What time should I remind you about *{task['title']}*? (e.g. '6am', '8:30pm')",
                parse_mode=ParseMode.MARKDOWN,
            )
            return True
        import pytz
        from datetime import datetime, timezone, timedelta
        IST = pytz.timezone("Asia/Kolkata")
        try:
            h, m = map(int, time_str.split(":"))
            now_ist = datetime.now(IST)
            target_ist = now_ist.replace(hour=h, minute=m, second=0, microsecond=0)
            if target_ist <= now_ist:
                target_ist += timedelta(days=1)
            new_time_utc = target_ist.astimezone(timezone.utc)
        except Exception:
            await update.message.reply_text("Couldn't parse that time. Try something like '6am' or '20:30'.")
            return True
        task_db.reschedule_task(task["id"], new_time_utc)
        when_label = new_time_utc.astimezone(IST).strftime("%I:%M %p")
        day_label = "today" if new_time_utc.astimezone(IST).date() == datetime.now(IST).date() else "tomorrow"
        await update.message.reply_text(
            f"Done! I'll remind you about *{task['title']}* at {when_label} {day_label} 👍",
            parse_mode=ParseMode.MARKDOWN,
        )

    return True


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await handle_time_input(update, ctx):
        return

    # Resolve disambiguation for task actions (done/skip/delete/pause/mark_important/reschedule)
    if await _resolve_pending_task_action(update, ctx):
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

    # Skip topic confirmation
    if await study_handlers.handle_skip_topic_confirm(update, ctx):
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

    # Delay duration response (when user was asked "how long?")
    if await handle_delay_duration_response(update, ctx):
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
        if text in {"cancel", "back", "stop", "exit", "no", "nope", "nah"}:
            ctx.user_data.clear()
            await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
            return
        ctx.user_data.pop("freetext_task_state", None)
        await _parse_and_respond(update, ctx, update.message.text.strip(), _cs)
        return

    # Multi-step goal creation from free text
    if await _handle_freetext_goal_flow(update, ctx):
        return

    # Goal picker for add_topic flow
    if await _handle_add_topic_goal_picker(update, ctx):
        return

    # Time-type picker response
    if await _handle_time_picker_response(update, ctx):
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


async def _check_and_onboard_new_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if user is new and was shown onboarding (caller should return early)."""
    uid = update.effective_user.id
    # Check cache to avoid hitting DB on every message
    if ctx.user_data.get("onboarded"):
        return False
    # Check Supabase settings table
    sb = __import__("supabase_svc").get_client()
    res = sb.table("settings").select("user_id").eq("user_id", uid).execute()
    if res.data:
        ctx.user_data["onboarded"] = True
        return False
    # New user — create settings row and send onboarding
    settings_svc.get_settings(uid)  # creates defaults
    ctx.user_data["onboarded"] = True
    first_name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"Hey {first_name}! 👋 I'm disrupto — your AI life OS.\n\n"
        "I help you track habits, study smarter, and stay on top of your day. "
        "Just talk to me naturally — no commands needed.\n\n"
        "Ready to get started? Tell me one thing you want to track or learn. 🚀"
    )
    return True


async def handle_free_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import claude_svc
    from tasks.handlers import _parse_and_respond
    from telegram.constants import ChatAction
    text = update.message.text.strip()

    # New user onboarding — check before anything else
    if await _check_and_onboard_new_user(update, ctx):
        return

    # Pre-check cancel words BEFORE classify_intent — instant response, no API call
    ascii_text = text.encode("ascii", errors="ignore").decode().strip()
    cancel_words = {"cancel", "stop", "quit", "exit", "nevermind", "never mind", "forget it"}
    if ascii_text.lower() in cancel_words:
        uid = update.effective_user.id
        # Clean up quiz state if active
        if uid in ctx.bot_data.get("quiz_state", {}):
            ctx.bot_data["quiz_state"].pop(uid, None)
            await update.message.reply_text(
                "Quiz cancelled. Come back whenever you're ready!",
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            ctx.user_data.clear()
            await update.message.reply_text("Cancelled! 👍", reply_markup=ReplyKeyboardRemove())
        return

    # Bulk topic import — numbered/bulleted list while user has an active goal
    parsed_list = _parse_bullet_list(text)
    if parsed_list:
        import study.svc as study_svc_bulk
        goals = study_svc_bulk.list_goals(update.effective_user.id)
        if goals:
            goal = goals[0]
            created = study_svc_bulk.bulk_create_topics(goal["id"], parsed_list)
            numbered = "\n".join(f"{i+1}. {t['title']}" for i, t in enumerate(created))
            await update.message.reply_text(
                f"Added {len(created)} topics to *{goal['name']}* 📚\n\n{numbered}\n\nUse /study to go through them.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    # Pre-check: ignore emoji-only messages and bare dismissal/reaction phrases
    if not ascii_text:  # emoji-only or symbols with no text
        return
    # Use ascii_text for word check so "❌ Cancel" → "Cancel" → caught
    # Also catches stale keyboard button replies that arrive outside an active flow
    if ascii_text.lower() in {
        "back", "no", "nope", "nah",
        "nm", "nothing",
        "wtf", "lol", "lmao", "omg", "damn", "hmm", "hm", "ok",
        "okay", "k", "kk", "fine", "cool", "nice", "great",
        # keyboard button replies that should never reach Gemini
        "yeah, add it", "edit", "yes, delete it",
        "none (root topic)", "name", "description", "target date",
    }:
        await update.message.reply_text("Hey! 👋 What do you want to track? Or say 'help' to see what I can do.")
        return

    # Build rolling chat context (last 5 turns)
    history = ctx.user_data.setdefault("chat_history", [])
    history.append(f"User: {text}")
    if len(history) > 10:
        history[:] = history[-10:]
    context = "\n".join(history[:-1])  # exclude current message

    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        intent = claude_svc.classify_intent(text, context=context)
    except Exception:
        intent = "chat"

    if intent == "task":
        await _parse_and_respond(update, ctx, text, claude_svc, context=context)
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
    elif intent == "show_topics":
        await study_handlers.cmd_topics(update, ctx)
    elif intent == "study_topic":
        topic_name = ""
        try:
            topic_name = claude_svc.extract_topic_name(text)
        except Exception:
            pass
        if topic_name:
            await study_handlers.handle_study_topic(update, ctx, topic_name)
        else:
            await update.message.reply_text(
                "Which topic did you want to study? Try: 'study OOP Basics' or say 'show topics' to see your list."
            )
    elif intent == "skip_topic":
        topic_name = ""
        try:
            topic_name = claude_svc.extract_topic_name(text)
        except Exception:
            pass
        if topic_name:
            await study_handlers.handle_skip_topic_request(update, ctx, topic_name)
        else:
            await update.message.reply_text(
                "Which topic did you want to skip? Try: 'skip OOP Basics' or say 'show topics' to see your list."
            )
    elif intent == "start_study":
        await study_handlers.cmd_study(update, ctx)
    elif intent == "create_goal":
        await handle_create_goal_freetext(update, ctx, text, claude_svc)
    elif intent == "study":
        await update.message.reply_text(
            "Sounds like you want to learn something! 📚\n\n"
            "Say 'I want to learn X' to create a goal, then say 'study' to start a session.",
        )
    elif intent == "reschedule_task":
        await handle_reschedule_task_freetext(update, ctx, text, claude_svc)
    elif intent == "set_time":
        await handle_set_time_freetext(update, ctx, text, claude_svc)
    elif intent == "add_topic":
        await handle_add_topic_freetext(update, ctx, text, claude_svc)
    elif intent == "manage_goal":
        await handle_manage_goal_freetext(update, ctx, text, claude_svc)
    elif intent == "clear_data":
        await cmd_clear(update, ctx)
    elif intent == "twilio":
        await _handle_twilio_freetext(update, ctx, text)
    elif intent == "show_help":
        await cmd_info(update, ctx)
    elif intent == "show_settings":
        await tasks_handlers.cmd_settings(update, ctx)
    elif intent == "mark_important":
        await handle_mark_important_freetext(update, ctx, text, claude_svc)
    elif intent == "delay":
        await handle_delay_intent(update, ctx, text)
    elif intent in ("done", "skip_task", "delete_task", "pause_task"):
        # Bare "done"/"skip" with no task name — check last reminded task first
        if intent in ("done", "skip_task") and text.lower().strip() in ("done", "skip"):
            uid2 = update.effective_user.id
            last_id = ctx.bot_data.get("last_reminded", {}).get(uid2)
            if last_id:
                await handle_last_reminded_action(update, ctx, last_id, intent)
                return
        await handle_task_action_freetext(update, ctx, text, intent, claude_svc)
    else:
        # General chat — Learnix responds naturally
        try:
            context_block = f"Recent conversation:\n{context}\n\n" if context else ""
            reply = claude_svc._ask(
                f"{context_block}You are Learnix, a friendly AI life coach. Reply casually and helpfully in 1-2 sentences.\n\nUser: {text}",
                max_tokens=4096,
            )
            history.append(f"Bot: {reply[:200]}")
            await update.message.reply_text(reply)
        except Exception:
            await update.message.reply_text("I'm here! Say 'help' to see what I can do.")


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Transcribe a Telegram voice note and route to free-text handler."""
    import tempfile
    from pathlib import Path
    import claude_svc

    voice = update.message.voice
    if not voice:
        return

    await update.message.chat.send_action(__import__("telegram").constants.ChatAction.TYPING)

    # Download voice file to a temp path
    tmp_path = None
    try:
        file = await ctx.bot.get_file(voice.file_id)
        suffix = ".oga"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

        # Transcribe via Gemini
        try:
            transcribed = claude_svc.transcribe_voice(tmp_path)
        except Exception as e:
            logger.error(f"Voice transcription failed: {e}")
            await update.message.reply_text(
                "Sorry, I couldn't understand that voice note. Try typing instead!"
            )
            return
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    if not transcribed:
        await update.message.reply_text("I heard something but couldn't make it out. Try again!")
        return

    # Echo transcription header, then process as free text
    # We reuse handle_free_text by patching update.message.text temporarily
    # Instead, create a synthetic text routing call
    echo_prefix = f"🎤 I heard: _{transcribed}_\n\n"

    # Route through the same free-text intent system
    # We can't easily monkey-patch update, so we call the core logic directly
    original_reply = update.message.reply_text

    _prefix_sent = False

    async def prefixed_reply(msg, **kwargs):
        nonlocal _prefix_sent
        if not _prefix_sent:
            _prefix_sent = True
            combined = echo_prefix + msg
            return await original_reply(combined, **kwargs)
        return await original_reply(msg, **kwargs)

    update.message.reply_text = prefixed_reply  # type: ignore[method-assign]
    try:
        # Temporarily set message text so handle_free_text reads it
        update.message.text = transcribed  # type: ignore[assignment]
        await handle_free_text(update, ctx)
    finally:
        update.message.reply_text = original_reply  # type: ignore[method-assign]


import re as _re


def _parse_bullet_list(text: str) -> list[str] | None:
    """If text looks like a numbered or bulleted list with >=2 items, return the items.
    Returns None otherwise."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    items = []
    for line in lines:
        # Match: "1. X", "1) X", "- X", "• X", "* X"
        m = _re.match(r'^(?:\d+[.)]\s*|[-•*]\s+)(.+)$', line)
        if m:
            items.append(m.group(1).strip())
    return items if len(items) >= 2 else None


_STEM_MAP = {
    "reading": "read",
    "running": "run",
    "pushups": "pushup",
    "pushup": "push",
    "doing": "do",
    "writing": "write",
    "studying": "study",
    "working": "work",
    "sleeping": "sleep",
    "walking": "walk",
    "drinking": "drink",
    "eating": "eat",
    "meditating": "meditate",
    "stretching": "stretch",
    "exercising": "exercise",
}


def _stem_words(words: set[str]) -> set[str]:
    """Return words expanded with their stems (original words kept too)."""
    stemmed = set(words)
    for w in words:
        if w in _STEM_MAP:
            stemmed.add(_STEM_MAP[w])
    return stemmed


def _fuzzy_match_task(task_name: str, tasks: list[dict]) -> list[dict]:
    """Return tasks that best match task_name using progressively looser strategies."""
    import difflib

    needle = task_name.lower().strip()
    if not needle:
        return []

    # Try 1: substring match (original or reversed)
    matches = []
    for t in tasks:
        haystack = t["title"].lower()
        if needle in haystack or haystack in needle:
            matches.append(t)
    if matches:
        return matches

    # Try 2: any needle word appears in any task title word (with stemming)
    needle_words = _stem_words(set(needle.split()))
    for t in tasks:
        title_words = _stem_words(set(t["title"].lower().split()))
        if needle_words & title_words:
            matches.append(t)
    if matches:
        return matches

    # Try 3: any task title word appears in the needle (reverse word overlap)
    for t in tasks:
        title_words = _stem_words(set(t["title"].lower().split()))
        if title_words & needle_words:
            if t not in matches:
                matches.append(t)
    if matches:
        return matches

    # Try 4: difflib ratio > 0.4 between needle and each title
    scored = []
    for t in tasks:
        ratio = difflib.SequenceMatcher(None, needle, t["title"].lower()).ratio()
        if ratio > 0.4:
            scored.append((ratio, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:3]]


async def handle_last_reminded_action(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    task_id: str,
    intent: str,
) -> None:
    """Act on the last-reminded task directly without fuzzy matching."""
    import tasks.svc as task_db
    import analytics_svc
    import settings_svc as settings_db

    uid = update.effective_user.id
    # Clear last_reminded so it doesn't fire twice
    ctx.bot_data.get("last_reminded", {}).pop(uid, None)

    # Fetch the task to get its title/recurrence
    all_tasks = task_db.list_tasks(uid)
    task = next((t for t in all_tasks if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text("Couldn't find that task. Try /tasks to see your list.")
        return

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

    # For done/skip_task: check if a task was recently reminded — use it directly
    if intent in ("done", "skip_task"):
        last_id = ctx.bot_data.get("last_reminded", {}).get(uid)
        if last_id:
            # Extract task name to see if user is referring to something specific
            try:
                task_name = claude_svc.extract_task_name_from_message(text)
            except Exception:
                task_name = ""
            if not task_name:
                await handle_last_reminded_action(update, ctx, last_id, intent)
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
        # Ambiguous — store pending state then ask which one
        ctx.user_data["pending_task_action"] = {
            "action": intent,
            "candidates": [{"id": t["id"], "title": t["title"]} for t in matches[:3]],
        }
        names = "\n".join(f"  • {t['title']}" for t in matches[:3])
        await update.message.reply_text(
            f"Which task did you mean?\n{names}",
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


async def handle_reschedule_task_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    claude_svc,
) -> None:
    """Handle 'reschedule_task' intent: change reminder time for a specific task."""
    import tasks.svc as task_db
    import pytz
    from datetime import datetime, timezone, timedelta

    IST = pytz.timezone("Asia/Kolkata")
    uid = update.effective_user.id

    try:
        info = claude_svc.extract_reschedule_info(text)
    except Exception:
        info = {"task_name": "", "time": ""}

    task_name = info.get("task_name", "").strip()
    time_str = info.get("time", "").strip()

    if not task_name:
        await update.message.reply_text(
            "Which task do you want to reschedule? Try: 'remind me about workout at 6am'."
        )
        return

    tasks = task_db.list_tasks(uid)
    if not tasks:
        await update.message.reply_text("You don't have any active tasks right now.")
        return

    matches = _fuzzy_match_task(task_name, tasks)
    if not matches:
        await update.message.reply_text(
            f"Couldn't find a task matching *{task_name}*. Say /tasks to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if len(matches) > 1:
        ctx.user_data["pending_task_action"] = {
            "action": "reschedule_task",
            "candidates": [{"id": t["id"], "title": t["title"]} for t in matches[:3]],
            "time_str": time_str,
        }
        names = "\n".join(f"  • {t['title']}" for t in matches[:3])
        await update.message.reply_text(
            f"Which task did you mean?\n{names}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    task = matches[0]

    if not time_str:
        await update.message.reply_text(
            f"What time should I remind you about *{task['title']}*? (e.g. '6am', '8:30pm')",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Parse HH:MM into today's datetime in IST, push to tomorrow if already passed
    try:
        h, m = map(int, time_str.split(":"))
        now_ist = datetime.now(IST)
        target_ist = now_ist.replace(hour=h, minute=m, second=0, microsecond=0)
        if target_ist <= now_ist:
            target_ist += timedelta(days=1)
        new_time_utc = target_ist.astimezone(timezone.utc)
    except Exception:
        await update.message.reply_text(
            f"Couldn't parse that time. Try something like '6am' or '20:30'."
        )
        return

    task_db.reschedule_task(task["id"], new_time_utc)

    when_label = new_time_utc.astimezone(IST).strftime("%I:%M %p")
    day_label = "today" if new_time_utc.astimezone(IST).date() == datetime.now(IST).date() else "tomorrow"
    await update.message.reply_text(
        f"Done! I'll remind you about *{task['title']}* at {when_label} {day_label} 👍",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_set_time_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    claude_svc,
) -> None:
    """Handle 'set_time' intent expressed in free text."""
    try:
        info = claude_svc.extract_set_time_info(text)
    except Exception:
        info = {"time_type": "", "time_value": ""}

    time_type = info.get("time_type", "")
    time_value = info.get("time_value", "")

    # If we have both — apply immediately
    if time_type and time_value:
        uid = update.effective_user.id
        try:
            h, m = map(int, time_value.split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except Exception:
            await update.message.reply_text(
                f"Couldn't parse that time. Try something like 'set morning to 08:00'."
            )
            return
        if time_type == "morning":
            settings_svc.set_morning_brief_time(uid, time_value)
            label = "Morning brief"
        elif time_type == "study":
            settings_svc.set_daily_time(uid, time_value)
            label = "Study time"
        else:  # eod
            settings_svc.set_eod_time(uid, time_value)
            label = "EOD check-in"
        await update.message.reply_text(
            f"Done! {label} set to *{time_value}* IST. 🕐",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Have a time but not which type — ask
    if time_value and not time_type:
        ctx.user_data["setting_time_value_pending"] = time_value
        buttons = [["Morning brief"], ["Study session"], ["EOD check-in"]]
        await update.message.reply_text(
            f"Got it — {time_value}. Which reminder is that for?",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        ctx.user_data["setting_time_for_picker"] = True
        return

    # Have a type but no time — ask for the time
    if time_type and not time_value:
        label_map = {"morning": "morning brief", "study": "study session", "eod": "EOD check-in"}
        label = label_map.get(time_type, time_type)
        ctx.user_data["setting_time_for"] = time_type
        await update.message.reply_text(
            f"What time for your {label}? (HH:MM IST, e.g. `09:00`)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Neither — ask which they want to change
    await update.message.reply_text(
        "Which time do you want to change?\n\n"
        "• Morning brief\n• Study session\n• EOD check-in\n\n"
        "Say something like 'set morning brief to 8am'."
    )


async def _handle_time_picker_response(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Consume a reply to the time-type picker. Returns True if consumed."""
    if not ctx.user_data.get("setting_time_for_picker"):
        return False
    choice = update.message.text.strip().lower()
    type_map = {
        "morning brief": "morning",
        "study session": "study",
        "eod check-in": "eod",
    }
    time_type = type_map.get(choice)
    if not time_type:
        # Not a valid picker answer — clear and let message fall through
        ctx.user_data.pop("setting_time_for_picker", None)
        ctx.user_data.pop("setting_time_value_pending", None)
        return False
    time_value = ctx.user_data.pop("setting_time_value_pending", "")
    ctx.user_data.pop("setting_time_for_picker", None)
    uid = update.effective_user.id
    if time_type == "morning":
        settings_svc.set_morning_brief_time(uid, time_value)
        label = "Morning brief"
    elif time_type == "study":
        settings_svc.set_daily_time(uid, time_value)
        label = "Study time"
    else:
        settings_svc.set_eod_time(uid, time_value)
        label = "EOD check-in"
    await update.message.reply_text(
        f"Done! {label} set to *{time_value}* IST. 🕐",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return True


async def handle_add_topic_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    claude_svc,
) -> None:
    """Handle 'add_topic' intent in free text."""
    import study.svc as study_svc

    try:
        info = claude_svc.extract_add_topic_info(text)
    except Exception:
        info = {"topic_name": "", "goal_name": ""}

    topic_name = info.get("topic_name", "").strip()
    goal_hint = info.get("goal_name", "").strip()

    if not topic_name:
        await update.message.reply_text(
            "What topic do you want to add? Try: 'add Recursion to my Python goal'."
        )
        return

    uid = update.effective_user.id
    goals = study_svc.list_goals(uid)
    if not goals:
        await update.message.reply_text("You don't have any goals yet. Say 'I want to learn X' to create one first!")
        return

    # Match goal by hint, or default to single goal
    matched_goal = None
    if goal_hint:
        goal_hint_lower = goal_hint.lower()
        for g in goals:
            if goal_hint_lower in g["name"].lower() or g["name"].lower() in goal_hint_lower:
                matched_goal = g
                break

    if not matched_goal and len(goals) == 1:
        matched_goal = goals[0]

    if not matched_goal:
        # Multiple goals, ambiguous — ask which
        buttons = [[g["name"]] for g in goals]
        ctx.user_data["pending_add_topic_name"] = topic_name
        await update.message.reply_text(
            f"Which goal should I add *{topic_name}* to?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        ctx.user_data["add_topic_goal_picker"] = [g["id"] for g in goals]
        ctx.user_data["add_topic_goals_map"] = {g["name"]: g for g in goals}
        return

    # Add directly
    existing = study_svc.list_topics_for_goal(matched_goal["id"])
    order_index = len(existing)
    study_svc.create_topic(goal_id=matched_goal["id"], title=topic_name, order_index=order_index)
    await update.message.reply_text(
        f"Added! 📌 *{topic_name}* is now in *{matched_goal['name']}*.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_add_topic_goal_picker(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Consume goal-picker response for add_topic flow. Returns True if consumed."""
    if "add_topic_goal_picker" not in ctx.user_data:
        return False
    chosen = update.message.text.strip()
    goals_map = ctx.user_data.pop("add_topic_goals_map", {})
    ctx.user_data.pop("add_topic_goal_picker", None)
    topic_name = ctx.user_data.pop("pending_add_topic_name", "")
    goal = goals_map.get(chosen)
    if not goal:
        await update.message.reply_text(
            "Hmm, couldn't find that goal. Try again: 'add X to my Y goal'.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return True
    import study.svc as study_svc
    existing = study_svc.list_topics_for_goal(goal["id"])
    study_svc.create_topic(goal_id=goal["id"], title=topic_name, order_index=len(existing))
    await update.message.reply_text(
        f"Added! 📌 *{topic_name}* is now in *{goal['name']}*.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return True


async def handle_manage_goal_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    claude_svc,
) -> None:
    """Handle 'manage_goal' intent (delete/pause/edit) in free text."""
    import study.svc as study_svc

    try:
        action = claude_svc.extract_manage_goal_action(text)
        goal_name_hint = claude_svc.extract_goal_name_from_message(text)
    except Exception:
        action = ""
        goal_name_hint = ""

    uid = update.effective_user.id
    all_goals = study_svc.list_goals(uid) + study_svc.list_goals(uid, status="paused")
    if not all_goals:
        await update.message.reply_text("You don't have any goals yet.")
        return

    # Try to match goal by hint
    matched_goal = None
    if goal_name_hint:
        hint_lower = goal_name_hint.lower()
        for g in all_goals:
            if hint_lower in g["name"].lower() or g["name"].lower() in hint_lower:
                matched_goal = g
                break

    if not matched_goal and len(all_goals) == 1:
        matched_goal = all_goals[0]

    if action == "delete":
        # Route to deletegoal conversation
        await study_handlers.cmd_deletegoal(update, ctx)
    elif action == "pause":
        await study_handlers.cmd_pausegoal(update, ctx)
    elif action == "edit":
        await study_handlers.cmd_editgoal(update, ctx)
    else:
        # Ambiguous action — show options
        goal_str = f" *{matched_goal['name']}*" if matched_goal else ""
        await update.message.reply_text(
            f"What do you want to do with{goal_str} your goal?\n\n"
            "• 'delete my X goal'\n"
            "• 'pause my X goal'\n"
            "• 'edit my X goal'"
        )


async def handle_create_goal_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    claude_svc,
) -> None:
    """Handle 'create_goal' intent: extract subject, then start goal flow pre-filled."""
    try:
        goal_name = claude_svc.extract_goal_name_from_message(text)
    except Exception:
        goal_name = ""

    if not goal_name:
        # Fall back to starting goal flow normally
        await study_handlers.cmd_goal(update, ctx)
        return

    # Pre-fill the goal name and jump straight to difficulty selection
    ctx.user_data["goal_name"] = goal_name
    ctx.user_data["goal_desc"] = ""
    # We can't enter the ConversationHandler mid-flow from outside it,
    # so we send the difficulty prompt and set a flag to handle the next message
    buttons = [["Easy"], ["Medium"], ["Hard"]]
    await update.message.reply_text(
        f"Let's set up a learning goal! 🎯\n\nGoal: *{goal_name}*\n\nWhat difficulty?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    ctx.user_data["freetext_goal_state"] = "difficulty"


async def _handle_freetext_goal_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle multi-step goal creation started from free text. Returns True if consumed."""
    state = ctx.user_data.get("freetext_goal_state")
    if not state:
        return False

    text = update.message.text.strip()

    if state == "difficulty":
        choice = text.lower()
        if choice not in ("easy", "medium", "hard"):
            buttons = [["Easy"], ["Medium"], ["Hard"]]
            await update.message.reply_text(
                "Please pick Easy, Medium, or Hard:",
                reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
            )
            return True
        ctx.user_data["goal_difficulty"] = choice
        ctx.user_data["freetext_goal_state"] = "deadline"
        await update.message.reply_text(
            "Target date? (YYYY-MM-DD, e.g. 2026-12-01) Or '-' to skip:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return True

    if state == "deadline":
        from datetime import datetime as _dt
        import study.svc as study_svc

        deadline = text
        if deadline != "-":
            try:
                _dt.fromisoformat(deadline)
            except ValueError:
                await update.message.reply_text("Hmm, that date doesn't look right. Use YYYY-MM-DD or '-' to skip:")
                return True
        else:
            deadline = None

        uid = update.effective_user.id
        name = ctx.user_data.get("goal_name", "New Goal")
        desc = ctx.user_data.get("goal_desc", "")
        difficulty = ctx.user_data.get("goal_difficulty", "medium")
        study_svc.create_goal(uid, name, desc, deadline, difficulty=difficulty)
        diff_label = {"easy": "Easy 🟢", "medium": "Medium 🟡", "hard": "Hard 🔴"}.get(difficulty, "Medium 🟡")

        # Clean up
        for key in ("goal_name", "goal_desc", "goal_difficulty", "freetext_goal_state"):
            ctx.user_data.pop(key, None)

        await update.message.reply_text(
            f"Goal created! 🎯 *{name}* ({diff_label}) is on the list.\n\n"
            f"Say 'break down {name}' to auto-generate topics, or 'add topic X' to add manually.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    return False


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
            difficulty = study_svc.get_goal_difficulty(matched_goal)
            subtopics = claude_svc.breakdown_study_goal(matched_goal["name"], difficulty=difficulty)
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
                "Call reminders on! 📞 I'll call you for ALL reminders — habits, one-time reminders, everything. Share your number:",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup([[btn]], one_time_keyboard=True, resize_keyboard=True),
            )
        else:
            await update.message.reply_text(
                "Call reminders on for all reminders! 📞",
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


async def _handle_twilio_freetext(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    uid = update.effective_user.id
    lower = text.lower()
    off_words = {"off", "disable", "stop", "turn off", "deactivate", "no calls", "no call"}
    is_off = any(w in lower for w in off_words)
    if is_off:
        twilio_svc.set_twilio_enabled(uid, False)
        await update.message.reply_text("Call reminders off. ⏸", parse_mode="HTML")
    else:
        twilio_svc.set_twilio_enabled(uid, True)
        if not twilio_svc.get_phone_number(uid):
            btn = KeyboardButton("📱 Share my number", request_contact=True)
            await update.message.reply_text(
                "Call reminders on! 📞 I'll call you for ALL reminders. Share your number:",
                reply_markup=ReplyKeyboardMarkup([[btn]], one_time_keyboard=True, resize_keyboard=True),
            )
        else:
            await update.message.reply_text("Call on 📞", reply_markup=ReplyKeyboardRemove())


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


async def handle_mark_important_freetext(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    claude_svc,
) -> None:
    """Handle 'mark_important' intent: mark a task as important."""
    import tasks.svc as task_db

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
        # Try last reminded task
        last_id = ctx.bot_data.get("last_reminded", {}).get(uid)
        if last_id:
            task = next((t for t in tasks if t["id"] == last_id), None)
            if task:
                task_db.mark_important(task["id"])
                await update.message.reply_text(
                    f"Got it — *{task['title']}* is now marked ⚡ important. "
                    f"I'll keep reminding you every hour until you do it.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
        await update.message.reply_text("Which task should I mark as important? Try: 'mark workout as important'.")
        return

    matches = _fuzzy_match_task(task_name, tasks)
    if not matches:
        await update.message.reply_text(
            f"Couldn't find a task matching *{task_name}*. Try /tasks to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if len(matches) > 1:
        ctx.user_data["pending_task_action"] = {
            "action": "mark_important",
            "candidates": [{"id": t["id"], "title": t["title"]} for t in matches[:3]],
        }
        names = "\n".join(f"  • {t['title']}" for t in matches[:3])
        await update.message.reply_text(
            f"Which task did you mean?\n{names}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    task = matches[0]
    task_db.mark_important(task["id"])
    await update.message.reply_text(
        f"Got it — *{task['title']}* is now marked ⚡ important. "
        f"I'll keep reminding you every hour until you do it.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_delay_intent(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> None:
    """Handle explicit 'delay' intent — extract duration if given, else ask."""
    uid = update.effective_user.id
    last_id = ctx.bot_data.get("last_reminded", {}).get(uid)
    if not last_id:
        await update.message.reply_text("No recent reminder to delay. Say the task name explicitly, e.g. 'delay workout by 30 mins'.")
        return

    duration_minutes = _parse_delay_duration(text)
    if duration_minutes is None:
        # Ask how long
        ctx.user_data["pending_delay_task_id"] = last_id
        await update.message.reply_text(
            "How long? Reply with a time like '30 mins', '2 hours', or just say '1 hour' to use the default."
        )
        return

    await _apply_delay(update, ctx, last_id, duration_minutes)


async def handle_delay_duration_response(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Called from handle_text. Handles duration reply after a 'delay?' prompt. Returns True if consumed."""
    task_id = ctx.user_data.get("pending_delay_task_id")
    if not task_id:
        return False

    text = update.message.text.strip()
    duration_minutes = _parse_delay_duration(text)
    if duration_minutes is None:
        # Default 1 hour if we can't parse
        duration_minutes = 60

    ctx.user_data.pop("pending_delay_task_id", None)
    await _apply_delay(update, ctx, task_id, duration_minutes)
    return True


async def _apply_delay(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    task_id: str,
    duration_minutes: int,
) -> None:
    """Apply a delay to a task by rescheduling its next_reminder_at."""
    import tasks.svc as task_db
    from datetime import datetime, timezone, timedelta

    uid = update.effective_user.id
    all_tasks = task_db.list_tasks(uid)
    task = next((t for t in all_tasks if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text("Couldn't find that task. Try /tasks to see your list.")
        return

    new_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    task_db.reschedule_task(task_id, new_time)

    if duration_minutes < 60:
        duration_str = f"{duration_minutes} min"
    elif duration_minutes == 60:
        duration_str = "1 hour"
    else:
        hours = duration_minutes // 60
        mins = duration_minutes % 60
        duration_str = f"{hours}h" + (f" {mins}m" if mins else "")

    await update.message.reply_text(
        f"Got it! I'll remind you about *{task['title']}* in {duration_str}. ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )


def _parse_delay_duration(text: str) -> int | None:
    """Parse delay duration from text. Returns minutes, or None if can't parse.
    Also detects bare 'delay' or 'remind me later' with no duration.
    """
    import re
    text_lower = text.lower().strip()

    # Check for bare delay words with no duration info
    bare_delay = re.match(r'^(delay|remind me later|later|snooze)$', text_lower)
    if bare_delay:
        return None

    # Look for hour + minute patterns
    # e.g. "2 hours", "1.5 hours", "30 mins", "45 minutes", "1 hour 30 mins"
    hours_match = re.search(r'(\d+(?:\.\d+)?)\s*h(?:ours?)?', text_lower)
    mins_match = re.search(r'(\d+)\s*m(?:in(?:utes?)?)?', text_lower)

    total_minutes = 0
    found = False

    if hours_match:
        total_minutes += int(float(hours_match.group(1)) * 60)
        found = True
    if mins_match:
        total_minutes += int(mins_match.group(1))
        found = True

    if found and total_minutes > 0:
        return total_minutes

    # Bare number — treat as minutes
    bare_num = re.match(r'^(\d+)$', text_lower)
    if bare_num:
        return int(bare_num.group(1))

    return None


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
    async def _global_cancel(u, c):
        uid = u.effective_user.id
        # If user is mid-quiz, clean up quiz state
        if uid in c.bot_data.get("quiz_state", {}):
            c.bot_data["quiz_state"].pop(uid, None)
            await u.message.reply_text(
                "Quiz cancelled. Come back whenever you're ready!",
            )
        else:
            await u.message.reply_text("Nothing to cancel. 👍")
    app.add_handler(CommandHandler("cancel", _global_cancel))

    async def _cmd_reset(u, c):
        c.user_data.clear()
        await u.message.reply_text("State cleared. 👍 You can start fresh now.", reply_markup=ReplyKeyboardRemove())

    app.add_handler(CommandHandler("reset", _cmd_reset))

    # Study handlers
    for h in study_handlers.get_handlers():
        app.add_handler(h)

    # Task handlers
    for h in tasks_handlers.get_handlers():
        app.add_handler(h)

    # Contact sharing handler (for /twilio on phone number collection)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Voice note handler
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

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

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Unhandled exception", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text("Oops, something broke. Try again or use /cancel to reset.")
            except Exception:
                pass

    app.add_error_handler(error_handler)
    app.post_init = on_startup
    logger.info("Starting Learnix bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
