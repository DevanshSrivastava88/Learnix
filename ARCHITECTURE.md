# ARCHITECTURE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Note:** The root `CLAUDE.md` in this repo is **not** engineering docs — it's an active
> "Learnix Learning System" prompt that drives `status.json` + the `gen_ai/` quiz modules.
> That workflow is unrelated to the product code. This file is the engineering doc; read it
> (not `CLAUDE.md`) when working on the bot/web code.

---

## What Learnix is

A multi-user Telegram bot that acts as a personal "AI life OS" — plus a small web task list.
Two product systems, one Supabase database:

1. **Tasks / LifeOS** — habits (recurring reminders), one-off & interval reminders, milestones,
   skip tracking, daily planning, proactive motivation nudges.
2. **Study** — learning goals → topic trees → LLM-taught lessons + 5-question quizzes, progress
   & streak tracking, auto-generated study plans.

Users **talk to it naturally** — free text is routed by a single LLM call, not slash commands
(commands still exist as a fallback). Live bot: **@Quest3131Bot**, deployed on Railway.

---

## Repo layout — three layers, and which code is live

This repo grew in place, so dead v1 code and an alternate frontend sit next to the live code.
**Know what's live before editing:**

| Path | Status | What it is |
|---|---|---|
| `bot/` | **LIVE** | The current bot (the heart of the codebase). Edit here. `bot/tests/` = unit tests (mocked). |
| `web/api/` + `web/ui/` | **LIVE** | Deployed web task list: FastAPI + Vite/React, single Docker image. |
| `supabase/migrations/` | **LIVE** | Numbered SQL migrations — the single source of truth for schema. |
| `tests/e2e/` | **LIVE** | Telethon end-to-end tests that drive the *deployed* bot. Run **from the repo root** (`python tests/e2e/test_all.py`). |
| root `CLAUDE.md`, `status.json`, `gen_ai/` | **LIVE but unrelated** | The "learning system" meta-workflow. Not product code. |
| `legacy/` | **LEGACY v1** | First bot (`bot.py` + `services.py`): Anthropic SDK + GitHub-as-database, plus stale `render.yaml`/env. Superseded by `bot/`. Don't edit — see `legacy/README.md`. |
| `web/app/`, `web/components/`, `web/lib/` | **Alt / older** | A Next.js goals dashboard that reads Supabase directly. Separate from the deployed `web/ui` task list. |

---

## ⚠️ The LLM provider is Groq (the names lie)

The live LLM layer is **Groq running `llama-3.1-8b-instant`**, called via the **OpenAI SDK**
(`base_url=https://api.groq.com/openai/v1`). It needs **`GROQ_API_KEY`**.

- `bot/claude_svc.py` is the live LLM module. It is **named `claude_svc` for historical reasons
  only** — it does not call Anthropic. Everything imports it as the LLM layer (`import claude_svc`).
- `bot/nim_svc.py` is an unwired **NVIDIA NIM proof-of-concept** (drop-in alt, `NIM_API_KEY`).
- **Do not trust these for the provider** — they say Gemini/Anthropic and are out of date:
  `bot/CLAUDE.md`, `bot/.env.example`, `render.yaml`, root `.env.example`.

### How routing works (the architectural core)
- All natural-language understanding goes through **one call: `claude_svc.understand_message(text, context)`**
  (`bot/claude_svc.py:144`), which returns structured intent. Other typed helpers: `teach_topic`,
  `generate_quiz`, `score_answer`, `parse_task`, `daily_summary`, plus motivation generators.
- **Python never regex-parses meaning.** It does arithmetic, validation, and *deterministic guards*
  on top of the LLM output (e.g. action-verb prefixes, the word "habit") — because the 8B model is
  cheap and sometimes wrong, every critical route needs a deterministic backstop. See the "Change
  Guidelines" in `FEATURES.md`.

---

## Bot internals (`bot/`)

- **`bot.py`** — the entry point and router. Registers all command handlers, a global free-text
  handler (`handle_text` → `understand_message`), voice + contact handlers, an error handler, and
  starts the scheduler in `post_init`. Run with `python bot.py` (long-polling).
- **`tasks/`** — `svc.py` = Supabase task DB ops (create/list/mark_done/skip/reschedule…);
  `handlers.py` = Telegram conversation flows; `timesheet_handlers.py` = natural-language day planning.
- **`study/`** — `svc.py` = goal/topic DB ops; `handlers.py` = goal/topic/quiz/study-plan flows.
- **Service modules** (flat in `bot/`): `scheduler.py` (poll jobs), `motivation_svc.py` (reactive,
  context-aware nudges with a 24h cooldown; `gather_user_context()` personalizes from real history),
  `analytics_svc.py` (matplotlib activity/skip graphs), `chat_history_svc.py` (persistent chat log,
  survives restarts), `settings_svc.py`, `skip_time_parser.py` ("3pm"/"in 2h"/"tomorrow 9am" → UTC),
  `twilio_svc.py` + `missed_call_webhook.py` (optional missed-call alerts), `supabase_svc.py`
  (lazy singleton client).
