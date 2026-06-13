"""
scheduler.py — Polling-based scheduler for all users.

4 jobs, all polling (no per-user APScheduler jobs):
1. study_poller    — every 60s, checks daily_session_time match
2. morning_poller  — every 60s, checks morning_brief_time match
3. eod_poller      — every 60s, checks eod_time match
4. reminder_poller — every 300s, checks tasks.next_reminder_at <= now
"""

import logging
import os
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

def get_missed_yesterday(user_id: int) -> list[str]:
    """Return titles of habit/reminder tasks that were due yesterday but not marked done."""
    from supabase_svc import get_client
    yesterday = date.today() - timedelta(days=1)
    yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0,
                               tzinfo=IST).astimezone(__import__("pytz").utc)
    yesterday_end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59,
                             tzinfo=IST).astimezone(__import__("pytz").utc)

    sb = get_client()

    # Tasks that were reminded yesterday (last_reminder_at between yesterday 00:00–23:59 IST)
    # We approximate using next_reminder_at: tasks whose next_reminder_at was set within
    # yesterday (i.e. was due yesterday). Since we advance by 1 day on done and 8h on remind,
    # a simpler heuristic: query activity_log for done habits yesterday, then compare to all habits.
    res_done = (
        sb.table("activity_log")
        .select("note")
        .eq("user_id", user_id)
        .eq("event_type", "habit")
        .eq("event_date", yesterday.isoformat())
        .execute()
    )
    done_notes = {row["note"].lower() for row in (res_done.data or []) if row.get("note")}

    # Active habit/reminder tasks
    res_tasks = (
        sb.table("tasks")
        .select("title, task_type, next_reminder_at")
        .eq("user_id", user_id)
        .eq("status", "active")
        .in_("task_type", ["habit", "reminder"])
        .execute()
    )
    tasks = res_tasks.data or []

    missed = []
    for t in tasks:
        title = t.get("title", "")
        # Check if next_reminder_at is today or later (meaning it was rescheduled, i.e. reminded)
        # We consider a task "missed" if its title didn't appear in yesterday's done activity log
        if title.lower() not in done_notes:
            next_at = t.get("next_reminder_at")
            if next_at:
                try:
                    next_dt = datetime.fromisoformat(next_at)
                    if next_dt.tzinfo is None:
                        next_dt = next_dt.replace(tzinfo=__import__("pytz").utc)
                    next_ist = next_dt.astimezone(IST)
                    # If task is due today or after, it was active yesterday and not done
                    if next_ist.date() >= date.today():
                        missed.append(title)
                except Exception:
                    pass
    return missed


def format_morning_brief(user_id: int) -> str:
    settings = settings_svc.get_settings(user_id)
    streak = settings.get("streak", 0) or 0
    goals = study_svc.list_goals(user_id)
    all_tasks = tasks_svc.list_tasks(user_id)
    habits = [t for t in all_tasks if t["task_type"] == "habit"]
    milestones = [t for t in all_tasks if t["task_type"] == "milestone"]
    next_topic = study_svc.get_next_pending_topic(user_id)

    lines = ["🌅 *Morning!* Here's what's on today:\n"]

    lines.append("📚 *Study*")
    if not goals:
        lines.append("No study goals yet — /goal to set one up.")
    else:
        planned_topic = None
        for g in goals:
            plan = study_svc.get_plan_status(g["id"])
            if plan:
                track = "on track ✅" if plan["on_track"] else "behind ⏳"
                lines.append(f"• *{g['name']}* — Day {plan['day']}/{plan['total_days']} "
                             f"({plan['completed']}/{plan['total']}, {track})")
                if plan["today_topic"] and planned_topic is None:
                    planned_topic = (plan["today_topic"]["title"], g["name"])
            else:
                counts = study_svc.count_topics_for_goal(g["id"])
                total = counts["total"]
                completed = counts["completed"]
                pct = int(completed / total * 100) if total else 0
                lines.append(f"• {g['name']} — {completed}/{total} topics ({pct}%)")
        if planned_topic:
            lines.append(f"\n▶️ Today's topic: *{planned_topic[0]}* ({planned_topic[1]})")
            lines.append(f"Say *study {planned_topic[1]}* when you're ready.")
        elif next_topic:
            goal = study_svc.get_goal(next_topic["goal_id"])
            goal_name = goal["name"] if goal else ""
            lines.append(f"\n▶️ Up next: *{next_topic['title']}* ({goal_name})")
            lines.append("Tap /study when you're ready.")

    lines.append("\n✅ *Habits*")
    if not habits:
        lines.append("No habits yet — /newtask to add one.")
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

    lines.append("\n📋 *Milestones*")
    if not milestones:
        lines.append("No milestones — /newtask to add one.")
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

    # Missed yesterday section
    try:
        missed = get_missed_yesterday(user_id)
        if missed:
            lines.append("\n⚠️ *Missed yesterday:*")
            for title in missed:
                lines.append(f"• {title}")
    except Exception:
        pass  # Don't break the morning brief if this fails

    # Unscheduled tasks
    try:
        unscheduled = [t for t in all_tasks if t.get("task_type") == "task" and not t.get("next_reminder_at")]
        if unscheduled:
            lines.append("\n📌 *Unscheduled tasks:*")
            for t in unscheduled:
                lines.append(f"• {t['title']}")
            lines.append("_Unscheduled tasks are easy to forget — say \"set [task] to [time]\" to pin one._")
    except Exception:
        pass

    lines.append(f"\n🔥 Streak: {streak} day(s) — let's keep it going!")
    return "\n".join(lines)


