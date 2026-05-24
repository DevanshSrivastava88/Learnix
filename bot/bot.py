"""
bot.py — Learnix Telegram bot. Main entry point.

Architecture:
- ConversationHandlers for multi-step flows (/goal, /addtopic, /settime, quiz)
- APScheduler (via python-telegram-bot job_queue) for proactive daily sessions
- pending_sessions dict: {user_id: topic_id} for yes/later replies
"""

import os
import logging
from datetime import datetime, time as dtime
from typing import Optional

import pytz
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue,
)

import supabase_svc as db
import claude_svc as claude

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# Maps telegram user_id → topic_id awaiting "yes"/"later" reply
pending_sessions: dict[int, str] = {}

# Quiz state: user_id → {topic_id, questions, q_index, score, topic}
quiz_state: dict[int, dict] = {}

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------

# /goal flow
GOAL_NAME, GOAL_DESC, GOAL_DEADLINE = range(3)

# /addtopic flow
AT_GOAL_SELECT, AT_PARENT_SELECT, AT_TITLE, AT_DESC, AT_NOTES = range(5, 10)

# /settime flow
ST_TIME = 20

# quiz flow (inline, not a ConversationHandler — handled via MessageHandler)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md_escape(text: str) -> str:
    """Escape MarkdownV2 special chars."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


def format_goal_status(goal: dict) -> str:
    counts = db.count_topics_for_goal(goal["id"])
    total = counts["total"]
    completed = counts["completed"]
    target = goal.get("target_date", "")
    name = goal["name"]

    if total == 0:
        progress = "No topics yet"
    else:
        pct = int(completed / total * 100)
        bar_filled = int(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        progress = f"{bar} {completed}/{total} ({pct}%)"

    # Deadline check
    deadline_str = ""
    if target:
        try:
            target_dt = datetime.fromisoformat(str(target))
            now = datetime.now(IST)
            if target_dt.tzinfo is None:
                target_dt = IST.localize(target_dt)
            days_left = (target_dt.date() - now.date()).days
            if days_left < 0:
                deadline_str = f"  ⚠️ Overdue by {abs(days_left)}d"
            elif days_left == 0:
                deadline_str = "  🔥 Due today!"
            elif days_left <= 7:
                deadline_str = f"  ⏰ {days_left}d left"
            else:
                deadline_str = f"  📅 {days_left}d left"
        except Exception:
            deadline_str = f"  📅 {target}"

    return f"*{name}*{deadline_str}\n{progress}"


def get_on_track_status(goal: dict) -> str:
    """Return On track / Behind label for proactive message."""
    counts = db.count_topics_for_goal(goal["id"])
    total = counts["total"]
    completed = counts["completed"]
    target = goal.get("target_date")

    if not target or total == 0:
        return "On track ✅"

    try:
        target_dt = datetime.fromisoformat(str(target))
        now = datetime.now(IST)
        if target_dt.tzinfo is None:
            target_dt = IST.localize(target_dt)
        days_total = max(1, (target_dt.date() - now.date()).days)
        remaining = total - completed
        # If remaining topics > days left, behind
        if remaining > days_total:
            behind = remaining - days_total
            return f"⚠️ Behind by {behind} topics"
        return "On track ✅"
    except Exception:
        return "On track ✅"


# ---------------------------------------------------------------------------
# /start — Dashboard
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    # Ensure user id is stored
    settings = db.get_settings()
    if not settings.get("telegram_user_id"):
        db.set_telegram_user_id(user_id)

    goals = db.list_goals("in_progress")
    settings = db.get_settings()
    streak = settings.get("streak", 0) or 0
    session_time = settings.get("daily_session_time", "09:00")

    lines = ["*📚 Learnix Dashboard*\n"]

    if not goals:
        lines.append("No active goals. Use /goal to create one!")
    else:
        lines.append("*Active Goals:*")
        for g in goals:
            lines.append(format_goal_status(g))
            lines.append("")

    lines.append(f"🔥 Streak: {streak} day(s)")
    lines.append(f"⏰ Daily session: {session_time} IST")
    lines.append("\n*Commands:*")
    lines.append("/study — Start a study session now")
    lines.append("/goal — Create a new goal")
    lines.append("/addtopic — Add a topic")
    lines.append("/progress — Full progress view")
    lines.append("/settime — Change daily session time")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /progress — Full progress
# ---------------------------------------------------------------------------

async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    goals = db.list_goals("in_progress")
    if not goals:
        await update.message.reply_text("No active goals yet. Use /goal to create one.")
        return

    lines = ["*📊 Full Progress*\n"]
    for goal in goals:
        lines.append(format_goal_status(goal))
        topics = db.list_topics_for_goal(goal["id"])
        if topics:
            lines.append("Topics:")
            for t in topics:
                if t.get("parent_id"):
                    prefix = "  └ "
                else:
                    prefix = "  • "
                status_icon = {
                    "completed": "✅",
                    "needs_revision": "🔁",
                    "not_started": "⬜",
                }.get(t["status"], "⬜")
                score_str = f" [{t['score']}]" if t.get("score") else ""
                lines.append(f"{prefix}{status_icon} {t['title']}{score_str}")
        lines.append("")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# /goal — Create goal (ConversationHandler)
# ---------------------------------------------------------------------------

async def cmd_goal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Let's create a new learning goal! 🎯\n\nWhat's the name of your goal?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GOAL_NAME


async def goal_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["goal_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Great! Give a short description (or send '-' to skip):"
    )
    return GOAL_DESC


async def goal_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["goal_desc"] = "" if desc == "-" else desc
    await update.message.reply_text(
        "What's your target completion date? (format: YYYY-MM-DD, e.g. 2025-08-01)"
    )
    return GOAL_DEADLINE


async def goal_get_deadline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    deadline = update.message.text.strip()
    # Basic validation
    try:
        datetime.fromisoformat(deadline)
    except ValueError:
        await update.message.reply_text(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2025-08-01):"
        )
        return GOAL_DEADLINE

    name = ctx.user_data["goal_name"]
    desc = ctx.user_data.get("goal_desc", "")
    goal = db.create_goal(name, desc, deadline)

    await update.message.reply_text(
        f"✅ Goal *{name}* created! Target: {deadline}\n\n"
        "Now use /addtopic to add topics to study.",
        parse_mode=ParseMode.MARKDOWN,
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /addtopic — Add topic/subtopic (ConversationHandler)
# ---------------------------------------------------------------------------

async def cmd_addtopic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    goals = db.list_goals("in_progress")
    if not goals:
        await update.message.reply_text("No active goals. Create one with /goal first.")
        return ConversationHandler.END

    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals]
    buttons.append(["Cancel"])
    await update.message.reply_text(
        "Which goal is this topic for?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return AT_GOAL_SELECT


async def at_goal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Goal not found. Try /addtopic again.")
        return ConversationHandler.END

    ctx.user_data["selected_goal"] = goal
    # Ask if this is a subtopic
    topics = db.list_topics_for_goal(goal["id"])
    root_topics = [t for t in topics if not t.get("parent_id")]

    if root_topics:
        buttons = [["None (root topic)"]] + [[t["title"]] for t in root_topics] + [["Cancel"]]
        ctx.user_data["root_topics"] = root_topics
        await update.message.reply_text(
            "Is this a subtopic? Select a parent topic, or 'None' for a root topic:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return AT_PARENT_SELECT
    else:
        ctx.user_data["parent_topic"] = None
        await update.message.reply_text(
            "What's the topic title?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return AT_TITLE


async def at_parent_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    if chosen == "None (root topic)":
        ctx.user_data["parent_topic"] = None
    else:
        root_topics = ctx.user_data.get("root_topics", [])
        parent = next((t for t in root_topics if t["title"] == chosen), None)
        ctx.user_data["parent_topic"] = parent

    await update.message.reply_text(
        "What's the topic title?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AT_TITLE


async def at_get_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["topic_title"] = update.message.text.strip()
    await update.message.reply_text(
        "Short description? (or send '-' to skip):"
    )
    return AT_DESC


async def at_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["topic_desc"] = "" if desc == "-" else desc
    await update.message.reply_text(
        "Any notes or key points for this topic? (or send '-' to skip):\n"
        "Tip: Claude will use these notes when teaching you."
    )
    return AT_NOTES


async def at_get_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    notes = update.message.text.strip()
    ctx.user_data["topic_notes"] = "" if notes == "-" else notes

    goal = ctx.user_data["selected_goal"]
    parent = ctx.user_data.get("parent_topic")
    title = ctx.user_data["topic_title"]
    desc = ctx.user_data.get("topic_desc", "")
    topic_notes = ctx.user_data.get("topic_notes", "")

    # Compute order_index
    existing = db.list_topics_for_goal(goal["id"])
    if parent:
        siblings = [t for t in existing if t.get("parent_id") == parent["id"]]
    else:
        siblings = [t for t in existing if not t.get("parent_id")]
    order_index = len(siblings)

    topic = db.create_topic(
        goal_id=goal["id"],
        title=title,
        description=desc,
        notes=topic_notes,
        parent_id=parent["id"] if parent else None,
        order_index=order_index,
    )

    parent_str = f" (under *{parent['title']}*)" if parent else ""
    await update.message.reply_text(
        f"✅ Topic *{title}*{parent_str} added to *{goal['name']}*!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /settime — Set daily session time (ConversationHandler)
# ---------------------------------------------------------------------------

async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    settings = db.get_settings()
    current = settings.get("daily_session_time", "09:00")
    await update.message.reply_text(
        f"Current daily session time: *{current}* IST\n\n"
        "Send the new time in HH:MM format (24h, IST). Example: `14:30`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ST_TIME


async def st_get_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    time_str = update.message.text.strip()
    try:
        h, m = map(int, time_str.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except Exception:
        await update.message.reply_text(
            "Invalid format. Use HH:MM (e.g. 09:00 or 21:30):"
        )
        return ST_TIME

    db.set_daily_time(time_str)

    # Reschedule the daily job
    reschedule_daily_job(ctx.application, h, m)

    await update.message.reply_text(
        f"✅ Daily session time set to *{time_str}* IST. See you then!",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /cancel
# ---------------------------------------------------------------------------

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text(
        "Cancelled. Back to the main menu. /start",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Study session helpers
# ---------------------------------------------------------------------------

async def run_study_session(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                             topic: dict) -> None:
    """
    Full study session: teach → generate quiz → ask questions one by one.
    Quiz state is stored in quiz_state[user_id].
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await ctx.bot.send_message(
        chat_id,
        f"📖 *{topic['title']}*\n\nLet me teach you this topic...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Teaching
    try:
        lesson = claude.teach_topic(topic["title"], topic.get("notes", "") or "")
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Error fetching lesson: {e}")
        return

    await ctx.bot.send_message(chat_id, lesson)

    # Generate quiz
    await ctx.bot.send_message(chat_id, "Now let's test your understanding with 5 questions! 🧠")
    try:
        questions = claude.generate_quiz(topic["title"], topic.get("notes", "") or "")
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Error generating quiz: {e}")
        return

    # Store quiz state
    quiz_state[user_id] = {
        "topic_id": topic["id"],
        "topic": topic,
        "questions": questions,
        "q_index": 0,
        "score": 0,
        "chat_id": chat_id,
    }

    # Ask first question
    await ask_quiz_question(ctx, user_id)


async def ask_quiz_question(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    state = quiz_state.get(user_id)
    if not state:
        return

    idx = state["q_index"]
    questions = state["questions"]
    chat_id = state["chat_id"]

    if idx >= len(questions):
        await finish_quiz(ctx, user_id)
        return

    q = questions[idx]
    num = idx + 1
    total = len(questions)
    await ctx.bot.send_message(
        chat_id,
        f"*Q{num}/{total}:* {q['question']}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def finish_quiz(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    state = quiz_state.pop(user_id, None)
    if not state:
        return

    score = state["score"]
    total = len(state["questions"])
    topic = state["topic"]
    topic_id = state["topic_id"]
    chat_id = state["chat_id"]

    passed = score >= 3

    # Determine new status
    new_status = "completed" if passed else "needs_revision"
    score_str = f"{score}/{total}"

    db.update_topic_status(topic_id, new_status, score_str)
    db.insert_quiz_attempt(topic_id, score)

    if passed:
        db.bubble_up_completion(topic_id)

    # Update streak
    from datetime import date
    new_streak = db.update_streak(date.today())

    result_emoji = "🎉" if passed else "📚"
    result_label = "Passed!" if passed else "Needs revision"

    msg = (
        f"{result_emoji} *Quiz Complete!*\n\n"
        f"Score: *{score_str}*\n"
        f"Result: {result_label}\n"
        f"🔥 Streak: {new_streak} day(s)\n\n"
    )

    if passed:
        msg += "Great work! Topic marked as complete. ✅"
    else:
        msg += "Don't worry — you'll revisit this topic later. Keep going! 💪"

    await ctx.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Quiz answer handler (global MessageHandler)
# ---------------------------------------------------------------------------

async def handle_quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    state = quiz_state.get(user_id)
    if not state:
        return

    user_answer = update.message.text.strip()
    idx = state["q_index"]
    questions = state["questions"]
    q = questions[idx]

    # Score the answer
    try:
        result = claude.score_answer(q["question"], q["expected_answer"], user_answer)
        correct = result.get("correct", False)
        explanation = result.get("explanation", "")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Scoring error: {e}")
        return

    if correct:
        state["score"] += 1
        icon = "✅"
    else:
        icon = "❌"

    await update.message.reply_text(
        f"{icon} {explanation}",
        parse_mode=ParseMode.MARKDOWN,
    )

    state["q_index"] += 1
    await ask_quiz_question(ctx, user_id)


# ---------------------------------------------------------------------------
# /study — Manual trigger
# ---------------------------------------------------------------------------

async def cmd_study(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    topic = db.get_next_pending_topic()
    if not topic:
        await update.message.reply_text(
            "🎉 No pending topics! All done, or add more topics with /addtopic."
        )
        return

    goal = db.get_goal(topic["goal_id"])
    goal_name = goal["name"] if goal else "Unknown"
    pos = db.get_topic_position(topic)

    await update.message.reply_text(
        f"Starting study session...\n"
        f"Goal: *{goal_name}*  |  Topic {pos['position']}/{pos['total']}",
        parse_mode=ParseMode.MARKDOWN,
    )

    await run_study_session(update, ctx, topic)


# ---------------------------------------------------------------------------
# Proactive daily session job
# ---------------------------------------------------------------------------

async def daily_session_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job: send proactive study prompt to user."""
    settings = db.get_settings()
    telegram_user_id = settings.get("telegram_user_id")
    if not telegram_user_id:
        logger.warning("No telegram_user_id in settings — skipping daily session job.")
        return

    topic = db.get_next_pending_topic()
    if not topic:
        await ctx.bot.send_message(
            telegram_user_id,
            "🎉 You've completed all topics! Add more with /addtopic.",
        )
        return

    goal = db.get_goal(topic["goal_id"])
    goal_name = goal["name"] if goal else "Unknown"
    on_track = get_on_track_status(goal) if goal else "On track ✅"
    pos = db.get_topic_position(topic)

    msg = (
        f"Good morning! 🌅 Time to level up.\n\n"
        f"Today: *{topic['title']}* "
        f"(Topic {pos['position']} of {pos['total']} — {goal_name} goal)\n"
        f"Goal status: {on_track}\n\n"
        f"Reply *yes* to start now, or *later* to skip today."
    )

    await ctx.bot.send_message(
        telegram_user_id,
        msg,
        parse_mode=ParseMode.MARKDOWN,
    )

    # Store pending session
    pending_sessions[telegram_user_id] = topic["id"]

    # Schedule a 2-hour reminder job if user replies "later"
    # (handled in handle_yes_later)


async def reminder_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """2-hour follow-up reminder if user said 'later'."""
    user_id = ctx.job.data["user_id"]
    topic_id = ctx.job.data["topic_id"]

    # Only remind if still pending
    if pending_sessions.get(user_id) != topic_id:
        return

    topic = db.get_topic(topic_id)
    if not topic:
        return

    await ctx.bot.send_message(
        user_id,
        f"⏰ Reminder: Ready to study *{topic['title']}* now?\n\nReply *yes* to start.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# yes / later handler
# ---------------------------------------------------------------------------

async def handle_yes_later(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()

    topic_id = pending_sessions.get(user_id)
    if not topic_id:
        # Not a pending session reply — pass through
        # Check if quiz is active
        if user_id in quiz_state:
            await handle_quiz_answer(update, ctx)
        return

    if text == "yes":
        pending_sessions.pop(user_id, None)
        topic = db.get_topic(topic_id)
        if not topic:
            await update.message.reply_text("Topic not found. Use /study to start manually.")
            return
        await run_study_session(update, ctx, topic)

    elif text == "later":
        pending_sessions.pop(user_id, None)
        await update.message.reply_text(
            "No problem! I'll remind you in 2 hours. 😴"
        )
        # Schedule 2-hour reminder
        ctx.job_queue.run_once(
            reminder_job,
            when=7200,  # 2 hours in seconds
            data={"user_id": user_id, "topic_id": topic_id},
            name=f"reminder_{user_id}",
        )

    else:
        # Not yes/later — could be quiz answer
        if user_id in quiz_state:
            await handle_quiz_answer(update, ctx)


# ---------------------------------------------------------------------------
# Scheduler helpers
# ---------------------------------------------------------------------------

def reschedule_daily_job(app: Application, hour: int, minute: int) -> None:
    """Remove existing daily job and schedule a new one at given IST time."""
    jq: JobQueue = app.job_queue

    # Remove existing
    existing = jq.get_jobs_by_name("daily_session")
    for job in existing:
        job.schedule_removal()

    # Schedule new daily job in IST
    target_time = dtime(hour=hour, minute=minute, tzinfo=IST)
    jq.run_daily(daily_session_job, time=target_time, name="daily_session")
    logger.info(f"Daily session rescheduled to {hour:02d}:{minute:02d} IST")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    # Store telegram_user_id from env if not in DB
    env_uid = os.environ.get("TELEGRAM_USER_ID")
    if env_uid:
        try:
            db.set_telegram_user_id(int(env_uid))
        except Exception:
            pass

    app = Application.builder().token(token).build()

    # /goal conversation
    goal_conv = ConversationHandler(
        entry_points=[CommandHandler("goal", cmd_goal)],
        states={
            GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_name)],
            GOAL_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_desc)],
            GOAL_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_deadline)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    # /addtopic conversation
    addtopic_conv = ConversationHandler(
        entry_points=[CommandHandler("addtopic", cmd_addtopic)],
        states={
            AT_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_goal_select)],
            AT_PARENT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_parent_select)],
            AT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_title)],
            AT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_desc)],
            AT_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_notes)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            MessageHandler(filters.Regex(r"^Cancel$"), cmd_cancel),
        ],
    )

    # /settime conversation
    settime_conv = ConversationHandler(
        entry_points=[CommandHandler("settime", cmd_settime)],
        states={
            ST_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_get_time)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("study", cmd_study))
    app.add_handler(goal_conv)
    app.add_handler(addtopic_conv)
    app.add_handler(settime_conv)
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # Global text handler: yes/later → pending sessions, or quiz answers
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_yes_later)
    )

    # Schedule daily job on startup
    settings = db.get_settings()
    time_str = settings.get("daily_session_time", "09:00")
    try:
        h, m = map(int, time_str.split(":"))
    except Exception:
        h, m = 9, 0

    async def on_startup(application: Application) -> None:
        reschedule_daily_job(application, h, m)
        logger.info("Learnix bot started.")

    app.post_init = on_startup

    logger.info("Starting Learnix bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
