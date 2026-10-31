# Learnix Backlog

_Last updated: 2026-10-31_
_Project status: workInProgress_
_Auto-agent: enabled_

## ✅ Done (2026-10-31, autonomous)
- **tests/test_parse_task.py** — 19 new unit tests for `claude_svc.parse_task` with zero prior coverage: `returns_dict_on_valid_llm_response`, `returns_empty_dict_on_non_dict_response`, `returns_empty_dict_on_list_response`, `returns_empty_dict_on_string_response`, `strips_add_prefix`, `strips_track_prefix`, `strips_remind_me_to_prefix`, `strips_remind_me_about_prefix`, `strips_schedule_prefix`, `strips_create_prefix`, `clean_title_unchanged`, `strips_habit_prefix`, `strips_habbit_typo_prefix`, `strips_daily_prefix`, `strips_at_pm_suffix`, `strips_at_24h_time_suffix`, `strips_embedded_time_with_colon_format`, `time_str_and_type_preserved`, `empty_title_returns_without_title_key_override`. Suite: 611 tests, all green.

## ✅ Done (2026-10-28, autonomous)
- **tests/test_cmd_tasks.py** — 16 new unit tests for `cmd_tasks` in `tasks/handlers.py` with zero prior coverage: `no_tasks_replies_empty`, `today_task_shows_today_header`, `habit_has_recycle_marker`, `non_habit_no_recycle_marker`, `time_label_on_the_hour`, `time_label_with_minutes`, `upcoming_task_tomorrow_label`, `upcoming_task_future_date_label`, `unscheduled_task_in_unscheduled_section`, `unscheduled_habit_daily_shows_every_day`, `unscheduled_habit_multi_day_frequency`, `unscheduled_hint_message`, `untimed_habit_appears_in_upcoming_with_tomorrow_label`, `subtask_indented_under_parent`, `orphan_step_renders_as_plain_task`, `multiple_sections_all_present`. Suite: 592 tests, all green.

## ✅ Done (2026-10-26, autonomous)
- **tests/test_settings_svc.py** — 16 new unit tests for previously uncovered `settings_svc.py` functions with zero prior coverage: `upsert_settings` (returns first row, returns {} on empty data, injects user_id into payload), `set_daily_time`, `set_morning_brief_time`, `set_eod_time`, `set_persona` (each delegates to upsert_settings with correct key), `get_persona` (returns stored persona, returns "default" when None, returns "default" when key missing), `get_all_users` (returns rows, returns [] when None), and two uncovered `update_streak` paths (`last_study_date is None` → streak starts at 1, `delta == 0` same-day → streak unchanged) plus a date-object last_study_date branch and upsert call verification. Suite: 576 tests, all green.

## ✅ Done (2026-10-25, autonomous)
- **tests/test_delete_settings_handlers.py** — 21 new unit tests for `cmd_deletetask`, `deletetask_select`, `deletetask_confirm`, `cmd_settings`, and `cmd_persona` in `tasks/handlers.py` with zero prior coverage: `cmd_deletetask_no_tasks_replies_empty`, `cmd_deletetask_shows_task_titles`, `cmd_deletetask_stores_tasks_in_user_data`, `deletetask_select_found_stores_task_and_asks_confirm`, `deletetask_select_not_found_replies_error`, `deletetask_select_empty_list_replies_error`, `deletetask_confirm_yes_deletes_task`, `deletetask_confirm_yes_reply_contains_title`, `deletetask_confirm_cancel_keeps_task`, `deletetask_confirm_cancel_replies_kept`, `cmd_settings_shows_all_fields`, `cmd_settings_twilio_on_shows_on`, `cmd_settings_twilio_off_shows_off`, `cmd_settings_flirty_persona_shows_flirty_label`, `cmd_persona_flirty_sets_flirty`, `cmd_persona_sexy_sets_flirty`, `cmd_persona_normal_sets_default`, `cmd_persona_friendly_sets_default`, `cmd_persona_no_arg_shows_current_flirty`, `cmd_persona_no_arg_shows_current_friendly`, `cmd_persona_unknown_arg_shows_current`. Suite: 560 tests, all green.
## ✅ Done (2026-10-23, autonomous)
- **tests/test_task_action_handlers.py** — 24 new unit tests for `cmd_pause`, `handle_pause_task`, `cmd_resume`, `handle_resume_task`, `cmd_complete`, `handle_complete_task`, and `handle_done` in `tasks/handlers.py` with zero prior coverage: `cmd_pause_no_tasks_replies_empty`, `cmd_pause_lists_active_tasks_with_shortids`, `cmd_pause_queries_active_status`, `handle_pause_task_found_pauses_and_replies`, `handle_pause_task_not_found_replies_error`, `handle_pause_task_prefix_match`, `cmd_resume_no_paused_replies_empty`, `cmd_resume_lists_paused_tasks`, `cmd_resume_queries_paused_status`, `handle_resume_task_found_activates_and_replies`, `handle_resume_task_not_found_replies_error`, `cmd_complete_no_milestones_replies_empty`, `cmd_complete_lists_milestones_only`, `cmd_complete_shows_shortid_links`, `handle_complete_task_found_marks_completed`, `handle_complete_task_logs_milestone_activity`, `handle_complete_task_reply_includes_title`, `handle_complete_task_not_found_replies_error`, `handle_done_marks_task_done`, `handle_done_logs_habit_activity`, `handle_done_reply_shows_recurrence_days`, `handle_done_shows_streak_when_greater_than_one`, `handle_done_no_streak_message_when_streak_is_one`, `handle_done_not_found_replies_error`. Suite: 539 tests, all green.

