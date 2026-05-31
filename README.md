# Learnix — AI Life OS Bot

Telegram bot for study tracking, habit management, and daily planning. Talk to it naturally — no slash commands needed.

**Bot:** @Quest3131Bot | **Stack:** Python + Gemini 2.5 Flash + Supabase + Railway

---

## Just Talk — No Commands Needed

| What you want | Say |
|---|---|
| See your tasks | "show me my tasks", "what do I have to do", "my habits" |
| Today's schedule | "what's my schedule", "plan my day", "what's today look like" |
| Add a habit | "I want to run every morning", "add meditation every day" |
| One-time reminder | "remind me to call dad at 6pm", "remind me in 20 mins to drink water" |
| Repeating reminder | "remind me to drink water every hour" |
| Mark task done | "I just did my pushups", "done with workout", "finished meditation" |
| Skip a task | "skip reading today", "skipping pushups" |
| Delete a task | "delete my running habit", "remove meditation" |
| Pause reminders | "pause workout reminders" |
| Study progress | "how am I doing", "am I on track", "how's my Python going" |
| See goals | "what am I learning", "my goals" |
| Start studying | "let's study", "quiz me", "let's do some Python" |
| Activity stats | "how active have I been", "show my stats", "how lazy have I been" |
| Skip analytics | "what did I skip most", "my skip patterns" |
| Break into steps | "break down morning workout", "give me a roadmap for ML" |

---

## Commands

### Tasks & Habits
| Command | What it does |
|---|---|
| `/newtask` | Add a habit or reminder (guided) |
| `/tasks` | List all active habits |
| `/skip_<id>` | Skip a habit — reschedule or log |
| `/deletetask` | Delete a habit |
| `/pause` / `/resume` | Pause or resume reminders |
| `/complete` | Mark a habit permanently done |

### Planning
| Command | What it does |
|---|---|
| `/schedule` | Day view — automatics + habits with next-due times. Reply with times to plan ("workout at 8am, reading at 10pm") |

### Study
| Command | What it does |
|---|---|
| `/goal` | Create a learning goal |
| `/goals` | See all goals |
| `/addtopic` | Add a topic to a goal |
| `/study` | Start a study session (teach + quiz) |
| `/progress` | Progress per topic |
| `/editgoal` / `/deletegoal` / `/pausegoal` | Manage goals |

### Analytics
| Command | What it does |
|---|---|
| `/graph` | Activity chart — last 30 days |
| `/skipgraph` | Skip patterns — which days/habits you bail on |

### Settings
| Command | What it does |
|---|---|
| `/settings` | View current reminder times |
| `/setmorning` | Morning brief time |
| `/settime` | Daily study session time |
| `/seteod` | EOD check-in time |
| `/twilio on\|off` | Toggle missed-call notifications |

### Other
| Command | What it does |
|---|---|
| `/start` | Welcome + overview |
| `/help` | Full command list |
| `/clear` | Delete all your data |
| `/cancel` | Cancel any active flow |

---

## Reminders

- Each habit gets 2 reminders/day automatically
- When a reminder fires, just reply **"done"** or **"skip"** — bot knows which task
- Interval reminders: "every hour", "every 30 mins"
- Auto-skipped after 2nd reminder with no response

---

## Break Into Steps

```
You:  break down morning workout
Bot:  Created 6 steps as daily habits
      • Wake up, hydrate
      • Dynamic warm-up
      • 20-minute cardio
      • Strength training circuit
      • Cool-down stretches
      • Shower and refuel

You:  break down Learn Python
Bot:  Added 7 topics to Learn Python
      1. Variables & Data Types
      2. Control Flow & Loops
      ...
      Use /study to go through them in order.
```

---

## Known Issues / Bugs (from testing)

- **Fuzzy match too strict**: "skip reading" doesn't match "Read 10 pages" — needs looser matching
- **Duplicate task disambiguation**: if two tasks have the same name, bot lists both with no way to distinguish
- **Tasks list shows /done_id links**: planned to remove in favour of natural language

---

## Run Locally

```bash
cd bot
python -m pytest tests/ -v   # run tests
python bot.py                 # start bot
```

## Deploy to Railway

```bash
cd bot
railway up
```

Check logs:
```bash
railway logs --service learnix-bot
```

## Project Structure

```
learnix/
├── bot/
│   ├── bot.py              # main router + all cmd handlers
│   ├── claude_svc.py       # Gemini calls (teach, quiz, classify, parse)
│   ├── scheduler.py        # APScheduler jobs (morning brief, reminders, EOD)
│   ├── analytics_svc.py    # matplotlib graph generator
│   ├── tasks/
│   │   ├── handlers.py     # task CRUD conversation flows
│   │   └── svc.py          # Supabase task DB ops
│   ├── study/
│   │   ├── handlers.py     # goal/topic/quiz flows
│   │   └── svc.py          # Supabase study DB ops
│   └── tests/
├── supabase/migrations/    # DB migrations
└── BACKLOG.md
```
