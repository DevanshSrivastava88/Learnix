"""
Learnix web API — multi-user task layer over the existing bot data.

Reuses bot/tasks/svc.py (Supabase) so there is no second source of truth.
Auth is bot-initiated: the user sends /weblogin to the Telegram bot, which
mints a one-time code tied to their user_id. The web verifies that code and
issues a signed session cookie. All task routes are scoped to the session's
user_id — every user sees only their own tasks.
"""
import hashlib
import hmac
import os
import secrets
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- wire in the existing bot package + its env ------------------------------
_HERE = Path(__file__).resolve().parent


def _bot_candidates():
    cands = []
    env = os.environ.get("LEARNIX_BOT_DIR")
    if env:
        cands.append(Path(env))
    if len(_HERE.parents) >= 2:           # local dev: web/api -> repo/bot
        cands.append(_HERE.parents[1] / "bot")
    cands.append(_HERE / "_bot")          # container fallback
    return cands


BOT_DIR = next((c for c in _bot_candidates() if (c / "tasks" / "svc.py").exists()), None)
if BOT_DIR is None:
    raise RuntimeError("Could not locate bot data layer (tasks/svc.py)")
sys.path.insert(0, str(BOT_DIR))
load_dotenv(BOT_DIR / ".env")  # no-op in prod; Railway injects env vars directly

import tasks.svc as tasks_svc            # noqa: E402  (path set above)
from supabase_svc import get_client      # noqa: E402

# Sessions are signed with this secret. Set SESSION_SECRET in prod so sessions
# survive restarts; a random ephemeral one is used otherwise (logs everyone out
# on restart, but never insecure).
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
SESSION_TTL = 30 * 24 * 3600  # 30 days
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"  # set 0 for local http

app = FastAPI(title="Learnix Tasks")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- session tokens (HMAC-signed, stateless) ---------------------------------

def _make_token(uid: int) -> str:
    exp = int(time.time()) + SESSION_TTL
    body = f"{uid}.{exp}"
    sig = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _read_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        uid_s, exp_s, sig = token.rsplit(".", 2)
    except ValueError:
        return None
    body = f"{uid_s}.{exp_s}"
    expected = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    if int(exp_s) < int(time.time()):
        return None
    return int(uid_s)


def get_current_uid(request: Request) -> int:
    uid = _read_token(request.cookies.get("session"))
    if uid is None:
        raise HTTPException(401, "Not logged in")
    return uid


# --- shaping -----------------------------------------------------------------

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


class LoginCode(BaseModel):
    code: str


# --- auth routes -------------------------------------------------------------

@app.post("/api/auth/verify")
def auth_verify(body: LoginCode, response: Response):
    code = (body.code or "").strip().upper()
    if not code:
        raise HTTPException(400, "Enter the code from Telegram")
    res = get_client().table("web_login_codes").select("*").eq("code", code).limit(1).execute()
    row = res.data[0] if res.data else None
    if not row or row.get("used"):
        raise HTTPException(401, "Invalid or already-used code")
    from datetime import datetime, timezone
    try:
        expired = datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc)
    except Exception:
        expired = True
    if expired:
        raise HTTPException(401, "Code expired — send /weblogin again")
    get_client().table("web_login_codes").update({"used": True}).eq("code", code).execute()
    uid = int(row["user_id"])
    response.set_cookie(
        "session", _make_token(uid),
        httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=SESSION_TTL,
    )
    return {"ok": True, "uid": uid}


@app.get("/api/me")
def me(uid: int = Depends(get_current_uid)):
    return {"uid": uid}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


# --- task routes (scoped to the logged-in user) ------------------------------

@app.get("/api/tasks")
def list_all(uid: int = Depends(get_current_uid)):
    active = _visible(tasks_svc.list_tasks(uid, status="active"))
    completed = _visible(tasks_svc.list_tasks(uid, status="completed"))
    return {"active": active, "completed": completed}


@app.post("/api/tasks")
def add(body: NewTask, uid: int = Depends(get_current_uid)):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "Title is required")
    return _shape(tasks_svc.create_task(uid, title, "task"))


@app.patch("/api/tasks/{task_id}")
def patch(task_id: str, body: TaskPatch, uid: int = Depends(get_current_uid)):
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != uid:
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
def remove(task_id: str, uid: int = Depends(get_current_uid)):
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != uid:
        raise HTTPException(404, "Task not found")
    tasks_svc.delete_task(task_id)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True}


# --- serve the built frontend (single-service deploy) ------------------------
_STATIC_CANDIDATES = [_HERE / "static", _HERE.parents[0] / "ui" / "dist"]
STATIC_DIR = next((c for c in _STATIC_CANDIDATES if (c / "index.html").exists()), None)

if STATIC_DIR is not None:
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def _index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    def _spa(path: str):
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
