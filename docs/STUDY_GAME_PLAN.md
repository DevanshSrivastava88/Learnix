# Study Game Plan — Learnix x Exocortex x HLD Gym (2026-10-15)

Goal: Learnix ("learnings") = the coach that makes devansh study. Exocortex = the brain that
remembers what he knows, what he missed, and when to review. HLD Gym = the science + content.

## Who does what
| Piece | Job |
|---|---|
| Exocortex (`excortex.duckdns.org`, MCP: list_topics/get_notes/add_notes/record_review) | Source of truth: topics, notes, weak spots, review schedule |
| Learnix bot + web | Daily nudge, quiz/recall session, grading, streaks/motivation |
| HLD Gym (`D:\Projects\hld_gym`, write access since 2026-10-15) | Learning science (`docs/learning-and-retention.md`, `docs/kernels.md`) + system-design chapters/quizzes (ask moto before reusing verbatim) |

## REALITY CHECK (found at /ttyl, 2026-10-15) — read before building
- Exocortex ALREADY has a /learn page (2026-10-06, @3b07e2d): add topic → TEACH ME → QUIZ ME → LLM grade 0-5
  → review ladder 1/3/7/14/30/60d, misses aimed at gaps. Plus exo-mcp (list_topics/get_notes/record_review).
- So Phases 1-3 below are half-built INSIDE Exocortex, and log.txt says Learnix is being folded into Exocortex.
- Decision for devansh: build study in Exocortex /learn (likely) vs keep Learnix bot as the nudge channel only.

## Phases
0. **Unblock** — merge `admin-bypass` → master; check bot + web alive on Railway; read Exocortex API (does it expose REST, or only MCP?).
1. **Wire** — Learnix reads due topics from Exocortex, writes every grade back via record_review. No duplicate schedule in Learnix.
2. **Recall session** (plan #1+#2) — daily "due today" push → question with NO notes shown → he answers → LLM grades (structured JSON) → record_review. Misses become weak spots.
3. **Explain it back** (#3) — free text or voice note, LLM grades vs his notes, says exactly what's missing.
4. **HLD content** — after moto OKs: import HLD Gym chapters as Exocortex topics (quiz.json/cards.json → notes + questions). First real study subject = system design.
5. **Later** — interleaving (#7), kernels (#4), draw-from-memory on web (#5), voice tutor (#6).

## Open questions (ask before building)
- Main study surface: Telegram bot, web app, or Exocortex app itself?
- What subjects first — system design (HLD), QA_and_ai_study goal, or both?
- moto: OK to reuse hld_gym chapters/quizzes inside Learnix/Exocortex?
