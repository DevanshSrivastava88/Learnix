# Learnix Backlog

_Last updated: 2026-05-28_

## 🔥 Immediate (next session)

- [ ] **Test new features live** — skip flow, /timesheet, /skipgraph in Telegram
- [ ] **Fix "Cancel" pre-check bug** — bare "Cancel" text gets Gemini-classified as a task; needs string check before hitting Gemini in `handle_free_text`
- [ ] **Deploy to Railway** — `cd D:\Projects\learnix\bot && railway up --detach`; check if Railway incident resolved first

## 📋 Short-term

- [ ] Update project memory with today's changes (motivation engine, skip, timesheet, skipgraph)
- [ ] Test motivation engine triggers manually (force a trigger condition, verify message fires)
- [ ] `/skipgraph` needs data — need actual skips logged before graph is useful
- [ ] Consider NVIDIA NIM (free LLM API, OpenAI-compatible) as Gemini replacement — build.nvidia.com

## 🗓 Phase 2 — Web Dashboard

- [ ] Next.js 14 + Supabase + TypeScript + Tailwind dark
- [ ] Multi-user data view with new schema (goals, habits, skips, motivation log)
- [ ] Activity graph embed
- [ ] Skip analytics embed

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
