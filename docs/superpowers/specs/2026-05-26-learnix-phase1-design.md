# Learnix Phase 1 — Full Design Spec
**Date:** 2026-05-26  
**Status:** Approved

---

## Overview

Learnix is a multi-user Telegram bot that serves as a personal AI operating system. It combines an AI-powered study system (teach + quiz via Gemini) with a general task management system (habits + milestones), unified by a daily morning brief and EOD check-in. Anyone can DM the bot and start using it (/start auto-registers them).

---

## Two Internal Systems, One Bot

### System 1: Study (Learnix Core)
- Users create **study goals** (e.g. "Become an AI Engineer")
- Each goal has a **topics tree** (hierarchical subtopics)
- Bot teaches each topic via Gemini 2.5 Flash, then runs a 5-question quiz
- Topics are marked complete/needs_revision based on quiz score
- Completion bubbles up to parent topics
- Daily proactive study session at user-configured time
- Streak tracking per user

### System 2: Tasks (LifeOS)
- **Habits** — recurring actions (e.g. "Make bed" every day, "Bath" every 2 days)
  - Have a `next_reminder_at` timestamp
  - When marked done → `next_reminder_at` auto-set to `now + recurrence_days`
- **Milestones** — goal with a checklist + deadline (e.g. "Launch side project" with 5 steps)
  - Have sub-items (milestones table)
  - Progress tracked as completed/total items
  - Deadline reminder fires 3 days before and 1 day before target_date

### Unified Layer
- **Morning Brief** (default 08:00 IST, configurable): Shows all active study goals progress, habits due today, milestone deadlines coming up, next study topic
- **EOD Check-in** (default 21:00 IST, configurable): Shows what was completed today — study sessions done, habits checked off, milestones ticked
- **Reminder Poller**: Single job runs every 5 minutes, checks `tasks.next_reminder_at <= now()` across all users, sends reminders

---

## Database Schema

### Existing tables (with changes)
```sql
-- goals: add user_id
alter table goals add column user_id bigint not null;
create index on goals(user_id);

-- topics: unchanged (scoped via goal → user)
-- quiz_attempts: unchanged (scoped via topic → goal → user)

-- settings: redesign from singleton to per-user
drop table settings;
create table settings (
  user_id            bigint primary key,
  daily_session_time text not null default '09:00',
  morning_brief_time text not null default '08:00',
  eod_time           text not null default '21:00',
  streak             int not null default 0,
  last_study_date    date
);
```

### New tables
```sql
create table tasks (
  id               uuid primary key default gen_random_uuid(),
  user_id          bigint not null,
  title            text not null,
  task_type        text not null,          -- 'habit' | 'milestone'
  status           text default 'active',  -- 'active' | 'paused' | 'completed'
  description      text,
  next_reminder_at timestamptz,            -- habits: auto-calculated; milestones: deadline reminders
  recurrence_days  int,                    -- habits only (1=daily, 2=every 2 days, etc.)
  target_date      date,                   -- milestones only
  created_at       timestamptz default now()
);
create index on tasks(user_id);
create index on tasks(next_reminder_at) where status = 'active';

create table milestones (
  id          uuid primary key default gen_random_uuid(),
  task_id     uuid not null references tasks(id) on delete cascade,
  title       text not null,
  done        boolean default false,
  order_index int default 0
);
```

---

## File Structure

```
bot/
  bot.py              # main router, registers all handlers, starts scheduler
  supabase_svc.py     # base Supabase client
  settings_svc.py     # per-user settings CRUD
  scheduler.py        # morning brief, EOD, reminder poller, study daily jobs
  study/
    handlers.py       # /goal, /addtopic, /study, /progress commands
    svc.py            # goals/topics/quiz DB ops (all scoped by user_id)
  tasks/
    handlers.py       # /newtask, /tasks, /done, /edit, /delete, /pause, /resume
    svc.py            # tasks/milestones DB ops
  claude_svc.py       # Gemini teach + quiz + score (unchanged)
```

---

## Bot Commands

### Always available
| Command | Description |
|---|---|
| `/start` | Register user + show dashboard |
| `/help` | List all commands |

### Study system
| Command | Description |
|---|---|
| `/goal` | Create a new study goal |
| `/goals` | List study goals with progress |
| `/addtopic` | Add topic/subtopic to a goal |
| `/study` | Start study session now |
| `/progress` | Full topic tree with statuses |
| `/editgoal` | Edit goal name/deadline |
| `/deletegoal` | Delete a study goal |
| `/pausegoal` | Pause daily study reminders for a goal |

### Tasks system
| Command | Description |
|---|---|
| `/newtask` | Create habit or milestone (conversational flow) |
| `/tasks` | List all active habits + milestones |
| `/done` | Mark a habit done (auto-schedules next reminder) |
| `/edittask` | Edit task title/recurrence/deadline |
| `/deletetask` | Delete a task |
| `/pause` | Pause a task's reminders |
| `/resume` | Resume a paused task |
| `/complete` | Mark a milestone as fully complete |

### Settings
| Command | Description |
|---|---|
| `/settime` | Set daily study session time |
| `/settings` | View/change morning brief time + EOD time |

---

## Scheduler Design (Multi-user)

Instead of per-user APScheduler jobs (complex, memory-heavy with many users), use **3 polling jobs** that run on fixed intervals and fan out to all users:

1. **Study poller** — runs every minute, checks `settings` for users whose `daily_session_time` matches current HH:MM IST
2. **Morning brief poller** — runs every minute, checks `settings` for users whose `morning_brief_time` matches current HH:MM IST  
3. **EOD poller** — runs every minute, checks `settings` for users whose `eod_time` matches current HH:MM IST
4. **Reminder poller** — runs every 5 minutes, queries `tasks` where `next_reminder_at <= now() AND status = 'active'`, sends reminder per user

This scales to thousands of users with no per-user jobs.

---

## Key Flows

### New user onboarding
1. User DMs bot `/start`
2. Bot creates `settings` row for their `telegram_user_id` with defaults
3. Bot shows dashboard + explains 3 things they can do (study goal / habit / milestone)

### Habit reminder flow
1. Poller fires, finds habit due for user
2. Bot sends: "⏰ Time to: *Make bed*! Reply /done_<id> or tap Done"
3. User replies → `next_reminder_at = now() + recurrence_days`

### Morning brief format
```
🌅 Good morning! Here's your day:

📚 STUDY
Next: Neural Networks (Goal: Become AI Engineer) — 3/12 topics done
Goal status: On track ✅

✅ HABITS DUE TODAY
• Make bed (daily)
• Bath (every 2 days — last done 2 days ago)

📋 MILESTONES
• Launch side project — 2/5 done, deadline in 4 days ⏰

Reply /study to start your session.
```

### EOD check-in format
```
🌙 Day wrap-up!

Today you:
✅ Studied: Backpropagation (score 4/5)
✅ Habits done: Make bed ✓, Bath ✓
📋 Milestones: Wrote README (Launch side project 3/5)

🔥 Streak: 5 days — keep it up!
```

---

## Migration Plan

1. Run migration SQL (new tables + alter existing)
2. Existing `goals` rows get user_id from `settings.telegram_user_id` (single existing user = you)
3. Drop old `settings` table, create new per-user one, seed from old data
4. Refactor `supabase_svc.py` → split into `study/svc.py` + `tasks/svc.py` + `settings_svc.py`
5. Refactor `bot.py` handlers → move to `study/handlers.py` + `tasks/handlers.py`
6. Replace APScheduler per-user jobs with polling approach in `scheduler.py`
