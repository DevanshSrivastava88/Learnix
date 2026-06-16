# Memory Integration — Decisions Log

> Porting the **exo-cortex / Atlas** long-term-memory architecture (by **Shreyash "moto"
> Dubey**, repo `shreyashdubey/exo-cortex-memory`) into our stack.
>
> **Real target:** a brand-new app (future). **Testbed now:** the Learnix bot.
> **Standing directive:** integrate everything moto cooks — he did the research. Anything we
> change, skip, or optimize gets logged here *with the why*, so (a) the future port is clean
> and (b) we can relay these decisions to moto on Discord.
>
> Last updated: 2026-06-16

---

## What Atlas does (one line)
After every message a cheap LLM call extracts what's worth remembering → structured store;
before every reply the store + a semantic search are injected into the prompt. The model
*feels* like it remembers because memory is re-fed every turn.

## Decision table

| Atlas component | Decision | Why |
|---|---|---|
| **Extract-every-turn** (cheap LLM → strict JSON of facts/goals/people/events) | **INTEGRATE** | The core value. Reuse our existing Groq call — extend it to also emit memory, not new infra. |
| **Ground-truth rule** (store only what USER confirmed, never the bot's guesses) | **INTEGRATE (verbatim prompt)** | Free, prevents hallucinated memory. Proven live (it refused to invent aunt's pronouns). |
| **Anti-meta rule** (never store "user said hi / introduced themselves") | **INTEGRATE (verbatim prompt)** | Keeps the timeline clean — the thing that kills naive memory bots. |
| **Structured store** (Postgres: profile, people, goals, events) | **INTEGRATE (adapt)** | We're already on Supabase/Postgres. Add `user_facts` / `people` / `events` tables. |
| **Sentiment timeline** (typed events: mood/progress/setback/milestone, sentiment + intensity) | **INTEGRATE** | Feeds our motivation engine real emotional context. New for us. |
| **Session summaries** (on session end → LLM → {summary, mood, open_threads} → 1 row → recap injected next session, "welcome back, last time…") | **INTEGRATE (re-boundary)** | User loves it. BUT Atlas gets a clean REPL open/close; chat has none. Need a synthetic boundary — **idle-gap** (no msg N hours → summarize) or daily rollup. Decided per app. |
| **Dedup + fuzzy merge** in apply_extraction | **INTEGRATE** | Stops duplicate facts/goals. |
| **Qdrant semantic recall** (embed events, vector search relevant past moments) | **DEFER** | Only heavy new dep. Our data is task-structured, not free chat — structured queries may be enough. Revisit if we want free-text "remember when I said…" over months. |
| **OpenAI gpt-4.1 chat + text-embedding-3-small** | **SKIP** | We're Groq-only by cost design. Keep one provider. (Embeddings only return if Qdrant comes back.) |
| **CLI auth** (PBKDF2 / getpass / admin users.py) | **SKIP** | We have our own identity (Telegram id / weblogin). New app will have its own auth. |
| **Proactivity daemon** (launchd / select-poll / checkin.py — see docs/PROACTIVITY.md in his repo) | **DEFER, STEAL POLICY** | The mechanism solves "CLI has no surface when closed" — we already have push. Copy the *policy* (two-gate Vuln∧Recept, hard-caps-before-LLM, bias-to-silence, grounded openers), not the Mac plumbing. |
| **Observability** (call_log + retrieval_log + admin replay server) | **DEFER (thin version later)** | Production-grade but heavy for now. Maybe a thin call log. |
| `get_current_datetime` tool (LLM never guesses the clock) | **ALREADY HAVE** | Our parse_time/parse_deadline + at/in guard already does this. Don't add dateparser. |

## Our optimizations on top of his design
*(things we improve, not just copy — flag these to moto)*

- **FACT-UPDATE PATH (his real gap).** Atlas `facts_add` is append-only — corrections never
  update, so `KEY FACTS` accumulates stale/contradictory entries (live-proven: exam date
  "next week" stayed after user corrected to "the 25th"). **We add `fact_updates[]` /
  `facts_remove[]` to the extractor + a retire/supersede path**, OR timestamp facts and let
  newer win on conflict. Same pattern he already uses for goals.
- *(more to be added as we build)*

