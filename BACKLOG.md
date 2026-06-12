# Learnix Backlog

_Last updated: 2026-06-12_
_Project status: workInProgress_
_Auto-agent: enabled_

## 🔥 Immediate (next session)

- [ ] **Multi-task in one message** — "add call shreysh in 1 h and mum in 2 h" only creates the
  first task; understand_message returns a single task object. Needs tasks: [] array support.

- [ ] **Monitor 70B quota** — understand_message uses llama-3.3-70b-versatile with 8B fallback; if quota exhausts midday, routing quality drops (8B misclassifies). Watch logs for fallback hits.
- [ ] **chat_history table growth** — rows accumulate forever; add periodic cleanup (delete rows older than 7 days)
- [ ] **Remove dead code** — classify_intent + parse_task in claude_svc.py are now only used by /newtask conversation flow + tests; skip_time_parser only by legacy time_str path. Consolidate later.
- [ ] **Test new features live** — skip flow, /timesheet, /skipgraph in Telegram
- [x] **Fix "Cancel" pre-check bug** — bare "Cancel" text gets Gemini-classified as a task; needs string check before hitting Gemini in `handle_free_text`
- [ ] **Deploy to Railway** — still failing: "Failed to read app source directory" from nixpacks. Railway incident not resolved. Retry later.
- [x] **Twilio missed call feature** — optional per-user toggle (on/off via /settings). Use Twilio creds from talking-agent project. User number: +918004844144

## 📋 Short-term

- [x] Update project memory with today's changes (motivation engine, skip, timesheet, skipgraph)
- [x] Test motivation engine triggers manually (force a trigger condition, verify message fires) — automated unit tests added in `tests/test_motivation_svc.py` (30 tests: all triggers, priority order, edge cases, async send flow)
- [ ] `/skipgraph` needs data — need actual skips logged before graph is useful
- [x] Consider NVIDIA NIM (free LLM API, OpenAI-compatible) as Gemini replacement — build.nvidia.com

## 🗓 Phase 2 — Web Dashboard

- [ ] Next.js 14 + Supabase + TypeScript + Tailwind dark
- [ ] Multi-user data view with new schema (goals, habits, skips, motivation log)
- [ ] Activity graph embed
- [ ] Skip analytics embed

## ✅ Done (2026-06-12)

- **Absolute time fix** — "set [task] to [time]" now routes to reschedule_task (was creating a
  duplicate new task); absolute clock times returned as time_hhmm by the LLM, Python computes
  the exact IST datetime and stores it directly (LLM minute-arithmetic drifted: "11 pm" → 10:51pm).
  parse_time_only got the same hhmm/minutes split. Reply says "at 8:00 PM" for clock times.
  Live tested (test_set_time.py, test_exact_time.py). Committed d925cc0a.
- **Bare "cancel" fake-success fix** — pre-LLM cancel shortcut said "Cancelled! 👍" without
  doing anything when no flow was pending (the permanent `onboarded` flag made user_data always
  look non-empty). Now: quiz/pending flows still abort instantly; otherwise "cancel" falls
  through to LLM routing and deletes the last-discussed task from history. Also: empty task_ref
  resolves from history like pronouns, and exact title match wins in _fuzzy_match_task (substring
  matching dragged "Call Shreyash" into disambiguation for "Call Shreyash Test"). Live tested
  (test_bare_cancel.py: add → 1h → cancel → deleted). 170/170 tests.

- **Unified LLM routing** — `understand_message()` in claude_svc.py: ONE call returns intent +
  task fields (title/type/time_minutes) + task_ref (pronoun resolution). Replaces
  classify_intent + parse_task + regex time parsing per message (3 calls → 1).
  Uses llama-3.3-70b-versatile (8B misclassified "add water the plants" → chat,
  returned literal "it" as task_ref) with automatic 8B fallback on quota exhaustion.
- **Persistent chat history** — migration 008 `chat_history` table; `chat_history_svc.py`
  DbHistory write-through list. Context survives Railway redeploys — "cancel it" after a
  deploy now resolves. Bot history lines carry real task titles ("[added task: X]") instead
  of generic placeholders. Wiped on "confirm delete".
- **Safety guards** — explicit add/track/remind prefix always routes to task (LLM override);
  bare pronouns (it/that/this) resolve from history or ask, NEVER fuzzy-match (8B once
  deleted "Meditation Task" because it contains "it"); clarify must never ask for time.
- **Earlier same session:** migration 007 (task_type='task' allowed — inserts were silently
  failing the CHECK constraint while bot said "Added"), honest error replies on Groq 429
  and failed inserts, LLM time parsing for bare "1 hr" follow-ups, retry bump (4 tries, 1s base).
- **Tests:** fixed 8 test_breakdown tests patching wrong function (_ask_json vs _ask_json_array,
  drifted after a prior session's refactor — tests were making real network calls); added
  isinstance list validation in breakdown fns. 105/105 green. Live Telethon suite: inline time,
  bare "1 hr", "cancel it" context resolution, gibberish rejection — all PASS.
- Committed 75282e22 (rebased onto slave1's [auto] commits), pushed.

## ✅ Done (2026-06-11)

- Add `nim_svc.py` — NVIDIA NIM proof-of-concept LLM provider, drop-in alternative to `claude_svc.py`.
  Uses OpenAI-compatible API (`integrate.api.nvidia.com/v1`, model `meta/llama-3.1-70b-instruct`).
  Same function signatures as `claude_svc.py`; `transcribe_voice` raises `NotImplementedError` (NIM
  has no audio endpoint). Added `openai>=1.0.0` to requirements. 27 new tests in
  `tests/test_nim_svc.py` covering lazy init, `_ask`, `_ask_json` (JSON-mode flag), all high-level
  functions, and the `NotImplementedError` guard; suite now 169 tests, all green.
  To activate: set `NIM_API_KEY` env var and replace `import claude_svc` with `import nim_svc` where needed.

## ✅ Done (2026-06-10)

- Add tests for `get_skips_last_n_days`, `get_done_counts_last_n_days`, `build_skip_graph` in
  `tests/test_analytics_svc.py` — 7 new tests covering: data return, None-guard, empty-data graph,
  skip+done data graph (with most-skipped task label), and None task lookup; suite now 142 tests,
  all green

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
