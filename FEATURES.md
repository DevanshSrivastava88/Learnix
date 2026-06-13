# Learnix — Feature Baseline & Change Guidelines

_Single source of truth for what the bot does. Update it when a feature is added or
changed. Every code change must keep everything below working._

Bot: **@Quest3131Bot** (disrupto) · LIVE on Railway · 195 unit tests · `test_all.py` = 32/32 live.

> **Full live regression:** `python test_all.py` runs all 32 feature checks end-to-end
> (robust harness: per-run session copy, settle-based replies, DB pre-clean). Last: 32/32.

---

## 🛡 Change Guidelines (read before touching code)

1. **Never break a feature in this list.** Before shipping, run the relevant live
   Telethon test (`test_*.py`) AND `pytest bot/tests` (must stay green).
2. **One concern per change.** Small, surgical edits — no drive-by refactors.
3. **Deploy = `railway up` from `bot/`**, wait until status leaves Building, then
   wait ~45s more for the container to actually swap before live-testing (early
   tests hit the OLD container and lie).
4. **LLM-first:** understanding via one `understand_message()` call. Python only does
   arithmetic, validation, and deterministic guards on top — never regex-parses meaning.
5. **8B fallback is dumb.** Any critical routing needs a deterministic guard
   (action-verb prefix, "habit" keyword, etc.) so it survives the 8B model.
6. **Clean test data** from the DB after every live run (Telethon scripts create real rows).
7. After every change: update this file if features changed, plus log.txt + BACKLOG.md.

---

## ✅ Existing Features (the baseline)

### Tasks & Reminders (natural language)
- **Add one-time reminder** — "remind me to call mom at 4pm" / "...in 30 mins" / "...tomorrow at 10am" / "...on monday at 5pm"
- **Add multiple in one message** — "call X in 1h and Y in 2h" → both created
- **Add unscheduled** — "add buy groceries" → asks for a time, "no" leaves it unscheduled
- **Exact times** — clock times computed deterministically (LLM names HH:MM, Python computes IST); no drift
- **Day offsets** — tomorrow / day-after / weekday names, survive the "what time?" follow-up
- **done X** — completes one-time tasks/subtasks (removed); habits reschedule + streak
- **skip X today** — logs skip, reschedules habit by recurrence
- **delete X** — removes task (+ cascades to its subtasks); finds paused tasks too
- **pause X / resume X** — toggle reminders; free-text and /pause /resume
- **reschedule** — "move X to 8pm" updates existing task's time
- **mark X important** — ⚡ flag, reminds hourly till EOD
- **delay / snooze** — push an existing reminder

### Subtasks (break a big task down)
- **breakdown** — "break down X" proposes AI steps for REVIEW (yes/no/natural-language revision); nothing created until "yes"
- **add subtask Y to X** — manual single subtask
- Stored as `Parent — Step N: Title` rows; shown indented under parent in /tasks; no reminders of their own

### Habits
- **add habit X** / "X every day" — recurring; inline time ("at 9am") creates immediately
- **No time = no reminder** — listed only, surfaced in the 7pm evening digest
- done resets for next occurrence + streak

### Views
- **/tasks** (or "list") — grouped **Today / 📅 Upcoming / Unscheduled**, 🔁 marks habits, subtasks indented
- **/schedule** — full day: automatics + habits + live reminders
- **/graph** — activity bar chart (matplotlib photo)
- **/skipgraph** — 30-day skip chart + completion rate
- **/settings** — study/morning/EOD times, call reminders, **personality**
- **/help** /info — command + capability list

### Study — Guided Daily Plan ✨ (rebuilt 2026-06-13)
- **create goal** — "I want to learn X" → pick difficulty + target date → bot AUTO-generates
  topics and builds a **dated study plan** (topics spread evenly start→target via `_plan_offsets`)
- **Guided session** — "study X" (or the daily nudge at study time) shows **Day N/Total (on track/behind)**,
  runs today's scheduled topic: lesson → 5-question quiz → pass (≥3) completes + advances, else needs_revision
- **On-track tracking** — `get_plan_status`: behind only if topics are *past-due* (today's isn't overdue)
- **Weak-topic review** — completed topics with quiz ratio < 0.8 (or needs_revision) resurface FIRST
- **/plan** (or "my plan") — full dated schedule with status icons (✅🔁⏭⬜) + on-track header
- **/progress** — Day N/Total header, up-next topic, catch-up list, review hints (planned goals);
  topic-tree view for unplanned goals
- **Morning brief** shows the plan's Day N/Total + today's topic
- **Manage by text** — "delete/pause/resume my X goal" act on the matched goal (delete asks confirm)
- **/goals /topics**, study/skip a specific topic, /addtopic, /editgoal, /deletegoal, /pausegoal
- breakdown a goal into subtopics; bulk topic import from bullet lists; streak; bubble-up completion

### Reminders engine (scheduler)
- Normal tasks: 2 reminders/day then auto-skip; important: hourly till EOD
- **Morning brief** (08:00), **EOD check-in** (21:00), **7pm evening digest** (unscheduled + reminder-less habits)
- **Twilio** calls + IVR (press-1 done / press-2 skip), missed-call webhook — opt-in /twilio on

### Personality (option)
- **/persona flirty** (sexy/spicy) | **/persona normal** — flavors the chat tone; default friendly. Per-user in DB (migration 009)

### Other
- **Voice notes** — Gemini transcribes .ogg → processed as text
- **Onboarding** — any first message triggers welcome (no /start needed)
- **Persistent chat context** — Supabase chat_history (survives redeploys), 7-day auto-cleanup
- **/clear** (confirm) wipes data; /cancel /reset escape stuck flows

---

## 🐞 Known open bugs
_(none currently — "delete/pause my X goal" fixed; goal names title-cased; full guided study
loop verified: plan build → study → advance → /plan → morning brief.)_

## ⚠️ Known limitations (not bugs)
- Guided study uses the FIRST in-progress goal (goals[0]). Multiple concurrent planned goals
  aren't interleaved — second goal won't get daily nudges until the first is done/paused.
- Multi-task split is best-effort (8B): "call X and Y" usually splits, but duration-phrased
  pairs ("stretch in 30 mins and meditate in 45 mins") sometimes merge into one task.