## ✅ Done (2026-10-22, autonomous)
- **tests/test_format_morning_brief.py** — 13 new unit tests for `format_morning_brief` and `format_eod` in `scheduler.py` with zero prior coverage for these paths: `morning_brief_plan_on_track_shows_day_and_status`, `morning_brief_plan_behind_shows_behind_status`, `morning_brief_milestone_overdue`, `morning_brief_milestone_near_deadline`, `morning_brief_milestone_far_deadline`, `morning_brief_milestone_no_target_date`, `morning_brief_habit_due_today_shows_due_today`, `morning_brief_habit_future_shows_next_date`, `morning_brief_unscheduled_task_appears_in_section`, `morning_brief_no_unscheduled_section_when_all_have_reminders`, `morning_brief_missed_yesterday_listed`, `morning_brief_no_missed_section_when_none_missed`, `format_eod_studied_today_topic_shown`. Suite: 515 tests, all green.

## ✅ Done (2026-10-21, autonomous)
- **tests/test_get_missed_yesterday.py** — 10 new unit tests for `get_missed_yesterday` in `scheduler.py` with zero prior coverage: `no_tasks_returns_empty`, `task_done_yesterday_not_missed`, `task_not_done_next_at_today_is_missed`, `task_not_done_next_at_tomorrow_is_missed`, `task_with_no_next_reminder_not_missed`, `task_with_stale_next_at_in_past_not_missed`, `done_check_is_case_insensitive`, `done_row_without_note_field_not_crash`, `multiple_tasks_only_undone_returned`, `none_data_from_db_handled_safely`. Suite: 502 tests, all green.
## ✅ Done (2026-10-19, autonomous)
- **tests/test_timesheet_async_handlers.py** — 18 new unit tests for async handlers in `tasks/timesheet_handlers.py` with zero prior coverage: `cmd_timesheet` (no habits → END, filters non-habit tasks, stores habits in user_data, returns TS_PLAN state, reply contains habit names, only stores habit type), `ts_plan` (no matches → error message + END, clears user_data, one valid habit schedules + END, reply contains title, unmatched listed in reply, bad time string not scheduled, two habits both scheduled, empty habits list → END, correct user_id used), `_cancel` (clears user_data, sends cancelled message, returns END). Suite: 492 tests, all green.
## ✅ Done (2026-10-16, autonomous)
- **tests/test_study_format_fns.py** — 22 new unit tests for `study/handlers.py` functions with zero prior coverage: `format_plan` (includes goal name, difficulty labels easy/medium/hard/unknown, "today" label when date matches, formatted non-today date, dash for missing date, footer count, footer goal name, numbered topics, empty list) and `_format_goal_status` (no topics placeholder, goal name, 100% progress, 50% progress, no deadline indicator, overdue ⚠️, due today 🔥, within 7 days ⏰, more than 7 days 📅, invalid date fallback). Suite: 474 tests, all green.

