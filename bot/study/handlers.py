"""Study command handlers: /goal, /goals, /addtopic, /study, /progress, /editgoal, /deletegoal, /pausegoal"""

import logging
from datetime import datetime
from typing import Optional

import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters
)

import study.svc as db
import claude_svc as claude
import settings_svc

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

def format_plan(goal_name: str, scheduled: list, difficulty: str = "medium") -> str:
    """Render a freshly-built dated study plan."""
    from datetime import date
    diff_label = {"easy": "Easy 🟢", "medium": "Medium 🟡", "hard": "Hard 🔴"}.get(difficulty, "Medium 🟡")
    lines = [f"📚 *Study plan: {goal_name}* ({diff_label})\n"]
    today = date.today()
    for i, t in enumerate(scheduled, 1):
        sd = t.get("scheduled_date")
        if sd:
            d = date.fromisoformat(str(sd)[:10])
            when = "today" if d == today else d.strftime("%a %d %b")
        else:
            when = "—"
        lines.append(f"  {i}. *{t['title']}* · {when}")
    lines.append(f"\n{len(scheduled)} topics mapped out. I'll send you today's topic at your study time — "
                 f"or say *study {goal_name}* to start now.")
    return "\n".join(lines)


async def finalize_goal_with_plan(update, ctx, uid, name, desc, difficulty, deadline):
    """Create a goal, auto-generate its topics, build the dated plan, and show it.
    Shared by the /goal conversation and the free-text create_goal flow."""
    import asyncio as _aio
    goal = db.create_goal(uid, name, desc, deadline, difficulty=difficulty)
    # Auto-generate topics (the professional flow — no separate 'break it down' step)
    try:
        titles = await _aio.to_thread(claude.breakdown_study_goal, name, difficulty)
    except Exception as e:
        logger.error(f"plan topic generation failed: {e}")
        titles = []
    if not titles:
        diff_label = {"easy": "Easy 🟢", "medium": "Medium 🟡", "hard": "Hard 🔴"}.get(difficulty, "Medium 🟡")
        await update.message.reply_text(
            f"Goal created! 🎯 *{name}* ({diff_label}).\n"
            f"Couldn't auto-generate topics just now — say 'break down {name}' to retry.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(),
        )
        return
    db.bulk_create_topics(goal["id"], titles)
    scheduled = db.generate_plan(goal["id"])
    await update.message.reply_text(
        format_plan(name, scheduled, difficulty),
        parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(),
    )


# Conversation states
GOAL_NAME, GOAL_DESC, GOAL_DEADLINE, GOAL_DIFFICULTY = range(4)
AT_GOAL_SELECT, AT_PARENT_SELECT, AT_TITLE, AT_DESC, AT_NOTES = range(5, 10)
EDIT_GOAL_SELECT, EDIT_GOAL_FIELD, EDIT_GOAL_VALUE = range(10, 13)
DELETE_GOAL_SELECT, DELETE_GOAL_CONFIRM = range(13, 15)


def _format_goal_status(goal: dict) -> str:
    counts = db.count_topics_for_goal(goal["id"])
    total = counts["total"]
    completed = counts["completed"]
    target = goal.get("target_date", "")
    if total == 0:
        progress = "No topics yet"
    else:
        pct = int(completed / total * 100)
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        progress = f"{bar} {completed}/{total} ({pct}%)"
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
    return f"*{goal['name']}*{deadline_str}\n{progress}"


# ---------------------------------------------------------------------------
# /goals
# ---------------------------------------------------------------------------