- **Scheduler is poll-based** (`register_jobs`): study/morning/EOD pollers (60s) fire at each user's
  configured IST time; reminder poller (300s) sends due-task reminders; motivation poller (1800s)
  checks triggers. **All user-facing times are IST (`Asia/Kolkata`); timestamps are stored UTC.**

---

## Data layer

**Supabase Postgres is the single source of truth.** Schema lives only in `supabase/migrations/`
(numbered `001_…`→`011_…`; apply in order). Key tables: `settings`, `goals`, `topics`,
`quiz_attempts`, `tasks`, `milestones`, `activity_log`, `task_skips`, `motivation_log`,
`chat_history`, study-plan + persona tables. Everything is scoped by Telegram `user_id`
(owner uid = `584321397`). The web API deliberately **reuses `bot/tasks/svc.py`** so there is no
second source of truth.

---

## Web app (`web/`)

The **deployed** web app is a single-user task list = `web/api` + `web/ui` in one Docker image:

- **`web/api/main.py`** — FastAPI. Serves `/api/tasks` (CRUD) **and** the built React UI as static
  files. Imports the bot's data layer (finds `bot/` locally, or the vendored `_bot/` copy in the
  container). Single user via `LEARNIX_WEB_UID` (defaults to the owner uid).
- **`web/ui/`** — Vite + React + TypeScript + Tailwind + Motion. Dev server proxies `/api` → :8000.
- **`web/Dockerfile`** — multi-stage: build `web/ui` → Python image that vendors `bot/supabase_svc.py`
  + `bot/tasks/` and serves both API and UI. Build context is the **repo root**.

(`web/app` is a separate, older Next.js goals dashboard that reads Supabase directly — not part of
the deployed task-list service.)

---

## Commands

### Bot
```bash
cd bot
pip install -r requirements.txt
python bot.py                         # run (long-polling); needs bot/.env
```

### Tests
There are **two** test suites:

```bash
# 1) Unit suite — mocked Supabase + LLM, no live creds. THE one to keep green.
cd bot
python -m pytest tests/ -v
python -m pytest tests/test_tasks_svc.py::test_create_task   # single test

# 2) Live E2E — Telethon scripts in tests/e2e/ that drive the *deployed* bot.
#    RUN FROM THE REPO ROOT (they use root-relative paths: bot/.env, the session
#    file). Need a Telethon session + bot/.env + the live bot up. Create real DB
#    rows (clean them after). Slow + timing-sensitive.
pip install -r tests/e2e/requirements.txt   # telethon etc. (first time)
python tests/e2e/test_all.py                 # full live regression (~37 checks)
python tests/e2e/test_struggle_live.py       # a single live scenario
```

### Web (local)
```bash
cd web/api && uvicorn main:app --host 127.0.0.1 --port 8000   # backend :8000
cd web/ui  && npm install && npm run dev                      # frontend :5173 (proxies /api)
# or: powershell -ExecutionPolicy Bypass -File web/run.ps1
```

### Deploy (Railway)
```bash
cd bot && railway up                                  # bot service (railpack/nixpacks, python bot.py)
railway up --service learnix-web --ci                 # web service, run from repo ROOT
# web service must have RAILWAY_DOCKERFILE_PATH=web/Dockerfile set
railway logs --service learnix-bot                    # tail logs
```
**Deploy lag:** after `up` leaves "Building", wait ~45s for the container to actually swap before
running live tests — early tests hit the OLD container and lie.

### Environment
`bot/.env` (real keys; `.env.example` files are stale) needs at minimum:
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
(+ optional Twilio vars). Web uses `SUPABASE_URL`/`SUPABASE_KEY` and `LEARNIX_WEB_UID`.

---

## Conventions & gotchas

- **LLM-first, guard-backed.** Understanding via one `understand_message()` call; Python adds
  deterministic guards. Never reach for regex to infer intent.
- **`claude_svc` ≠ Anthropic.** It's Groq. See the LLM section above.
- **`FEATURES.md` is the behavioral source of truth** — it lists every shipped feature and the rule
  "never break a feature in this list." Read it before changing bot behavior. **`BACKLOG.md`** tracks
  roadmap/status. `bot/CLAUDE.md` is an engineering memory but is partly stale (LLM/test counts).
- **One concern per change**, small surgical edits — this codebase is guarded by live tests that are
  expensive to re-run.
- **Don't confuse the learning system with the product.** Root `CLAUDE.md` + `status.json` + `gen_ai/`
  are a self-contained tutoring workflow; they have nothing to do with the bot/web code.
