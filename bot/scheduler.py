"""
scheduler.py — Polling-based scheduler for all users.

4 jobs, all polling (no per-user APScheduler jobs):
1. study_poller    — every 60s, checks daily_session_time match
2. morning_poller  — every 60s, checks morning_brief_time match
3. eod_poller      — every 60s, checks eod_time match
4. reminder_poller — every 300s, checks tasks.next_reminder_at <= now
"""

import logging
from datetime import datetime, date

import pytz
from telegram.ext import Application, ContextTypes
from telegram.constants import ParseMode

import settings_svc
import study.svc as study_svc
import tasks.svc as tasks_svc
import motivation_svc

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Formatters (pure functions — easy to test)
# ---------------------------------------------------------------------------

def format_morning_brief(user_id: int) -> str:
    settings = settings_svc.get_settings(user_id)
    streak = settings.get("streak", 0) or 0
    goals = study_svc.list_goals(user_id)
    all_tasks = tasks_svc.list_tasks(user_id)
    habits = [t for t in all_tasks if t["task_type"] == "habit"]
    milestones = [t for t in all_tasks if t["task_type"] == "milestone"]
    next_topic = study_svc.get_next_pending_topic(user_id)

    lines = ["🌅 *Good morning!* Here's your day:\n"]

    lines.append("📚 *STUDY*")
    if not goals:
        lines.append("No active study goals. Use /goal to create one.")
    else:
        for g in goals:
            counts = study_svc.count_topics_for_goal(g["id"])
            total = counts["total"]
            completed = counts["completed"]
            pct = int(completed / total * 100) if total else 0
            lines.append(f"• {g['name']} — {completed}/{total} topics ({pct}%)")
        if next_topic:
            goal = study_svc.get_goal(next_topic["goal_id"])
            goal_name = goal["name"] if goal else ""
            lines.append(f"\n▶️ Next up: *{next_topic['title']}* ({goal_name})")
            lines.append("Reply /study to start your session.")

    lines.append("\n✅ *HABITS*")
    if not habits:
        lines.append("No habits yet. Use /newtask to add one.")
    else:
        now = datetime.now(IST)
        for h in habits:
            next_at = h.get("next_reminder_at")
            if next_at:
                try:
                    next_dt = datetime.fromisoformat(next_at).astimezone(IST)
                    if next_dt.date() <= now.date():
                        lines.append(f"• ⏰ {h['title']} (due today)")
                    else:
                        lines.append(f"• {h['title']} (next: {next_dt.strftime('%b %d')})")
                except Exception:
                    lines.append(f"• {h['title']}")
            else:
                lines.append(f"• {h['title']}")

    lines.append("\n📋 *MILESTONES*")
    if not milestones:
        lines.append("No milestones. Use /newtask to add one.")
    else:
        for m in milestones:
            counts = tasks_svc.count_milestones(m["id"])
            total = counts["total"]
            done = counts["done"]
            target = m.get("target_date", "")
            deadline_str = ""
            if target:
                try:
                    target_date = date.fromisoformat(str(target))
                    days_left = (target_date - date.today()).days
                    if days_left < 0:
                        deadline_str = " ⚠️ Overdue"
                    elif days_left <= 3:
                        deadline_str = f" 🔥 {days_left}d left"
                    else:
                        deadline_str = f" ({days_left}d left)"
                except Exception:
                    pass
            lines.append(f"• {m['title']} — {done}/{total}{deadline_str}")

    lines.append(f"\n🔥 Streak: {streak} day(s)")
    return "\n".join(lines)


def format_eod(user_id: int) -> str:
    settings = settings_svc.get_settings(user_id)
    streak = settings.get("streak", 0) or 0
    today = date.today()

    lines = ["🌙 *Day wrap-up!*\n"]

    goals = study_svc.list_goals(user_id)
    studied_today = []
    for g in goals:
        topics = study_svc.list_topics_for_goal(g["id"])
        for t in topics:
            if t.get("completed_at"):
                try:
                    completed_dt = datetime.fromisoformat(t["completed_at"]).astimezone(IST)
                    if completed_dt.date() == today and t["status"] == "completed":
                        studied_today.append(t["title"])
                except Exception:
                    pass

    if studied_today:
        lines.append("📚 *Studied today:*")
        for title in studied_today:
            lines.append(f"  ✅ {title}")
    else:
        lines.append("📚 No study sessions today — catch up tomorrow!")

    all_tasks = tasks_svc.list_tasks(user_id)
    habits = [t for t in all_tasks if t["task_type"] == "habit"]
    if habits:
        lines.append("\n✅ *Habits:*")
        for h in habits:
            next_at = h.get("next_reminder_at")
            if next_at:
                try:
                    next_dt = datetime.fromisoformat(next_at).astimezone(IST)
                    if next_dt.date() > today:
                        lines.append(f"  ✅ {h['title']}")
                    else:
                        lines.append(f"  ❌ {h['title']} (not done)")
                except Exception:
                    lines.append(f"  • {h['title']}")

    lines.append(f"\n🔥 Streak: {streak} day(s) — keep it up!")
    lines.append("\nSee you tomorrow! 👋")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Polling jobs
