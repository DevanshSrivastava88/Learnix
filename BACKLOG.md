# Learnix Backlog

_Last updated: 2026-06-19_
_Project status: workInProgress_
_Auto-agent: enabled_

## ✅ Done (2026-06-14, autonomous overnight)
- **Motivation 10x — Increment 1 (context engine)** — `gather_user_context()` pulls real
  history (most-avoided task by name, best/worst weekday, recent wins, streak, skip-rate,
  persona; best-effort, never raises). Rewired `generate_motivation_message` +
  `generate_struggle_support` → real specifics + identity framing. Grounded in Exocortex
  (`D:\Projects\moto_moto`) research. 16 new tests, 217 green. Commit f99c24f2.
- **Web UI — cute cross-out task list** (`web/`) — FastAPI over `bot/tasks/svc.py` +
  Vite/React/TS/Tailwind/Motion. **Restyled to Exocortex dark HUD** (acid-green #c7ff38, DM Mono +
  Manrope, grid bg, acid strikethrough). Single user (`LEARNIX_WEB_UID`). Same Supabase data.
  Commits 71a71588, fb6c9e18.
- **Web UI DEPLOYED LIVE** → https://learnix-web-production.up.railway.app — own Railway service
  `learnix-web` (isolated from the bot), single Docker image (FastAPI serves built React + /api).
  Set on the service: `RAILWAY_DOCKERFILE_PATH=web/Dockerfile`, SUPABASE_URL/KEY, LEARNIX_WEB_UID.
  Redeploy: `railway up --service learnix-web --ci` from repo root. Commits f06cac6a, ab852d00.
  **Next polish ideas:** habit/study type badges, due-date chips, drag-reorder, auth (it's
  currently public + single-uid — anyone with the URL sees the tasks).

## 🎯 Motivation engine 10x — remaining increments

**Increment 2 (next):** Memory-of-what-works — add outcome tracking to `motivation_log` (did
the user re-engage within 24h of a nudge? needs a migration adding a column) + **comeback
celebration** trigger (anti-AVE: returning after a 2+ day gap / rebuilding a streak = a moment).
Then bias future tone toward what landed.
**Parked (memory `project_learnix_motivation_10x.md`):** #4 adaptive timing, full #6 pattern
engine, #8 sentiment read, Exocortex crisis classifier (safety — fold in soon).

### Original 10x reference

**Goal:** make motivation feel personal, earned, and genuinely helpful — not generic coach lines.

**What exists now (`motivation_svc.py`):**
- Proactive poller, ≤1/24h, hour-gated: daily_skip_burst, streak_broken, low_weekly_rate, no_activity
- Reactive: struggle phrases → validate + real streak + GUARANTEED concrete offer (pause/push/scale)
- Comeback note on 2nd/3rd+ skip
- Messages: single LLM `_ask` with a tone guide per trigger. No memory of past messages, no
  personalization beyond streak count.

**10x directions (decide together next session):**
1. **Memory of what works** — log which nudges → user re-engaged; favor those tones (table: motivation_log already exists, add outcome tracking).
2. **Specifics, not platitudes** — reference the actual task/goal/topic they're avoiding + their best day/week, recent wins by name. Pull real data into the prompt.
3. **Identity-based framing** — "you're someone who shows up" vs "do your task". Tie to their goals.
4. **Adaptive timing** — learn each user's active hours from message/activity timestamps; nudge when they're actually reachable, not fixed 8am.
5. **Comeback celebration** — when they return after a slump or rebuild a streak, make it a moment.
6. **Pattern insight** — "you skip most on Mondays / after 9pm — want to move that habit?" (data-driven, actionable).
7. **Right-sized offers** — auto-suggest scaling (2x/day → 1x) when skip rate high, before they quit.
8. **Tone match to persona + mood** — flirty/friendly already; add read of message sentiment.
- Tests: extend test_motivation_reactive.py + add motivation cases to test_all.py.

## 🔥 Immediate (next session)

- [x] **Multi-task in one message** — "add call shreysh in 1 h and mum in 2 h" only creates the
  first task; understand_message returns a single task object. Needs tasks: [] array support.