async def cmd_goals(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet. Use /goal to set one up!")
        return
    lines = ["*📚 Your study goals*\n"]
    for g in goals:
        lines.append(_format_goal_status(g))
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /topics — numbered topic status list
# ---------------------------------------------------------------------------

_STATUS_ICONS = {
    "completed":      "✅",
    "in_progress":    "🔄",
    "skipped":        "⏭",
    "not_started":    "⬜",
    "needs_revision": "🔁",
}


def _format_topics_list(goal: dict, topics: list[dict], current_topic_id: Optional[str] = None) -> str:
    """Return a numbered topic list with status icons."""
    counts = db.count_topics_for_goal(goal["id"])
    total = counts["total"]
    completed = counts["completed"]
    pct = int(completed / total * 100) if total else 0

    root_topics = sorted(
        [t for t in topics if not t.get("parent_id")],
        key=lambda x: x["order_index"],
    )
    lines = [f"📚 *{goal['name']}* — {pct}% complete"]

    if current_topic_id:
        current = next((t for t in root_topics if t["id"] == current_topic_id), None)
        if current:
            pos = root_topics.index(current) + 1
            lines.append(f"Currently on: Topic {pos}")

    lines.append("")
    for i, t in enumerate(root_topics, 1):
        icon = _STATUS_ICONS.get(t["status"], "⬜")
        marker = " ← you're here" if t["id"] == current_topic_id else ""
        score_hint = ""
        if t["status"] == "in_progress" and t.get("score"):
            score_hint = f" ({t['score']} questions done)"
        lines.append(f"{i}. {icon} {t['title']}{score_hint}{marker}")
    return "\n".join(lines)


async def cmd_topics(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet. Use /goal to set one up!")
        return
    progress = db.get_study_progress(uid)
    for goal in goals:
        topics = db.list_topics_for_goal(goal["id"])
        current_id = progress["current_topic_id"] if progress and progress["goal_id"] == goal["id"] else None
        text = _format_topics_list(goal, topics, current_topic_id=current_id)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_study_topic(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic_name: str) -> None:
    """Jump to a specific topic by name."""
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet. Use /goal to set one up!")
        return
    all_topics = []
    for goal in goals:
        for t in db.list_topics_for_goal(goal["id"]):
            all_topics.append(t)
    matched = db.fuzzy_match_topic(topic_name, all_topics)
    if not matched:
        await update.message.reply_text(
            f"Couldn't find a topic matching *{topic_name}*. Use /topics to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    pos = db.get_topic_position(matched)
    await update.message.reply_text(
        f"📖 Jumping to *{matched['title']}* (Topic {pos['position']}/{pos['total']})",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _run_study_session(update, ctx, matched)


async def handle_skip_topic_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic_name: str) -> None:
    """Ask confirmation before marking a topic as skipped."""
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet.")
        return
    all_topics = []
    for goal in goals:
        for t in db.list_topics_for_goal(goal["id"]):
            all_topics.append(t)
    matched = db.fuzzy_match_topic(topic_name, all_topics)
    if not matched:
        await update.message.reply_text(
            f"Couldn't find a topic matching *{topic_name}*. Use /topics to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    ctx.user_data["pending_skip_topic_id"] = matched["id"]
    ctx.user_data["pending_skip_topic_title"] = matched["title"]
    buttons = [["Yes, skip it"], ["No, keep it"]]
    await update.message.reply_text(
        f"Skip *{matched['title']}*? This will mark it as skipped and move to the next topic.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )


async def handle_skip_topic_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from handle_text. Returns True if consumed."""
    if "pending_skip_topic_id" not in ctx.user_data:
        return False
    choice = update.message.text.strip()
    topic_id = ctx.user_data.pop("pending_skip_topic_id")
    topic_title = ctx.user_data.pop("pending_skip_topic_title", "")
    if choice == "Yes, skip it":
        db.skip_topic(topic_id)
        await update.message.reply_text(
            f"⏭ Skipped *{topic_title}*. It won't appear in your study sessions.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("Kept it! 👍", reply_markup=ReplyKeyboardRemove())
    return True


# ---------------------------------------------------------------------------
# /goal — create goal
# ---------------------------------------------------------------------------

async def cmd_goal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Let's set up a study goal! 🎯\n\nWhat do you want to learn? Give it a name:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GOAL_NAME


async def goal_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["goal_name"] = update.message.text.strip()
    await update.message.reply_text("Nice! Give it a short description — or '-' to skip:")
    return GOAL_DESC


async def goal_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["goal_desc"] = "" if desc == "-" else desc
    buttons = [["Easy"], ["Medium"], ["Hard"]]
    await update.message.reply_text(
        "What difficulty? 🎯\n• Easy — broad overview, fewer topics\n• Medium — balanced\n• Hard — deep dive, comprehensive topic list",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return GOAL_DIFFICULTY


async def goal_get_difficulty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip().lower()
    if choice not in ("easy", "medium", "hard"):
        buttons = [["Easy"], ["Medium"], ["Hard"]]
        await update.message.reply_text(
            "Please pick Easy, Medium, or Hard:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return GOAL_DIFFICULTY
    ctx.user_data["goal_difficulty"] = choice
    await update.message.reply_text(
        "Target date? (YYYY-MM-DD, e.g. 2026-12-01) Or '-' to skip:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GOAL_DEADLINE


async def goal_get_deadline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    deadline = update.message.text.strip()
    if deadline != "-":
        try:
            datetime.fromisoformat(deadline)
        except ValueError:
            await update.message.reply_text("Hmm, that date doesn't look right. Use YYYY-MM-DD or '-' to skip:")
            return GOAL_DEADLINE
    else:
        deadline = None
    uid = update.effective_user.id
    name = ctx.user_data["goal_name"]
    desc = ctx.user_data.get("goal_desc", "")
    difficulty = ctx.user_data.get("goal_difficulty", "medium")
    await update.message.reply_text("Building your study plan... 📚")
    await finalize_goal_with_plan(update, ctx, uid, name, desc, difficulty, deadline)
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /addtopic
# ---------------------------------------------------------------------------

async def cmd_addtopic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("You don't have any goals yet. Create one with /goal first!")
        return ConversationHandler.END
    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals] + [["Cancel"]]
    await update.message.reply_text(
        "Which goal is this topic under?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return AT_GOAL_SELECT


async def at_goal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Hmm, can't find that goal. Try /addtopic again.")
        return ConversationHandler.END
    ctx.user_data["selected_goal"] = goal
    topics = db.list_topics_for_goal(goal["id"])
    root_topics = [t for t in topics if not t.get("parent_id")]
    if root_topics:
        buttons = [["None (root topic)"]] + [[t["title"]] for t in root_topics] + [["Cancel"]]
        ctx.user_data["root_topics"] = root_topics
        await update.message.reply_text(
            "Is this a subtopic of something? Pick a parent, or 'None' if it's top-level:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return AT_PARENT_SELECT
    ctx.user_data["parent_topic"] = None
    await update.message.reply_text("What's the topic called?", reply_markup=ReplyKeyboardRemove())
    return AT_TITLE


async def at_parent_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    if chosen == "None (root topic)":
        ctx.user_data["parent_topic"] = None
    else:
        root_topics = ctx.user_data.get("root_topics", [])
        ctx.user_data["parent_topic"] = next((t for t in root_topics if t["title"] == chosen), None)
    await update.message.reply_text("What's the topic called?", reply_markup=ReplyKeyboardRemove())
    return AT_TITLE


async def at_get_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["topic_title"] = update.message.text.strip()
    await update.message.reply_text("Short description? (or '-' to skip):")
    return AT_DESC


async def at_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["topic_desc"] = "" if desc == "-" else desc
    await update.message.reply_text(
        "Any notes for this topic? (or '-' to skip)\n_Tip: Claude uses these when teaching you._",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AT_NOTES


async def at_get_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    notes = update.message.text.strip()
    ctx.user_data["topic_notes"] = "" if notes == "-" else notes
    goal = ctx.user_data["selected_goal"]
    parent = ctx.user_data.get("parent_topic")
    title = ctx.user_data["topic_title"]
    existing = db.list_topics_for_goal(goal["id"])
    siblings = [t for t in existing if t.get("parent_id") == (parent["id"] if parent else None)]
    db.create_topic(
        goal_id=goal["id"],
        title=title,
        description=ctx.user_data.get("topic_desc", ""),
        notes=ctx.user_data.get("topic_notes", ""),
        parent_id=parent["id"] if parent else None,
        order_index=len(siblings),
    )
    parent_str = f" (under *{parent['title']}*)" if parent else ""
    await update.message.reply_text(
        f"Added! 📌 *{title}*{parent_str} is in *{goal['name']}*.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /study — manual trigger
# ---------------------------------------------------------------------------

async def cmd_study(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text(
            "No study goals yet! Use /goal to set one up first."
        )
        return
    topic = db.get_next_pending_topic(uid)
    if not topic:
        await update.message.reply_text("🎉 You've done all your topics! Add more with /addtopic.")
        return
    goal = db.get_goal(topic["goal_id"])
    pos = db.get_topic_position(topic)
    counts = db.count_topics_for_goal(topic["goal_id"])
    total_root = pos["total"]
    completed_root = counts["completed"]
    pct = int(completed_root / total_root * 100) if total_root else 0
    goal_name = goal["name"] if goal else "?"
    await update.message.reply_text(
        f"📖 *Continuing {goal_name}*\n"
        f"Topic {pos['position']}/{pos['total']}: *{topic['title']}*\n"
        f"Progress: {pct}% overall",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _run_study_session(update, ctx, topic)


async def _run_study_session(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic: dict) -> None:
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    await ctx.bot.send_message(chat_id, f"📖 *{topic['title']}*\n\nTeaching...", parse_mode=ParseMode.MARKDOWN)
    try:
        lesson = claude.teach_topic(topic["title"], topic.get("notes", "") or "")
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"Couldn't load the lesson right now: {e}")
        return
    await ctx.bot.send_message(chat_id, lesson)
    await ctx.bot.send_message(chat_id, "Alright, quiz time! 🧠 Let's see what stuck.")
    try:
        questions = claude.generate_quiz(topic["title"], topic.get("notes", "") or "")
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"Couldn't generate the quiz: {e}")
        return
    ctx.bot_data.setdefault("quiz_state", {})[uid] = {
        "topic_id": topic["id"], "topic": topic,
        "questions": questions, "q_index": 0, "score": 0, "chat_id": chat_id,
    }
    await _ask_quiz_question(ctx, uid)


async def _ask_quiz_question(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    state = ctx.bot_data.get("quiz_state", {}).get(user_id)
    if not state:
        return
    idx = state["q_index"]
    questions = state["questions"]
    if idx >= len(questions):
        await _finish_quiz(ctx, user_id)
        return
    q = questions[idx]
    await ctx.bot.send_message(
        state["chat_id"],
        f"*Q{idx+1}/{len(questions)}:* {q['question']}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _finish_quiz(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    state = ctx.bot_data.get("quiz_state", {}).pop(user_id, None)
    if not state:
        return
    score = state["score"]
    total = len(state["questions"])
    topic_id = state["topic_id"]
    chat_id = state["chat_id"]
    passed = score >= 3
    new_status = "completed" if passed else "needs_revision"
    db.update_topic_status(topic_id, new_status, f"{score}/{total}")
    db.insert_quiz_attempt(topic_id, score)
    import analytics_svc
    analytics_svc.log_activity(user_id, "study", note=state["topic"]["title"])
    if passed:
        db.bubble_up_completion(topic_id)
    from datetime import date
    new_streak = settings_svc.update_streak(user_id, date.today())
    emoji = "🎉" if passed else "📚"
    label = "Passed!" if passed else "Needs revision"
    msg = (
        f"{emoji} *Quiz Complete!*\n\n"
        f"Score: *{score}/{total}*\nResult: {label}\n"
        f"🔥 Streak: {new_streak} day(s)\n\n"
    )
    msg += "Topic marked complete ✅" if passed else "You'll revisit this later 💪"
    await ctx.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)


async def handle_quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    state = ctx.bot_data.get("quiz_state", {}).get(uid)
    if not state:
        return
    user_answer = update.message.text.strip()

    # /cancel or natural-language cancel words exit the quiz cleanly
    _cancel_words = {"cancel", "stop", "quit", "exit", "nevermind", "never mind", "forget it"}
    if user_answer.startswith("/") or user_answer.lower() in _cancel_words:
        ctx.bot_data.get("quiz_state", {}).pop(uid, None)
        await update.message.reply_text(
            "Quiz cancelled. Come back whenever you're ready!",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Bug 2: "skip <topic>" or "study <topic>" escape mid-quiz without scoring
    lower_answer = user_answer.lower()
    if lower_answer.startswith("skip "):
        ctx.bot_data.get("quiz_state", {}).pop(uid, None)
        topic_name = user_answer[5:].strip()
        await handle_skip_topic_request(update, ctx, topic_name)
        return
    if lower_answer.startswith("study "):
        ctx.bot_data.get("quiz_state", {}).pop(uid, None)
        topic_name = user_answer[6:].strip()
        await handle_study_topic(update, ctx, topic_name)
        return

    idx = state["q_index"]
    q = state["questions"][idx]
    try:
        result = claude.score_answer(q["question"], q["expected_answer"], user_answer)
        correct = result.get("correct", False)
        explanation = result.get("explanation", "")
    except Exception as e:
        await update.message.reply_text(f"Hmm, scoring glitch — {e}")
        return
    if correct:
        state["score"] += 1
    await update.message.reply_text(
        f"{'✅' if correct else '❌'} {explanation}",
        parse_mode=ParseMode.MARKDOWN,
    )
    state["q_index"] += 1
    await _ask_quiz_question(ctx, uid)


# ---------------------------------------------------------------------------
# /progress
# ---------------------------------------------------------------------------

async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No goals yet! Use /goal to create one.")
        return
    lines = ["*📊 Your progress*\n"]
    for goal in goals:
        # Planned goals get the guided day-X/N on-track header
        plan = db.get_plan_status(goal["id"])
        if plan:
            track = "on track ✅" if plan["on_track"] else "behind ⏳"
            lines.append(f"🎯 *{plan['goal_name']}* — Day {plan['day']}/{plan['total_days']} ({track})")
            lines.append(f"   {plan['completed']}/{plan['total']} topics done")
            if plan["today_topic"]:
                lines.append(f"   👉 Up next: *{plan['today_topic']['title']}* — say *study {goal['name']}*")
            if plan["behind_topics"]:
                names = ", ".join(t["title"] for t in plan["behind_topics"][:3])
                lines.append(f"   ⏳ Catch up: {names}")
            weak = db.get_weak_topics(goal["id"])
            if weak:
                lines.append(f"   🔁 Review (shaky): {', '.join(t['title'] for t in weak[:3])}")
            lines.append("")
            continue
        # Unplanned goals — original topic-tree view
        lines.append(_format_goal_status(goal))
        topics = db.list_topics_for_goal(goal["id"])
        if topics:
            lines.append("Topics:")
            for t in topics:
                prefix = "  └ " if t.get("parent_id") else "  • "
                icon = {"completed": "✅", "needs_revision": "🔁", "not_started": "⬜"}.get(t["status"], "⬜")
                score_str = f" [{t['score']}]" if t.get("score") else ""
                lines.append(f"{prefix}{icon} {t['title']}{score_str}")
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /editgoal
# ---------------------------------------------------------------------------

async def cmd_editgoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("Nothing to edit — you don't have any goals yet.")
        return ConversationHandler.END
    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals] + [["Cancel"]]
    await update.message.reply_text(
        "Which goal do you want to edit?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return EDIT_GOAL_SELECT


async def editgoal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Hmm, couldn't find that goal. Try /editgoal again.")
        return ConversationHandler.END
    ctx.user_data["editing_goal"] = goal
    buttons = [["Name"], ["Description"], ["Target date"], ["Cancel"]]
    await update.message.reply_text(
        f"Editing *{goal['name']}* — what do you want to change?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return EDIT_GOAL_FIELD


async def editgoal_field(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    field = update.message.text.strip()
    if field == "Cancel":
        await update.message.reply_text("No changes made. 👍", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    ctx.user_data["editing_field"] = field
    prompts = {
        "Name": "What's the new name?",
        "Description": "What's the new description?",
        "Target date": "What's the new date? (YYYY-MM-DD):",
    }
    await update.message.reply_text(prompts.get(field, "What's the new value?"), reply_markup=ReplyKeyboardRemove())
    return EDIT_GOAL_VALUE


async def editgoal_value(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    goal = ctx.user_data["editing_goal"]
    field = ctx.user_data["editing_field"]
    field_map = {"Name": "name", "Description": "description", "Target date": "target_date"}
    db_field = field_map.get(field)
    if db_field == "target_date":
        try:
            datetime.fromisoformat(value)
        except ValueError:
            await update.message.reply_text("That date doesn't look right — use YYYY-MM-DD:")
            return EDIT_GOAL_VALUE
    db.update_goal(goal["id"], **{db_field: value})
    await update.message.reply_text(f"Updated! ✅ {field} is set.", reply_markup=ReplyKeyboardRemove())
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /deletegoal
# ---------------------------------------------------------------------------

async def cmd_deletegoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No goals to delete — you're all clear!")
        return ConversationHandler.END
    ctx.user_data["goals_list"] = goals
    buttons = [[g["name"]] for g in goals] + [["Cancel"]]
    await update.message.reply_text(
        "Which goal do you want to delete? This removes all its topics too.",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DELETE_GOAL_SELECT


async def deletegoal_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()
    goals = ctx.user_data.get("goals_list", [])
    goal = next((g for g in goals if g["name"] == chosen), None)
    if not goal:
        await update.message.reply_text("Hmm, couldn't find that goal.")
        return ConversationHandler.END
    ctx.user_data["deleting_goal"] = goal
    buttons = [["Yes, delete it"], ["Cancel"]]
    await update.message.reply_text(
        f"⚠️ Delete *{goal['name']}* and all its topics? Can't undo this.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return DELETE_GOAL_CONFIRM


async def deletegoal_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    if choice == "Yes, delete it":
        goal = ctx.user_data["deleting_goal"]
        db.delete_goal(goal["id"])
        await update.message.reply_text(
            f"Gone! 🗑️ *{goal['name']}* deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("Kept it! 👍", reply_markup=ReplyKeyboardRemove())
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /pausegoal — toggle paused/in_progress
# ---------------------------------------------------------------------------

async def cmd_pausegoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    paused = db.list_goals(uid, status="paused")
    all_goals = goals + paused
    if not all_goals:
        await update.message.reply_text("No goals yet! Use /goal to create one.")
        return
    lines = ["<b>Tap a goal to pause or resume it:</b>\n"]
    for g in all_goals:
        status_icon = "▶️" if g["status"] == "in_progress" else "⏸️"
        lines.append(f"{status_icon} /togglegoal_{g['id'][:8]} — {g['name']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_togglegoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    short_id = text.replace("/togglegoal_", "")
    uid = update.effective_user.id
    goals = db.list_goals(uid) + db.list_goals(uid, status="paused")
    goal = next((g for g in goals if g["id"].startswith(short_id)), None)
    if not goal:
        await update.message.reply_text("Hmm, couldn't find that goal.")
        return
    new_status = "paused" if goal["status"] == "in_progress" else "in_progress"
    db.update_goal_status(goal["id"], new_status)
    icon = "⏸️ Paused" if new_status == "paused" else "▶️ Resumed"
    await update.message.reply_text(f"{icon}: *{goal['name']}*", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Handler list to export
# ---------------------------------------------------------------------------

def get_handlers():
    cancel_handler = MessageHandler(filters.Regex(r"^Cancel$"), _cancel)

    goal_conv = ConversationHandler(
        entry_points=[CommandHandler("goal", cmd_goal)],
        states={
            GOAL_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_name)],
            GOAL_DESC:       [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_desc)],
            GOAL_DIFFICULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_difficulty)],
            GOAL_DEADLINE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_deadline)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    addtopic_conv = ConversationHandler(
        entry_points=[CommandHandler("addtopic", cmd_addtopic)],
        states={
            AT_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_goal_select)],
            AT_PARENT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_parent_select)],
            AT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_title)],
            AT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_desc)],
            AT_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, at_get_notes)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    editgoal_conv = ConversationHandler(
        entry_points=[CommandHandler("editgoal", cmd_editgoal)],
        states={
            EDIT_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, editgoal_select)],
            EDIT_GOAL_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, editgoal_field)],
            EDIT_GOAL_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, editgoal_value)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    deletegoal_conv = ConversationHandler(
        entry_points=[CommandHandler("deletegoal", cmd_deletegoal)],
        states={
            DELETE_GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletegoal_select)],
            DELETE_GOAL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletegoal_confirm)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )

    return [
        goal_conv, addtopic_conv, editgoal_conv, deletegoal_conv,
        CommandHandler("goals", cmd_goals),
        CommandHandler("topics", cmd_topics),
        CommandHandler("study", cmd_study),
        CommandHandler("progress", cmd_progress),
        CommandHandler("pausegoal", cmd_pausegoal),
        MessageHandler(filters.Regex(r"^/togglegoal_"), handle_togglegoal),
    ]


async def _cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled! 👋", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