def format_eod(user_id: int) -> str:
    settings = settings_svc.get_settings(user_id)
    streak = settings.get("streak", 0) or 0
    today = date.today()

    lines = ["🌙 *Day done — let's wrap up!*\n"]

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
        lines.append("📚 No study sessions today — no worries, tomorrow's a fresh start!")

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
                        lines.append(f"  ❌ {h['title']} (not done today)")
                except Exception:
                    lines.append(f"  • {h['title']}")

    lines.append(f"\n🔥 Streak: {streak} day(s)")
    lines.append("\nCatch you tomorrow! 👋")
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
        goals = study_svc.list_goals(uid, "in_progress")
        # Planned goal → guided daily nudge with day-X/N + today's scheduled topic
        plan = study_svc.get_plan_status(goals[0]["id"]) if goals else None
        if plan:
            weak = study_svc.get_weak_topics(goals[0]["id"])
            topic = weak[0] if weak else plan["today_topic"]
            if not topic:
                continue  # plan complete — no nag
            track = "on track ✅" if plan["on_track"] else "behind ⏳"
            review = " (review 🔁)" if (weak and topic in weak) else ""
            msg = (
                f"📖 Study time! — *{plan['goal_name']}* "
                f"Day {plan['day']}/{plan['total_days']} ({track})\n\n"
                f"Today: *{topic['title']}*{review}\n\n"
                f"Reply *yes* to start, or *later* to snooze."
            )
            await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
            ctx.bot_data.setdefault("pending_sessions", {})[uid] = topic["id"]
            continue
        topic = study_svc.get_next_pending_topic(uid)
        if not topic:
            await ctx.bot.send_message(uid, "🎉 You've done all your topics! Add more with /addtopic.")
            continue
        goal = study_svc.get_goal(topic["goal_id"])
        goal_name = goal["name"] if goal else "?"
        pos = study_svc.get_topic_position(topic)
        msg = (
            f"📖 Study time!\n\n"
            f"*{topic['title']}* — {goal_name} "
            f"(Topic {pos['position']}/{pos['total']})\n\n"
            f"Reply *yes* to jump in, or *later* to snooze."
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


def format_evening_digest(user_id: int) -> str:
    """7pm check-in: unscheduled tasks + reminder-less habits. Empty string if nothing."""
    all_tasks = tasks_svc.list_tasks(user_id)
    unscheduled = [
        t for t in all_tasks
        if not t.get("next_reminder_at") and " — Step " not in t.get("title", "")
        and t.get("task_type") in ("task", "habit")
    ]
    if not unscheduled:
        return ""
    lines = ["🌆 *Evening check-in* — these never got a time today:\n"]
    for t in unscheduled:
        mark = "🔁" if t.get("task_type") == "habit" else "•"
        lines.append(f"  {mark} {t['title']}")
    lines.append("\nGot a free moment? Knock one out and say *done [task]* 💪")
    return "\n".join(lines)


async def evening_digest_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 60s: at 19:00 IST send the unscheduled-work digest to all users."""
    now_ist = datetime.now(IST)
    if now_ist.strftime("%H:%M") != "19:00":
        return
    # Daily housekeeping piggybacks on this once-a-day tick
    try:
        import chat_history_svc
        chat_history_svc.cleanup_old(days=7)
    except Exception as e:
        logger.error(f"chat_history cleanup failed: {e}")
    users = settings_svc.get_all_users()
    for user in users:
        uid = user["user_id"]
        try:
            msg = format_evening_digest(uid)
            if msg:
                await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Evening digest failed for {uid}: {e}")


async def reminder_poller(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 300s: send habit/milestone reminders for all due tasks.

    Normal habits: exactly 2 reminders per day (8hr gap), then auto-skip.
    Important habits: remind every 1hr from first reminder until user's eod_time (IST).
                      After eod_time, stop for today. Next day resets to normal cadence.
    """
    from datetime import timezone as _tz, timedelta
    due = tasks_svc.get_due_tasks()
    railway_url = os.environ.get("RAILWAY_URL", "")

    for task in due:
        # Skip breakdown step tasks — users mark steps done manually
        if " — Step " in task.get("title", ""):
            continue
        uid = task["user_id"]
        title = task["title"]
        task_id = task["id"]
        task_type = task["task_type"]
        important = tasks_svc.is_important(task)
        try:
            if task_type == "task":
                # One-time task with a scheduled time — fire once, then complete
                await ctx.bot.send_message(
                    uid,
                    f"⏰ Hey! Don't forget: *{title}*",
                    parse_mode=ParseMode.MARKDOWN,
                )
                tasks_svc.update_task(task_id, status="completed")
                continue
            if task_type == "habit":
                now_ist = datetime.now(IST)

                if important:
                    # Get user's eod_time to know when to stop for today
                    eod_hhmm = settings_svc.get_settings(uid).get("eod_time", "21:00") or "21:00"
                    eod_h, eod_m = map(int, eod_hhmm.split(":"))
                    eod_today = now_ist.replace(hour=eod_h, minute=eod_m, second=0, microsecond=0)

                    if now_ist >= eod_today:
                        # Past EOD — skip for today, reset counter, reschedule to tomorrow
                        tasks_svc.reset_reminder_count(task_id, task)
                        next_utc = datetime.now(_tz.utc) + timedelta(days=task.get("recurrence_days", 1))
                        tasks_svc.reschedule_task(task_id, next_utc)
                        continue

                    # Still before EOD — send reminder and re-schedule in 1hr
                    msg = (
                        f"⏰ Time for ⚡ *{title}*!\n\n"
                        f"Reply 'done', 'skip', or 'delay ⏳'"
                    )
                    await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
                    ctx.bot_data.setdefault("last_reminded", {})[uid] = task_id
                    ctx.bot_data.setdefault("last_reminded_at", {})[uid] = datetime.now(_tz.utc).isoformat()

                    import twilio_svc
                    if twilio_svc.is_twilio_enabled(uid):
                        import asyncio
                        asyncio.get_running_loop().run_in_executor(
                            None, twilio_svc.make_reminder_call, uid, task_id, title, railway_url
                        )

                    next_utc = datetime.now(_tz.utc) + timedelta(hours=1)
                    tasks_svc.reschedule_task(task_id, next_utc)
                    tasks_svc.increment_reminder_count(task_id, task)

                else:
                    # Normal task: track reminder count in description
                    reminded_count = tasks_svc.get_reminder_count(task)

                    if reminded_count >= 2:
                        # Auto-skip after 2nd reminder with no response
                        import analytics_svc
                        tasks_svc.log_skip(uid, task_id, note="auto_skip_no_response")
                        tasks_svc.reset_reminder_count(task_id, task)
                        next_utc = datetime.now(_tz.utc) + timedelta(days=task.get("recurrence_days", 1))
                        tasks_svc.reschedule_task(task_id, next_utc)
                        analytics_svc.log_activity(uid, "habit", note=f"auto_skip:{title}")
                        await ctx.bot.send_message(
                            uid,
                            f"⏭ Auto-skipped *{title}* — no response after 2 reminders. Catch you tomorrow!",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        continue

                    # Send reminder and schedule next one 8hrs later
                    msg = (
                        f"⏰ Time for *{title}*!\n\n"
                        f"Reply 'done', 'skip', or 'delay ⏳'"
                    )
                    await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
                    ctx.bot_data.setdefault("last_reminded", {})[uid] = task_id
                    ctx.bot_data.setdefault("last_reminded_at", {})[uid] = datetime.now(_tz.utc).isoformat()

                    import twilio_svc
                    if twilio_svc.is_twilio_enabled(uid):
                        import asyncio
                        asyncio.get_running_loop().run_in_executor(
                            None, twilio_svc.make_reminder_call, uid, task_id, title, railway_url
                        )

                    next_utc = datetime.now(_tz.utc) + timedelta(hours=8)
                    tasks_svc.reschedule_task(task_id, next_utc)
                    tasks_svc.increment_reminder_count(task_id, task)

            else:
                counts = tasks_svc.count_milestones(task_id)
                total = counts["total"]
                done = counts["done"]
                target = task.get("target_date", "")
                msg = (
                    f"📋 *{title}*\n"
                    f"Progress: {done}/{total}"
                    + (f"\nDeadline: {target}" if target else "")
                    + f"\n\nUse /tasks to update."
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
    jq.run_repeating(evening_digest_poller, interval=60, first=25, name="evening_digest_poller")
    logger.info("All scheduler jobs registered.")