## ✅ Done (2026-10-15, autonomous)
- **tests/test_study_svc_extra.py** — 20 new unit tests for `study/svc.py` functions with zero prior coverage: `get_goal_difficulty` (decodes diff tag, defaults to medium, handles None), `get_topic` (found/not-found), `update_goal_status` (correct status passed to update), `update_topic_status` (sets status+score, omits score when None, adds completed_at for terminal statuses, skips completed_at for not_started), `skip_topic` (updates to skipped), `insert_quiz_attempt` (inserts topic_id/score/attempted_at), `get_attempts_for_topic` (returns rows, None→[]), `get_next_pending_topic` (None when no goals, None when no pending, returns leaf over parent, returns first root when all leaves, fallback to topics[0] when no leaves), `get_topic_position` (root via is_null path, child via eq path, both return correct 1-based position and total). Suite: 452 tests, all green.

## ✅ Done (2026-10-14, autonomous)
- **tests/test_skip_handlers.py** — 11 new unit tests for `handle_skip_task` and `handle_skip_response` in `tasks/handlers.py` (zero prior coverage): `test_skip_task_found_sets_pending_and_replies` (sets pending_skip + sends prompt), `test_skip_task_not_found_replies_error` (no pending set on miss), `test_skip_task_matches_prefix_of_id` (prefix match works), `test_skip_response_returns_false_when_no_pending` (guard returns False), `test_skip_response_outright_skip_logs_and_reschedules` ("skip" keyword → log_skip + reschedule_task), `test_skip_response_outright_skip_uses_recurrence_days` (next_at offset matches recurrence_days), `test_skip_response_case_insensitive_skip_keyword` ("SKIP" also routes outright), `test_skip_response_valid_time_reschedules_to_parsed_dt` (parsed time → set_custom_time + log_skip with rescheduled note), `test_skip_response_valid_time_reply_contains_time_string` (reply shows IST time), `test_skip_response_invalid_time_re_prompts_and_keeps_pending` (None parse → re-prompt, pending preserved), `test_skip_response_invalid_time_does_not_log_skip` (None parse → no DB writes). Suite: 432 tests, all green.

## ✅ Done (2026-10-13, autonomous)
- **tests/test_parse_time_only.py** — 14 new unit tests for `claude_svc.parse_time_only` (zero prior coverage): fast-path clock times `test_plain_time_future_returns_utc` (3pm > 10am → today), `test_plain_time_past_rolls_to_tomorrow` (9am < 10am → next day), `test_plain_time_with_minutes` (3:30pm), `test_plain_time_midnight_noon_edge` (12pm = noon → today), `test_plain_time_day_offset_overrides_roll` (day_offset=1 overrides roll logic), `test_plain_time_result_is_utc` (tzinfo check); LLM fallback path `test_llm_minutes_returns_future_utc` ({"minutes": 30}), `test_llm_minutes_zero_returns_none`, `test_llm_hhmm_future_time`, `test_llm_hhmm_past_rolls_to_tomorrow`, `test_llm_hhmm_tomorrow_flag_adds_day`, `test_llm_hhmm_with_day_offset` (day_offset=2), `test_llm_invalid_hhmm_falls_through_to_none` (bad hhmm → minutes=0 → None), `test_llm_non_dict_returns_none`. Suite: 421 tests, all green.

## ✅ Done (2026-10-12, autonomous)
- **tests/test_claude_svc_study_fns.py** — 19 new unit tests for previously untested `claude_svc` study/breakdown functions (zero prior coverage): `revise_subtasks` (returns revised list, filters empty strings, strips whitespace, truncates to 10 items, raises ValueError on non-list, prompt includes parent/feedback/numbered-steps, coerces non-string items, handles empty existing steps), `teach_topic` (returns LLM string, omits notes when absent, includes notes in prompt when present), `generate_quiz` (returns list of dicts, truncates to 5, raises on non-list), `score_answer` (returns correct+explanation, returns false for wrong answer, passes all three fields to prompt). Suite: 407 tests, all green.

## ✅ Done (2026-10-11, autonomous)
- **tests/test_weekday_offset.py** — 19 new unit tests for `_weekday_offset_from_text` in
  `tasks/handlers.py` (zero prior coverage): no-weekday returns None (3 cases), same-day
  full/abbreviated returns 7 (next-week semantics), next-day full/abbreviated returns 1, all
  7 weekdays and abbreviations produce offsets in [1, 7], deterministic arithmetic checks for
  Monday/Friday/Sunday, weekday embedded in sentence, long-form abbreviations (tues, thurs,
  satur), case insensitivity (upper/mixed). Suite: 388 tests, all green.

