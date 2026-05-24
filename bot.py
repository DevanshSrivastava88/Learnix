import os
import logging
from datetime import datetime, time
from functools import wraps

import pytz
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from services import ClaudeService, GitHubService

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
ALLOWED_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))

github = GitHubService()
claude = ClaudeService()

# ConversationHandler states
QUIZ, GOAL_TOPIC, GOAL_DATE = range(3)


def only_me(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
            return ConversationHandler.END
        return await func(update, context)
    return wrapper


def format_status(status: dict) -> str:
    lines = ["*📚 Learnix Dashboard*\n"]

    goals = status.get("goals", [])
    if goals:
        today = datetime.now(IST).date()
        for goal in goals:
            target = datetime.strptime(goal["target_date"], "%Y-%m-%d").date()
            days_left = (target - today).days
            topic = next((t for t in status["topics"] if t["folder"] == goal["topic"]), None)
            if not topic:
                continue
            done = sum(1 for m in topic["modules"] if m["status"] == "passed")
            remaining = topic["total_modules"] - done
            needed = round(remaining / max(days_left, 1), 1)
            mpd = goal.get("modules_per_day", 0)
            on_track = needed <= mpd
            icon = "✅" if on_track else "⚠️"
            lines.append(f"{icon} *Goal: {topic['name']}* — due {goal['target_date']} ({days_left}d left)")
            lines.append(f"   {done}/{topic['total_modules']} done · need {needed}/day")
            if not on_track:
                lines.append(f"   ⚠️ Behind! Step it up.")
            lines.append("")

    for topic in status.get("topics", []):
        done = sum(1 for m in topic["modules"] if m["status"] == "passed")
        lines.append(f"📖 *{topic['name']}* — {done}/{topic['total_modules']}")
        for m in topic["modules"]:
            s = m["status"]
            if s == "passed":
                lines.append(f"   ✅ {m['name']} ({m.get('score', '?')})")
            elif s in ("pending", "needs_revision"):
                lines.append(f"   ⏳ {m['name']} ({s})")
            elif s == "not_started":
                lines.append(f"   🔲 {m['name']}")
        lines.append("")

    lines.append("Commands: /study · /goal · /progress")
    return "\n".join(lines)


@only_me
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = github.get_status()
    await update.message.reply_text(format_status(status), parse_mode="Markdown")


@only_me
async def cmd_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = github.get_status()
    await update.message.reply_text(format_status(status), parse_mode="Markdown")


# ── Study flow ──────────────────────────────────────────────────────────────

@only_me
async def cmd_study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = github.get_status()

    next_module = next_topic = None
    for topic in status["topics"]:
        for module in topic["modules"]:
            if module["status"] in ("not_started", "needs_revision", "pending"):
                next_module = module
                next_topic = topic
                break
        if next_module:
            break

    if not next_module:
        await update.message.reply_text("🎉 All modules complete! Set a new topic with /goal")
        return ConversationHandler.END

    context.user_data["topic"] = next_topic
    context.user_data["module"] = next_module

    await update.message.reply_text(
        f"📖 *{next_module['name']}*\nLoading...",
        parse_mode="Markdown",
    )

    try:
        content = github.get_module_content(next_topic["folder"], next_module["file"])
    except Exception:
        await update.message.reply_text("❌ Couldn't load module file. Check GitHub repo.")
        return ConversationHandler.END

    teaching = claude.teach_module(next_module["name"], content)
    await update.message.reply_text(teaching, parse_mode="Markdown")

    questions = claude.generate_quiz(next_module["name"], content)
    context.user_data["questions"] = questions
    context.user_data["q_idx"] = 0
    context.user_data["answers"] = []

    await update.message.reply_text(
        f"*Q1/5:* {questions[0]['question']}", parse_mode="Markdown"
    )
    return QUIZ


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return ConversationHandler.END

    answer = update.message.text
    questions = context.user_data["questions"]
    idx = context.user_data["q_idx"]
    q = questions[idx]

    is_correct, explanation = claude.score_answer(q["question"], q["answer"], answer)
    context.user_data["answers"].append(is_correct)

    emoji = "✅" if is_correct else "❌"
    await update.message.reply_text(f"{emoji} {explanation}")

    idx += 1
    context.user_data["q_idx"] = idx

    if idx < 5:
        await update.message.reply_text(
            f"*Q{idx + 1}/5:* {questions[idx]['question']}", parse_mode="Markdown"
        )
        return QUIZ

    return await finish_quiz(update, context)


async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answers = context.user_data["answers"]
    score = sum(answers)
    module = context.user_data["module"]
    topic = context.user_data["topic"]

    passed = score >= 3
    status_val = "passed" if passed else "needs_revision"
    emoji = "🎉" if passed else "📝"
    msg = (
        f"{emoji} *Quiz done! Score: {score}/5*\n\n"
        + ("Great work! Module marked as passed." if passed else "Review needed. Do /study again to re-attempt.")
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

    github.update_module_status(topic["folder"], module["id"], status_val, f"{score}/5")
    github.update_module_result(topic["folder"], module["file"], score, status_val)

    return ConversationHandler.END


# ── Goal flow ────────────────────────────────────────────────────────────────

@only_me
async def cmd_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = github.get_status()
    topics = ", ".join(t["folder"] for t in status["topics"])
    await update.message.reply_text(
        f"🎯 *Set a Goal*\n\nWhich topic? ({topics})", parse_mode="Markdown"
    )
    return GOAL_TOPIC


async def goal_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return ConversationHandler.END
    context.user_data["goal_topic"] = update.message.text.strip().lower().replace(" ", "_")
    await update.message.reply_text("📅 Deadline? (YYYY-MM-DD, e.g. 2026-06-30)")
    return GOAL_DATE


async def goal_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return ConversationHandler.END

    date_str = update.message.text.strip()
    folder = context.user_data["goal_topic"]

    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use YYYY-MM-DD")
        return GOAL_DATE

    status = github.get_status()
    topic = next((t for t in status["topics"] if t["folder"] == folder), None)
    if not topic:
        await update.message.reply_text(f"❌ Topic '{folder}' not found.")
        return ConversationHandler.END

    done = sum(1 for m in topic["modules"] if m["status"] == "passed")
    remaining = topic["total_modules"] - done
    days_left = (target - datetime.now(IST).date()).days
    mpd = round(remaining / max(days_left, 1), 2)

    status["goals"] = [g for g in status.get("goals", []) if g["topic"] != folder]
    status["goals"].append({
        "topic": folder,
        "target_date": date_str,
        "modules_per_day": mpd,
        "set_on": datetime.now(IST).strftime("%Y-%m-%d"),
    })
    github.update_status(status)

    await update.message.reply_text(
        f"✅ *Goal set!*\n\n"
        f"Topic: {topic['name']}\n"
        f"Deadline: {date_str} ({days_left} days)\n"
        f"Remaining: {remaining} modules\n"
        f"Target: *{mpd} modules/day*",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── Daily reminder ───────────────────────────────────────────────────────────

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    if not ALLOWED_USER_ID:
        return
    try:
        status = github.get_status()
        msg = claude.daily_summary(status)
        await context.bot.send_message(chat_id=ALLOWED_USER_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        log.error(f"Daily reminder failed: {e}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    study_conv = ConversationHandler(
        entry_points=[CommandHandler("study", cmd_study)],
        states={QUIZ: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    goal_conv = ConversationHandler(
        entry_points=[CommandHandler("goal", cmd_goal)],
        states={
            GOAL_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_topic)],
            GOAL_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_date)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(study_conv)
    app.add_handler(goal_conv)

    # Daily reminder
    reminder_time_str = os.getenv("DAILY_REMINDER_TIME", "09:00")
    h, m = map(int, reminder_time_str.split(":"))
    app.job_queue.run_daily(
        daily_reminder,
        time=time(hour=h, minute=m, tzinfo=IST),
        days=(0, 1, 2, 3, 4, 5, 6),
    )

    log.info("Learnix bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
