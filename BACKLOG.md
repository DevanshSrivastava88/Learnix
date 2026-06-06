# Learnix Backlog

_Last updated: 2026-06-06_
_Project status: workInProgress_
_Auto-agent: enabled_

## 🔥 Immediate (next session)

- [ ] **Test new features live** — skip flow, /timesheet, /skipgraph in Telegram
- [x] **Fix "Cancel" pre-check bug** — bare "Cancel" text gets Gemini-classified as a task; needs string check before hitting Gemini in `handle_free_text`
- [ ] **Deploy to Railway** — still failing: "Failed to read app source directory" from nixpacks. Railway incident not resolved. Retry later.
- [x] **Twilio missed call feature** — optional per-user toggle (on/off via /settings). Use Twilio creds from talking-agent project. User number: +918004844144

## 📋 Short-term

- [x] Update project memory with today's changes (motivation engine, skip, timesheet, skipgraph)
- [ ] Test motivation engine triggers manually (force a trigger condition, verify message fires)
- [ ] `/skipgraph` needs data — need actual skips logged before graph is useful
- [ ] Consider NVIDIA NIM (free LLM API, OpenAI-compatible) as Gemini replacement — build.nvidia.com

## 🗓 Phase 2 — Web Dashboard

- [ ] Next.js 14 + Supabase + TypeScript + Tailwind dark
- [ ] Multi-user data view with new schema (goals, habits, skips, motivation log)
- [ ] Activity graph embed
- [ ] Skip analytics embed

## ✅ Done (2026-06-06)

- Fix broken test `test_handle_task_action_freetext_stores_pending_on_ambiguous` — task 2's
  title `"Morning workout — Step 1: Warmup"` was silently filtered by the `" — Step "` exclusion
  in `handle_task_action_freetext`, leaving only 1 match (not ambiguous) and crashing on a
  MagicMock > int comparison. Changed task 2 title to `"Morning workout at home"` so both tasks
  survive the filter and trigger the ambiguous-match path the test intended; suite now 105 tests,
  all green

## ✅ Done (2026-06-02)

- Fix test suite ordering failures — add `tests/conftest.py` that pre-imports real modules
  (`settings_svc`, `scheduler`, `study.handlers`) before `test_pending_task_action.py`'s
  collection-time stub injection, and restores real `tasks.svc`/`settings_svc` callables
  before any test runs; suite now 92 tests, all green

## ✅ Done (2026-06-01)

- Add tests for `skip_time_parser` — 17 cases covering in-X-min/hour, absolute times (am/pm, 24h), tomorrow patterns, roll-to-next-day edge, None on invalid input; suite now 34 tests, all green

## ✅ Done (2026-05-30)

- Fix claude_svc lazy Gemini init — module-level genai.configure() blocked test collection; deferred to first call so all 17 tests pass

## ✅ Done (2026-05-29)

- Twilio missed-call webhook design + Flask endpoint (`bot/missed_call_webhook.py`)
  - Twilio status callback → Flask → Telegram message
  - Signature validation, IST timestamp, no-answer / busy / failed detection
  - Ready to deploy on Railway as a separate service or ngrok for dev
  - Env vars needed: TWILIO_AUTH_TOKEN, TELEGRAM_CHAT_ID (+ existing BOT_TOKEN)

## ✅ Done (2026-05-28)

- Freetext confirm/re-describe loop fix (bot.py + tasks/handlers.py)
- Interval reminder type (every hour, every 30 mins)
- /schedule command (daily automatics + habits + live reminders)
- Skip system (/skip_<id> + reschedule or log outright)
- /timesheet — plan today's habits with natural language times
- /skipgraph — 30-day skip bar chart + completion rate line
- Motivation engine — 4 research-backed triggers, Gemini messages, 24h cooldown
- DB migration 004 (task_skips + motivation_log tables)
- Supabase PAT token saved to memory
