# Glass Focus Timer — design (Phase 1)

_Approved 2026-06-15. Shipped commit 01831d3d._

## Goal
An ADHD-friendly focus timer on the web app, glass UI over a dreamy lavender-cat
background. Phase 1 = timer only; calendar drag-drop reschedule is Phase 2.

## Flow
- Header **"FIX ADHD"** toggle (persisted in localStorage). OFF = normal list.
  ON = a **▶** on every active task.
- Tap ▶ → fullscreen liquid-glass timer over `/focus-bg.png` (the cat) for that task.
  1. **Welcome moment** ("You made it here. That's the hard part.") + optional
     duration (15/25/45 presets or free input).
  2. Duration set → **countdown**, chime at end. None → **count up**, chimes at 30 & 60 min.
  3. Big glass ring (drains on countdown), task title, MM:SS center.
- Controls: **Pause/Resume**, **✓ Done** → marks task completed (existing
  `PATCH /api/tasks/{id}` → completed), closes, chime.
- **Back-guard**: Esc / browser-back / ← → modal "Going back will cost your focus"
  → Return to timer / Exit task (exit = abandon, nothing logged, task stays).

## Constraints
- 100% client-side. No new backend, no new table. Only server touch = mark completed.
- Chimes via Web Audio (generated tone, no asset).
- Glass = `.glass` CSS util (backdrop-blur + translucency).

## Out of scope (Phase 2)
- MS-Teams-style day timeline with drag-drop reschedule of scheduled + unscheduled tasks.
- Persisted focus-session stats (FOCUSFLOW-style stats screen).

## Verification
Live Playwright on the deployed app: toggle → ▶ → welcome → 25m countdown ring →
back-guard modal → Done marks Feed Cat completed + closes. All passed.
