# Learnix Backlog

_Last updated: 2026-06-02_
_Project status: workInProgress_
_Auto-agent: enabled_

## 🔥 Immediate (next session)

- [ ] **Test important flag + delay end-to-end** — mark task important, verify hourly reminders till EOD
- [ ] **Test Twilio IVR** — enable calls, trigger reminder, verify press-1-done / press-2-skip works (RAILWAY_URL is set)
- [ ] **Test disambiguation flow** — "mark morning workout as important" → "Morning workout" → confirm ⚡

## 📋 Short-term

- [ ] Test motivation engine triggers manually
- [ ] `/skipgraph` needs real skip data before graph is useful
- [ ] Consider NVIDIA NIM as Gemini replacement — build.nvidia.com

## 🗓 Phase 2 — Web Dashboard

- [ ] Next.js 14 + Supabase + TypeScript + Tailwind dark
- [ ] Multi-user data view with new schema (goals, habits, skips, motivation log)
- [ ] Activity graph embed
- [ ] Skip analytics embed

## ✅ Done (2026-06-01 — massive feature day)

- Zero slash commands — everything via natural language
- Voice notes — Gemini transcribes + processes as text  
- Smart onboarding — any first message triggers welcome
- Important flag — tasks remind hourly till EOD
- Delay option — 'delay 30 mins' reschedules reminder
- Context-aware done/skip — bot remembers last reminder, no /done_id links
- Twilio IVR — press 1 done, press 2 skip, 10s timeout; calls ALL reminder types
- RAILWAY_URL env var set in Railway for IVR webhooks
- Morning brief shows missed tasks from yesterday
- Task reschedule — 'remind me about workout at 6am'
- Natural time setting — 'I want to study at 9pm'
- Goal difficulty — Easy/Medium/Hard at creation
- Jump to specific topic — 'study Control Flow'
- Skip topics mid-quiz, cancel exits quiz cleanly
- Disambiguation state persists across messages
- Test isolation fixed — 92/92 tests green
- README rewritten with full command reference
- Add tests for `skip_time_parser` — 17 cases, all green

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
