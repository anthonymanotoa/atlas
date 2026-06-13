"""Atlas dashboard backend — FastAPI serving JSON over localhost from atlas.db.

Single-user, local only. No auth (binds to 127.0.0.1). Serves the built React app
in production; in dev the Vite server proxies here.
Run:  uv run uvicorn dashboard.backend.main:app --port 8787 --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import analytics
from engine.db.models import DB
from engine.normalize import STATES, now_iso
from engine.paths import OUTBOX_DIR, REPO_ROOT

app = FastAPI(title="Atlas", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


class StateBody(BaseModel):
    state: str


class PrepBody(BaseModel):
    language: str = "en"


# ── API ──────────────────────────────────────────────────────────────────────
@app.get("/api/overview")
def api_overview():
    with DB() as db:
        return {"overview": analytics.overview(db), "needs_action": analytics.needs_action(db)}


@app.get("/api/jobs")
def api_jobs(state: str | None = None, limit: int = 500):
    with DB() as db:
        return {"jobs": db.list_jobs(state=state, limit=limit), "states": STATES}


@app.get("/api/board")
def api_board():
    """Jobs grouped by the columns shown on the kanban board."""
    columns = ["shortlisted", "tailored", "ready", "applied", "responded", "interview", "offer"]
    with DB() as db:
        return {"columns": columns,
                "jobs": {c: db.list_jobs(state=c) for c in columns}}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    with DB() as db:
        detail = analytics.job_detail(db, job_id)
    if not detail:
        raise HTTPException(404, "job not found")
    return detail


@app.post("/api/jobs/{job_id}/state")
def api_set_state(job_id: str, body: StateBody):
    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        db.set_state(job_id, body.state, {"via": "dashboard"})
    return {"ok": True, "state": body.state}


@app.post("/api/jobs/{job_id}/applied")
def api_mark_applied(job_id: str):
    with DB() as db:
        db.set_state(job_id, "applied", {"via": "dashboard"})
    return {"ok": True}


@app.post("/api/jobs/{job_id}/prep")
def api_prep(job_id: str, body: PrepBody):
    from engine.cv.build import build_for_job
    from engine.outreach.build import build_outreach, write_package
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        cv = build_for_job(db, job_id, language=body.language)
        build_outreach(db, job_id, language=body.language)
        write_package(db, job_id, language=body.language)
    return {"ok": True, "coverage": cv.coverage, "parse_ok": cv.parse_ok}


@app.post("/api/messages/{message_id}/sent")
def api_mark_sent(message_id: int):
    with DB() as db:
        db.conn.execute("UPDATE messages SET state='sent', sent_at=? WHERE id=?",
                        (now_iso(), message_id))
        db.conn.commit()
    return {"ok": True}


@app.get("/api/brief")
def api_brief():
    path = OUTBOX_DIR / "MORNING_BRIEF.md"
    return {"markdown": path.read_text() if path.exists() else "# Sin resumen todavía\n\nEjecuta `atlas brain`."}


@app.get("/api/cv/{job_id}/{version_id}/download")
def api_cv_download(job_id: str, version_id: int, fmt: str = "docx"):
    with DB() as db:
        version = next((v for v in db.cv_versions_for(job_id) if v["id"] == version_id), None)
    if not version:
        raise HTTPException(404, "cv version not found")
    path = version.get("path_pdf") if fmt == "pdf" else version.get("path_docx")
    if not path or not Path(path).exists():
        raise HTTPException(404, f"{fmt} file not available")
    p = Path(path)
    media = ("application/pdf" if fmt == "pdf"
             else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return FileResponse(str(p), filename=p.name, media_type=media)


@app.get("/api/health")
def health():
    return {"ok": True}


# ── Serve the built frontend (if present) ────────────────────────────────────
# Mounted LAST so it never shadows the /api/* routes.
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