## ✅ Done (2026-10-05, autonomous)
- **tests/test_tasks_svc.py** — 20 new unit tests for previously untested `tasks/svc.py` CRUD ops:
  `list_tasks` (returns rows, None→[], status filter), `get_task` (found, not-found), `delete_task`
  (correct id passed), `delete_subtasks` (removes step rows, zero when no steps, checks both active
  and paused), `create_milestone` (inserts correct row), `list_milestones` (returns items, None→[]),
  `count_milestones` (done/total counts, empty), `toggle_milestone` (done/undone), `log_skip`
  (default note, custom note), `reschedule_task` (updates next_reminder_at),
  `set_custom_time` (sets time + custom flag). Suite: 340 tests, all green.
  Also cherry-picked 4 orphaned detached-HEAD commits (10-02/03/04 work) onto master.

## ✅ Done (2026-10-04, autonomous)
- **tests/test_twilio_svc.py** — 6 new unit tests for `make_reminder_call` (zero prior coverage):
  env vars absent (all missing, one missing), no phone number returns False, success with IVR Gather
  flow (verifies action_url + task/user params in TwiML), success with plain Say fallback, exception
  returns False. Also cherry-picked two orphaned commits from 2026-10-02/03 onto master (those runs
  committed in detached HEAD). Suite: 320 tests, all green.

## ✅ Done (2026-10-03, autonomous)
- **tests/test_tasks_svc.py** — 12 new unit tests for `get_reminder_count`, `increment_reminder_count`,
  `reset_reminder_count` in `tasks/svc.py` (zero prior coverage): count absent/None/simple/compound
  descriptions; increment from zero, from existing, with important-flag prefix, appended to plain
  description; reset removes counter, preserves other fields, no-ops when absent, handles empty.
  Suite: 314 tests, all green.

## ✅ Done (2026-10-02, autonomous)
- **tests/test_missed_call_webhook.py** — 22 new unit tests for `missed_call_webhook.py` (zero prior
  coverage): `_twilio_signature` (pure HMAC-SHA1, 2 cases), `_send_telegram` (correct URL/payload,
  exception swallowed), `_notify_all` (multi-user, TELEGRAM_CHAT_ID fallback, no-op when neither),
  `/twilio/missed-call` Flask route (403 bad sig, 204 non-missed, 200 + notify on no-answer/busy/failed,
  XML body), `/twilio/call-response` route (missing param errors, invalid user_id, digit 1 done flow,
  digit 2 skip flow, unknown digit no-op, empty-title fallback), `/health`. Suite: 302 tests, all green.
## ✅ Done (2026-09-29, autonomous)
- **tests/test_scheduler.py** — 9 new unit tests for `format_evening_digest` (zero prior
  coverage: empty-when-scheduled, shows-unscheduled, 🔁 habit marker, • task bullet,
  subtask exclusion, milestone exclusion, empty list) and `format_eod` habit paths
  (done-today ✅ vs not-done-today). Suite: 280 tests, all green.
  Also cherry-picked the detached-HEAD commit `e9b88ed` (test_timesheet_handlers, 15 tests)
  onto master — it was committed but never pushed in the prior session.

## ✅ Done (2026-09-28, autonomous)
- **tests/test_timesheet_handlers.py** — 15 new unit tests for `_find_habit` (8 cases:
  exact, case-insensitive, partial, reverse-partial, no match, empty list, mixed-case) and
  `_parse_timesheet_input` (7 cases: valid dict, list/string/None non-dict responses, LLM
  exception, single habit, prompt content check). Suite: 271 tests, all green.

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

**Increment 2 (partial, auto 2026-08-22):** `comeback_celebration` trigger shipped — new highest-priority
trigger in `evaluate_triggers`: fires 09-20 IST when `_is_comeback_day()` detects activity today
after a 2+ day gap. Anti-AVE framing ("you're still the person who shows up"). 11 new tests, 256 green.
**Remaining:** Memory-of-what-works — outcome tracking in `motivation_log` (needs a migration adding
a column, Supabase required). Then bias future tone toward what landed.
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

- [x] **Monitor 70B quota** — the 70B→8B fallback in `understand_message` failed silently (no log line existed); added `logger.warning(...)` on the except path (+ module logger) so fallback hits are now visible in Railway logs. Watching the logs themselves is still a manual follow-up.
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
- [x] Activity graph embed
- [x] Skip analytics embed

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
- ~~**"delete my X goal" NL bug** — manage_goal name extraction mangles goal name; apply
  strip-prefix like task titles.~~ ✅ Fixed 2026-08-18 (auto) — action-verb prefix strip added to `extract_goal_name_from_message` in claude_svc + nim_svc; 7 new tests, 234 green.
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