- [ ] **Monitor 70B quota** — understand_message uses llama-3.3-70b-versatile with 8B fallback; if quota exhausts midday, routing quality drops (8B misclassifies). Watch logs for fallback hits.
- [x] **chat_history table growth** — rows accumulate forever; add periodic cleanup (delete rows older than 7 days)
- [x] **Remove dead code** — `claude_svc.classify_intent` had zero production callers (superseded by `understand_message`'s unified intent+task extraction); removed the function + its 5 now-orphaned tests in `test_breakdown.py`. `parse_task` and `skip_time_parser` are still actively used (by `/newtask` and the skip/timesheet flows respectively) — not dead, left as-is.
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

## ✅ Done (2026-06-13)

- **FEATURES.md baseline** — full feature list + change guidelines (regression guard). Commit 17082fca.
- **Persona option** — /persona flirty|normal, per-user (migration 009). Commit 17082fca.
- **Conversation-trap fix** — habit time-prompt no longer swallows following messages.
- **3 sweep bugs fixed (98312744)** — skip one-time task crash (timedelta(days=None) → status=skipped,
  migration 010); "mark X important" misroute (verb guard); "I want to learn X" → create_goal.
- **Multi-task / resume / JSON-unwrap** (54094241) — extra_tasks[], resume_task intent; CRITICAL:
  _ask_json blanket-unwrap sent every intent to chat — now only single-key {"items":[...]} unwraps.

## ✅ Study system rebuilt (2026-06-13) — guided daily plan
- Goal + target date → auto topics + dated plan; "study X"/daily nudge → Day N/Total on-track
  header + lesson + quiz; weak topics resurface; /progress shows track. Migrations 010, 011.
  Commits 5f84c667, ce608a20. (3 increments shipped + live-verified.)

## 🔜 Next
- **"delete my X goal" NL bug** — manage_goal name extraction mangles goal name; apply
  strip-prefix like task titles.
- **Study E2E**: verify full quiz completion advances day + marks topic done in a live run
  (unit-covered; header/lesson live-verified).
- **Phase 2 web dashboard** (Next.js).

## ✅ Done (2026-06-12)

- **Subtasks** — AI breakdown with review loop (yes/no/natural-language revision), manual
  "add subtask Y to X", indented dash display under parent, done completes subtask, cascade
  delete. Stored as "Parent — Step N: Title" rows, no migration. Commit 458f98df.
- **Weekday dates** — "on monday at 5pm" etc; LLM names the weekday, Python computes offset
  (LLM miscounted); plain "8am" replies computed deterministically (8B returned garbage).
- **Token cuts** — log.txt learnix group compressed 218→145 lines; project memory file
  trimmed to conciseness rule.
- **Stress suite + 3 fixes** — 10-case live suite (test_edge_cases.py): inline-timed habits
  create immediately; done preserves custom clock time (was drifting 9pm → 2:52pm); delete
  searches paused tasks. Retest 3/3 (test_retest_fixes.py). Committed 2b7dc3a3.
- **Habit logic overhaul** — no-time habit = no reminder (was reminding at creation minute);
  7pm IST evening digest of unscheduled tasks + reminder-less habits; 🔁 marker in list,
  no-time habits in Upcoming ("tomorrow") + Unscheduled (with frequency); type words stripped
  from titles. Live tested 4/4. Committed 2c1d9dbc.
- **Day support + list sections** — day_offset from LLM ("tomorrow"=1, works without clock time);
  date survives the time follow-up, "no" → 9am default that day; inline "tomorrow at 7am" exact;
  /tasks grouped Today / 📅 Upcoming / Unscheduled. Live tested 4/4. Committed a46e7768.
- **Phantom time guard re-wired** — refactor had orphaned _TIME_EXPR (defined, uncalled);
  "add fart" intermittently got a 23h59m reminder from a hallucinated time. Now any
  model-provided time is discarded when the user's message has no time words. Regex widened
  ("in 30", "next hour", "an hour", "half hour"). Title rule: keep activity verb
  ("add cook X" no longer drops "Cook"). Committed 5ffc19d6.
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