## BUILD STATUS
- **v2a sessions + welcome-back — SHIPPED + live-verified (2026-06-16).** Migration 016
  `mem_sessions`; `/wrap` stores the recap extract_memory already produced; welcome-back greeting
  ("last time we left off on X") on return. **NATURAL LANGUAGE ONLY — no slash commands** (user
  rule [[feedback-no-slash-commands]]): `/wrap` removed; wrap fires on NL guard ("wrap up / gotta
  go / that's all for now…"), welcome-back fires on a greeting ("hi/hey", once per session).
  Telethon PASS: "wrap this up" → recap stored; "hey" → welcome-back line.
- v2a NOTE: a message that creates a task opens a time-prompt flow that intercepts the next
  message (pre-existing) — wrap won't fire mid-flow. Edge case, acceptable.
- **v1 memory spine — SHIPPED + live-verified on the deployed bot (2026-06-16).**
  Migration 015 (`user_facts`+`mem_events`) · `memory_svc.py` (store/dedup/supersede/recall) ·
  `claude_svc.extract_memory()` (session-end, ground-truth+anti-meta+pillars+fact-update) ·
  `/wrap` command · recall plugged into `gather_user_context`/`_context_brief`.
  Telethon PASS: facts stored + pillar-tagged; **fact-update fix worked live** (exam "next week"
  → "the 25th", no stale contradiction; vaping → "quit 3 days ago"); struggle reply recalled
  "showed up 3 days straight" from memory. Session recap (summary+open_threads) returned by /wrap.
- Known wart: "trying to quit X" can linger beside "quit X" (not superseded — not a contradiction,
  just stale). Prompt-tunable later.
- **Next (v2):** idle-gap + daily backstop triggers (scheduler) · `mem_sessions` table + welcome-back
  recap on return · `people` table · addiction `quit_goals`/`relapse_log` + sobriety streak ·
  web tab-close beacon · then port to the new merged app.

## Product North Star (decided 2026-06-16)
**Full-life memory, three DOMINANT pillars: Productivity · Motivation · Addiction-removal.**
General life context captured, but coach weights these three highest.

### Motivation engine = the USP (design deferred — principle only)
> "Motivation is what drives oneself. The goal is to find what motivation sticks to the user
> and increase his productivity."
- So **motivation is first-class, not a pure consumer** — it has memory of *what lever works
  per user* (correction to Q4). Tracks which nudge style → re-engagement, learns + leans into it.
- Seeds already exist: Atlas `motivation_log.reengaged` + `_responds_to()`; Learnix
  "memory-of-what-works" (maintenance pt4). New app makes this the centerpiece.
- DO NOT design the engine yet — user will drive that session. Just keep the hook here.

### Data architecture (decided)
- **Shared memory substrate** (new): `user_facts`, `people`, `mem_events` (typed + sentiment),
  `mem_sessions`. All pillars read it.
- **Productivity** — existing tables (tasks/habits/goals/study). Keep.
- **Addiction-removal** — new `quit_goals` (substance, quit-date, why, sobriety streak) +
  `relapse_log` (ts, trigger, zero-shame note). Wrapped in crisis/no-shame/not-medical guards.
- **Motivation** — first-class "what-works" memory (style → re-engagement), engine reads
  everything. Design later.

## Final design decisions (grill session 2026-06-16)
1. **Write memory at SESSION END only** — one combined call reads the whole transcript →
   pulls facts + events + writes the summary. NOT per-message. **Our optimization over moto**
   (he extracts every turn): within a session the raw chat_history is already in context, so
   per-turn extraction is redundant; the store's job is cross-session memory → end-of-session
   is enough + far cheaper.
2. **Tail never lost** — every message already saved live (chat_history). Session end triggers:
   `/wrap` (explicit) + web **tab-close beacon** (`navigator.sendBeacon`) + **idle-gap** (~2-3h)
   + **daily rollup** backstop. Clean close = beacon saves tail; dirty close = backstop catches it.
3. **Plug into the existing motivation brain** — `gather_user_context` ALSO reads the new
   `user_facts`/`mem_events` (augment, don't replace). Keeps shipped motivation behavior working.
4. **Capture motivation-lever clues from day 1** — tag `mem_events.pillar='motivation'` when the
   bot notices what lifts the user, so the (later) engine has history to learn from. Costs ~nothing.

## Open questions for moto (relay via Discord)
1. Session boundary for a chat app — idle-gap vs daily rollup vs explicit?
2. Is Qdrant worth it for task-structured data, or is structured recall enough?
3. The fact-update gap — does he want the fix upstreamed to exo-cortex?
