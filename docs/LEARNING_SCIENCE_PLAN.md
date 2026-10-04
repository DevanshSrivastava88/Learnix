# Learning Science Plan — ideas from HLD Gym

> Source: moto's `shreyashdubey/hld_gym` (cloned at `D:\Projects\hld_gym`, live https://hld-gym.vercel.app).
> Key reads there: `docs/learning-and-retention.md`, `docs/kernels.md`, `playground/` (voice tutor).
> Captured 2026-10-04. Nothing built yet. Ask moto before reusing his chapters/kernels verbatim.

## Why
Learnix study mode = goal → daily plan → lesson + 1 quiz, weak topics resurface.
HLD Gym's research says what actually makes things stick. Pair with Exocortex memory
(remembers what you got wrong + when) → Learnix decides what to quiz and when.

## Ideas, ranked

| # | Idea | Plain meaning | Learnix today | Value |
|---|---|---|---|---|
| 1 | Retrieval practice | Pulling an answer out of your head beats rereading (Roediger & Karpicke 2006: testers crush rereaders a week later) | Partial — 1 quiz/day | 10/10 |
| 2 | Spaced repetition | Review gaps grow: 1d → 3d → 1w → 1mo. Gap ≈ 10–20% of how long you want to keep it (Cepeda) | No real schedule | 10/10 |
| 3 | Explain it back | User explains like to a 12-year-old; LLM grades + says what's wrong. Feedback is the missing ingredient — fluency feels like knowledge | No | 9/10 |
| 4 | Kernels | One core mechanism per topic that regenerates the rest. Gates: runs forward from blank page, derives 3+ facts, has a named boundary. Learner must *produce* it, not be handed it | No | 8/10 |
| 5 | Draw from memory | Big-picture knowledge is stored spatially; recall via drawing, AI checks | No (hard on Telegram; web app could) | 7/10 |
| 6 | Voice tutor | Speak answers out loud, AI talks back + grades (HLD uses Pipecat + OpenAI; we're Groq-first) | Voice msgs only | 7/10 (cost) |
| 7 | Interleaving | Mix topics in one quiz session instead of blocks | No | 6/10 |
| 8 | Honesty rule | Never claim a feature that isn't built | Habit | 5/10 |

Evidence ranking (Dunlosky 2013): practice testing + distributed practice = HIGH;
interleaving / self-explanation = moderate; rereading, highlighting, summarizing = LOW.
Learning styles don't replicate (Pashler 2008) — don't build around them.

## Skip
Reels, sell page, origins stories — content/marketing, not learning mechanics.

## Suggested build order
1. #1 + #2 together: per-topic review schedule driven by quiz misses (feeds Exocortex memory).
2. #3: free-text "explain it" answer graded by LLM (LLM-first, structured JSON verdict).
3. #7 interleaving once 2+ topics are active.
4. #4/#5/#6 later.
