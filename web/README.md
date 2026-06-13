# Learnix Web — today

A cute single-user task list (cross-out style) over the existing Learnix bot data.
Same Supabase source of truth as the Telegram bot — no second database.

- **Backend:** FastAPI (`api/main.py`), reuses `bot/tasks/svc.py`. Runs in its own venv
  (`api/.venv`) because the global env's `starlette` is too new for older FastAPI.
- **Frontend:** Vite + React + TypeScript + Tailwind + Motion (`ui/`). Warm-paper aesthetic,
  Fraunces / Quicksand / Caveat fonts, hand-drawn strikethrough on complete.

## Run

```bash
# 1) backend  (port 8000)
cd web/api
.venv/Scripts/python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 2) frontend (port 5173, proxies /api -> 8000)
cd web/ui
npm install   # first time only
npm run dev
```

Open http://localhost:5173

## Config

- `LEARNIX_WEB_UID` — Telegram user id the UI shows tasks for. Defaults to the owner uid.
- Reads `bot/.env` for `SUPABASE_URL` / `SUPABASE_KEY`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/tasks` | `{active, completed}` (subtasks hidden) |
| POST | `/api/tasks` | create `{title}` |
| PATCH | `/api/tasks/{id}` | `{status: active\|completed, title?}` — cross out / restore |
| DELETE | `/api/tasks/{id}` | remove |

Cross-out = `status: "completed"` (the same state the bot uses).
