"""
Learnix web API — thin single-user task layer over the existing bot data.

Reuses bot/tasks/svc.py (Supabase) so there is no second source of truth.
Single user for now: LEARNIX_WEB_UID (defaults to the known owner uid).
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- wire in the existing bot package + its env ------------------------------
# Local dev: bot/ lives two levels up. Container: a trimmed copy is vendored at
# api/_bot. Override with LEARNIX_BOT_DIR if needed.
_HERE = Path(__file__).resolve().parent
_BOT_CANDIDATES = [
    Path(os.environ["LEARNIX_BOT_DIR"]) if os.environ.get("LEARNIX_BOT_DIR") else None,
    _HERE.parents[1] / "bot",
    _HERE / "_bot",
]
BOT_DIR = next((c for c in _BOT_CANDIDATES if c and (c / "tasks" / "svc.py").exists()), None)
if BOT_DIR is None:
    raise RuntimeError("Could not locate bot data layer (tasks/svc.py)")
sys.path.insert(0, str(BOT_DIR))
load_dotenv(BOT_DIR / ".env")  # no-op in prod; Railway injects env vars directly

import tasks.svc as tasks_svc  # noqa: E402  (path set above)

UID = int(os.environ.get("LEARNIX_WEB_UID", "584321397"))

app = FastAPI(title="Learnix Tasks")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_subtask(title: str) -> bool:
    return " — Step " in (title or "")


def _shape(t: dict) -> dict:
    return {
        "id": t["id"],
        "title": t.get("title", ""),
        "status": t.get("status", "active"),
        "type": t.get("task_type", "task"),
        "created_at": t.get("created_at"),
    }


def _visible(rows: list) -> list:
    return [_shape(t) for t in rows if not _is_subtask(t.get("title", ""))]


# --- models ------------------------------------------------------------------

class NewTask(BaseModel):
    title: str


class TaskPatch(BaseModel):
    status: str | None = None
    title: str | None = None


# --- routes ------------------------------------------------------------------

@app.get("/api/tasks")
def list_all():
    active = _visible(tasks_svc.list_tasks(UID, status="active"))
    completed = _visible(tasks_svc.list_tasks(UID, status="completed"))
    return {"active": active, "completed": completed}


@app.post("/api/tasks")
def add(body: NewTask):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "Title is required")
    row = tasks_svc.create_task(UID, title, "task")
    return _shape(row)


@app.patch("/api/tasks/{task_id}")
def patch(task_id: str, body: TaskPatch):
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != UID:
        raise HTTPException(404, "Task not found")
    fields = {}
    if body.status in ("active", "completed"):
        fields["status"] = body.status
    if body.title is not None and body.title.strip():
        fields["title"] = body.title.strip()
    if not fields:
        raise HTTPException(400, "Nothing to update")
    tasks_svc.update_task(task_id, **fields)
    return _shape({**task, **fields})


@app.delete("/api/tasks/{task_id}")
def remove(task_id: str):
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != UID:
        raise HTTPException(404, "Task not found")
    tasks_svc.delete_task(task_id)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True, "uid": UID}


# --- serve the built frontend (single-service deploy) ------------------------
# Container: dist copied to api/static. Local: fall back to ui/dist if built.
_STATIC_CANDIDATES = [_HERE / "static", _HERE.parents[0] / "ui" / "dist"]
STATIC_DIR = next((c for c in _STATIC_CANDIDATES if (c / "index.html").exists()), None)

if STATIC_DIR is not None:
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def _index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    def _spa(path: str):
        # serve real files if they exist, otherwise fall back to the SPA shell
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