# ---------------------------------------------------------------------------

async def study_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: send daily study prompt to users whose study time == now."""
    now_ist = datetime.now(IST)
    current_hhmm = now_ist.strftime("%H:%M")
    users = settings_svc.get_all_users()
    for user in users:
        if user.get("daily_session_time") != current_hhmm:
            continue
        uid = user["user_id"]
        topic = study_svc.get_next_pending_topic(uid)
        if not topic:
            await ctx.bot.send_message(uid, "🎉 All topics done! Add more with /addtopic.")
            continue
        goal = study_svc.get_goal(topic["goal_id"])
        goal_name = goal["name"] if goal else "?"
        pos = study_svc.get_topic_position(topic)
        msg = (
            f"📖 Time to study!\n\n"
            f"*{topic['title']}* — {goal_name} "
            f"(Topic {pos['position']}/{pos['total']})\n\n"
            f"Reply *yes* to start now, or *later* to skip."
        )
        await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        ctx.bot_data.setdefault("pending_sessions", {})[uid] = topic["id"]


async def morning_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: send morning brief to users whose morning_brief_time == now."""
    now_ist = datetime.now(IST)
    current_hhmm = now_ist.strftime("%H:%M")
    users = settings_svc.get_all_users()
    for user in users:
        if user.get("morning_brief_time") != current_hhmm:
            continue
        uid = user["user_id"]
        try:
            msg = format_morning_brief(uid)
            await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Morning brief failed for {uid}: {e}")


async def eod_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: send EOD check-in to users whose eod_time == now."""
    now_ist = datetime.now(IST)
    current_hhmm = now_ist.strftime("%H:%M")
    users = settings_svc.get_all_users()
    for user in users:
        if user.get("eod_time") != current_hhmm:
            continue
        uid = user["user_id"]
        try:
            msg = format_eod(uid)
            await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"EOD failed for {uid}: {e}")


async def reminder_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 300s: send habit/milestone reminders for all due tasks.
    Habits: max 2 reminders per day, auto-skip on 3rd attempt.
    """
    due = tasks_svc.get_due_tasks()
    today = datetime.now(IST).date().isoformat()

    for task in due:
        uid = task["user_id"]
        title = task["title"]
        task_id = task["id"]
        task_type = task["task_type"]
        try:
            if task_type == "habit":
                short = task_id[:8]
                count_key = f"reminded_{task_id}_{today}"
                reminded_today = ctx.bot_data.get(count_key, 0)

                if reminded_today >= 2:
                    # Auto-skip after 2 reminders with no response
                    import analytics_svc
                    tasks_svc.log_skip(uid, task_id, note="auto_skip_no_response")
                    from datetime import timedelta
                    next_at = datetime.now(IST).replace(tzinfo=None)
                    import pytz as _pytz
                    from datetime import timezone as _tz
                    next_utc = datetime.now(_tz.utc) + timedelta(days=task.get("recurrence_days", 1))
                    tasks_svc.reschedule_task(task_id, next_utc)
                    ctx.bot_data[count_key] = 0
                    analytics_svc.log_activity(uid, "habit", note=f"auto_skip:{title}")
                    await ctx.bot.send_message(
                        uid,
                        f"⏭ Auto-skipped *{title}* — no response after 2 reminders. See you tomorrow!",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    continue

                # Send reminder and advance next_reminder_at by 8 hours
                msg = (
                    f"⏰ Habit reminder: *{title}*\n\n"
                    f"✅ Done → /done_{short}\n"
                    f"⏭ Skip → /skip_{short}"
                )
                await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
                from datetime import timezone as _tz, timedelta
                next_utc = datetime.now(_tz.utc) + timedelta(hours=8)
                tasks_svc.reschedule_task(task_id, next_utc)
                ctx.bot_data[count_key] = reminded_today + 1
            else:
                counts = tasks_svc.count_milestones(task_id)
                total = counts["total"]
                done = counts["done"]
                target = task.get("target_date", "")
                msg = (
                    f"📋 Milestone reminder: *{title}*\n"
                    f"Progress: {done}/{total}\n"
                    f"Deadline: {target}\n\n"
                    f"Use /tasks to update progress."
                )
                await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Reminder failed for task {task_id}: {e}")


async def motivation_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 300s: check skip patterns and send motivational messages if triggered."""
    users = settings_svc.get_all_users()
    for user in users:
        uid = user["user_id"]
        try:
            await motivation_svc.check_and_send_for_user(ctx.bot, uid)
        except Exception as e:
            logger.error(f"Motivation poller failed for {uid}: {e}")


def register_jobs(app: Application) -> None:
    """Register all polling jobs on app startup."""
    jq = app.job_queue
    jq.run_repeating(study_poller, interval=60, first=10, name="study_poller")
    jq.run_repeating(morning_poller, interval=60, first=15, name="morning_poller")
    jq.run_repeating(eod_poller, interval=60, first=20, name="eod_poller")
    jq.run_repeating(reminder_poller, interval=300, first=30, name="reminder_poller")
    jq.run_repeating(motivation_poller, interval=300, first=60, name="motivation_poller")
    logger.info("All scheduler jobs registered.")
