"""Atlas dashboard backend — FastAPI serving JSON over localhost from atlas.db.

Single-user, local only. No auth (binds to 127.0.0.1). Serves the built React app
in production; in dev the Vite server proxies here.
Run:  uv run uvicorn dashboard.backend.main:app --port 8787 --reload
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Literal
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import engine.paths as paths
from engine import analytics, profiles
from engine.db.models import DB
from engine.normalize import STATES, now_iso
from engine.paths import REPO_ROOT

# ── Shared SQLite connection (plan 014) ───────────────────────────────────────
# Threading decision — approach A: one shared connection + a module lock.
# uvicorn runs these sync handlers on an anyio worker thread pool, so a single
# sqlite3.Connection with the default check_same_thread=True would raise
# "SQLite objects created in a thread can only be used in that same thread" the
# instant a second worker thread touched it. We open ONE long-lived connection
# (check_same_thread=False) and serialize every API DB operation behind _DB_LOCK.
# Sound here because this is a single-user localhost app: WAL + a single writer is
# ample, and init_schema() now runs ONCE at startup instead of once per request.
_DB: DB | None = None
_DB_LOCK = Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _DB
    _DB = DB(check_same_thread=False)  # connect + PRAGMAs + init_schema() — exactly once
    try:
        yield
    finally:
        if _DB is not None:
            _DB.close()
            _DB = None


def get_db():
    """Yield the process-wide DB, serialized so sync handlers never race the connection."""
    with _DB_LOCK:
        yield _DB


app = FastAPI(title="Atlas", docs_url="/api/docs", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Server-side request-authenticity check on state-mutating POSTs (plan 020) ──
# Localhost-only, single-user, no auth. The CORS preflight + loopback bind are the
# first line; this is the server-side backstop for when a request reaches a handler
# anyway. Origins permitted to mutate state; config-driven so it tracks the bound
# host/port (set ATLAS_ALLOWED_ORIGINS as a comma-list to override). Defaults cover
# the loopback backend (documented --port 8787) + the Vite dev server.
_DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:8787",
    "http://localhost:8787",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
ALLOWED_ORIGINS = frozenset(
    o.strip()
    for o in os.environ.get("ATLAS_ALLOWED_ORIGINS", ",".join(_DEFAULT_ALLOWED_ORIGINS)).split(",")
    if o.strip()
)


def require_trusted_origin(request: Request) -> None:
    """Reject state-mutating requests from an untrusted browser origin (403).

    Same-origin and non-browser requests omit Origin and are allowed (this is
    load-bearing for production "served-from-FastAPI" mode); a present
    Origin/Referer must be in ALLOWED_ORIGINS.
    """
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer is None:
            return  # same-origin / non-browser request: nothing to verify
        parts = urlsplit(referer)
        origin = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None
        if origin is None:
            return
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(403, "origin not allowed")


class StateBody(BaseModel):
    state: str


class PrepBody(BaseModel):
    # constrained: never reaches the CV output path as a raw string.
    # None → auto-pick from the posting's detected language (create it in the offer's language).
    language: Literal["en", "es"] | None = None


class ProfileBody(BaseModel):
    id: str


class SettingBody(BaseModel):
    key: str
    value: str


# ── API ──────────────────────────────────────────────────────────────────────
@app.get("/api/overview")
def api_overview(db: DB = Depends(get_db)):
    return {"overview": analytics.overview(db), "needs_action": analytics.needs_action(db)}


@app.get("/api/jobs")
def api_jobs(
    state: str | None = None,
    limit: int = 500,
    min_freshness_days: int | None = None,
    has_salary: bool = False,
    language: str | None = None,
    db: DB = Depends(get_db),
):
    """Job list with the P1-A quality filters (freshness / salary-disclosed / language)."""
    jobs = [analytics.annotate(j) for j in db.list_jobs(state=state, limit=limit)]
    if has_salary:
        jobs = [j for j in jobs if j["salary_visible"]]
    if language:
        jobs = [j for j in jobs if (j.get("language") or "") == language]
    if min_freshness_days is not None:
        # keep fresh-enough postings; never hide jobs whose age is unknown
        jobs = [
            j
            for j in jobs
            if j.get("posted_days") is None or j["posted_days"] <= min_freshness_days
        ]
    return {"jobs": jobs, "states": STATES}


@app.get("/api/board")
def api_board(db: DB = Depends(get_db)):
    """Jobs grouped by the columns shown on the kanban board."""
    columns = ["shortlisted", "tailored", "ready", "applied", "responded", "interview", "offer"]
    rows = db.list_jobs(states=columns)  # one query; preserves fit_score/discovered_at ordering
    grouped: dict[str, list] = {c: [] for c in columns}
    for j in rows:
        grouped[j["state"]].append(analytics.annotate(j))
    return {"columns": columns, "jobs": grouped}


@app.get("/api/filters")
def api_filters(db: DB = Depends(get_db)):
    """Filter options for the board/list UI (freshness presets + languages actually present)."""
    langs = [
        r["language"]
        for r in db.conn.execute(
            "SELECT DISTINCT language FROM jobs WHERE language IS NOT NULL ORDER BY language"
        ).fetchall()
    ]
    return {"freshness_days": [14, 30, 60, 90], "languages": langs}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str, db: DB = Depends(get_db)):
    detail = analytics.job_detail(db, job_id)
    if not detail:
        raise HTTPException(404, "job not found")
    return detail


@app.post("/api/jobs/{job_id}/state", dependencies=[Depends(require_trusted_origin)])
def api_set_state(job_id: str, body: StateBody, db: DB = Depends(get_db)):
    from engine.outreach import followups

    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    if not db.get_job(job_id):
        raise HTTPException(404, "job not found")
    db.set_state(job_id, body.state, {"via": "dashboard"})
    # Drive the reply-aware cadence off the same transitions the user makes on the board.
    if body.state == "applied":
        followups.schedule(db, job_id, channel="email")
    elif body.state == "responded":
        followups.register_reply(db, job_id)  # cancel pending touches — never pester after a reply
    return {"ok": True, "state": body.state}


@app.post("/api/jobs/{job_id}/applied", dependencies=[Depends(require_trusted_origin)])
def api_mark_applied(job_id: str, db: DB = Depends(get_db)):
    from engine.outreach import followups

    db.set_state(job_id, "applied", {"via": "dashboard"})
    followups.schedule(db, job_id, channel="email")  # start the Day 3/7/14 + breakup cadence
    return {"ok": True}


@app.post("/api/jobs/{job_id}/prep", dependencies=[Depends(require_trusted_origin)])
def api_prep(job_id: str, body: PrepBody, db: DB = Depends(get_db)):
    from engine.cv.build import build_for_job
    from engine.outreach.build import build_outreach, write_package

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    # Create the application in the posting's language (es if the offer is in Spanish, else en).
    language = body.language or ("es" if job.get("language") == "es" else "en")
    cv = build_for_job(db, job_id, language=language)
    build_outreach(db, job_id, language=language)
    write_package(db, job_id, language=language)
    return {"ok": True, "coverage": cv.coverage, "parse_ok": cv.parse_ok, "language": language}


@app.post("/api/messages/{message_id}/sent", dependencies=[Depends(require_trusted_origin)])
def api_mark_sent(message_id: int, db: DB = Depends(get_db)):
    db.conn.execute(
        "UPDATE messages SET state='sent', sent_at=? WHERE id=?", (now_iso(), message_id)
    )
    db.conn.commit()
    return {"ok": True}


# ── On-demand discover + score (plan 019) ─────────────────────────────────────
# Lets the cockpit pull fresh jobs between scheduled brain runs. Progress model:
# fire-and-forget + poll (the SPA polls /api/discover/status). The run is
# deterministic and keyless (engine.discovery.runner + engine.scoring.run — no LLM,
# no SDK, no API key), so this stays within the $0 invariant. The background task
# opens its OWN short-lived `with DB()` connection (NOT the shared one from
# get_db): a ~45s/source run must not hold the API lock and block the SPA's polls.
# WAL handles the background writer + the shared reader concurrently.
_DISCOVER_LOCK = Lock()
_discovering = False


def _run_discover_and_score(only: set[str] | None) -> None:
    global _discovering
    try:
        from engine.config import load_criteria
        from engine.discovery.runner import discover as run_discover
        from engine.scoring.run import score_jobs

        with DB() as db:  # own connection — see note above
            run_discover(db, only=only)
            score_jobs(db, load_criteria())
    finally:
        with _DISCOVER_LOCK:
            _discovering = False


@app.post("/api/discover", dependencies=[Depends(require_trusted_origin)])
def api_discover(background: BackgroundTasks, only: str | None = None):
    """Kick off a deterministic discover→score run in the background (202-style)."""
    global _discovering
    with _DISCOVER_LOCK:
        if _discovering:
            return {"started": False, "running": True}  # one run at a time
        _discovering = True
    only_set = {s.strip() for s in only.split(",")} if only else None
    background.add_task(_run_discover_and_score, only_set)
    return {"started": True}


@app.get("/api/discover/status")
def api_discover_status():
    with _DISCOVER_LOCK:
        return {"running": _discovering}


@app.get("/api/brief")
def api_brief():
    path = paths.OUTBOX_DIR / "MORNING_BRIEF.md"
    return {
        "markdown": path.read_text()
        if path.exists()
        else "# Sin resumen todavía\n\nEjecuta `atlas brain`."
    }


@app.get("/api/cv/{job_id}/{version_id}/download")
def api_cv_download(job_id: str, version_id: int, fmt: str = "docx", db: DB = Depends(get_db)):
    version = next((v for v in db.cv_versions_for(job_id) if v["id"] == version_id), None)
    if not version:
        raise HTTPException(404, "cv version not found")
    path = version.get("path_pdf") if fmt == "pdf" else version.get("path_docx")
    if not path:
        raise HTTPException(404, f"{fmt} file not available")
    p = Path(path).resolve()
    # Confine downloads to the outbox: never serve a file outside data/outbox, whatever the DB row says.
    if not p.is_relative_to(paths.OUTBOX_DIR.resolve()) or not p.exists():
        raise HTTPException(404, f"{fmt} file not available")
    media = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(str(p), filename=p.name, media_type=media)


@app.get("/api/health")
def health():
    return {"ok": True}


# ── Settings + CSV export (P1-B) ──────────────────────────────────────────────
# Per-profile, stored in the profile's own `meta` KV table (no schema change).
ALLOWED_SETTINGS = {"download_dir", "csv_columns"}


@app.get("/api/settings")
def api_settings(db: DB = Depends(get_db)):
    return {k: db.meta_get(k) for k in ALLOWED_SETTINGS}


@app.post("/api/settings", dependencies=[Depends(require_trusted_origin)])
def api_set_setting(body: SettingBody, db: DB = Depends(get_db)):
    if body.key not in ALLOWED_SETTINGS:
        raise HTTPException(400, "unknown setting")
    value = body.value
    if body.key == "download_dir" and value:
        from engine.export import validate_download_dir

        try:
            value = validate_download_dir(value)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
    db.meta_set(body.key, value)
    return {"ok": True, "key": body.key, "value": value}


@app.get("/api/csv/columns")
def api_csv_columns(db: DB = Depends(get_db)):
    from engine import export

    return {
        "available": export.available_columns(),
        "selected": export.resolve_columns(None, db.meta_get("csv_columns")),
    }


@app.get("/api/export")
def api_export(columns: str | None = None, state: str | None = None, db: DB = Depends(get_db)):
    """Stream the job list as a CSV attachment; the browser saves it where the user picks.

    `columns` (comma list) overrides the saved/default template for this one export.
    """
    from engine import export

    requested = [c.strip() for c in columns.split(",") if c.strip()] if columns else None
    cols = export.resolve_columns(requested, db.meta_get("csv_columns"))
    jobs = db.list_jobs(state=state, limit=5000)
    text = export.generate_csv(jobs, cols)
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="atlas_jobs.csv"'},
    )


# ── Onboarding (P1-G): first adapt the CV + LinkedIn, then start ──────────────
# Per-profile flag in the profile's own `meta` KV. The gate is a workflow guide (the
# frontend hides the board until it's done), not a security lock — this is a local,
# single-user, passwordless app, so a hard per-route 403 would only add coupling.
@app.get("/api/onboarding")
def api_onboarding(db: DB = Depends(get_db)):
    from engine.advisor import audit_dict
    from engine.config import load_master_cv

    cv = load_master_cv()
    return {
        "complete": db.meta_get("onboarding_complete") == "1",
        "profile": paths.PROFILE_ID or profiles.OWNER_ID,
        "cv_present": bool(cv),
        "audit": audit_dict(cv),
    }


@app.post("/api/onboarding/complete", dependencies=[Depends(require_trusted_origin)])
def api_onboarding_complete(db: DB = Depends(get_db)):
    db.meta_set("onboarding_complete", "1")
    return {"ok": True}


# ── Profiles (selector, no password — profile *selection* on a trusted local box) ─────
@app.get("/api/profiles")
def api_profiles():
    return {"profiles": profiles.list_profiles(), "active": paths.PROFILE_ID or profiles.OWNER_ID}


@app.post("/api/profile", dependencies=[Depends(require_trusted_origin)])
def api_switch_profile(body: ProfileBody):
    """Switch the active profile and reopen the shared DB against its database.

    The backend holds ONE long-lived connection (plan 014), so a profile switch must
    re-point the path globals AND reopen that connection on the new profile's atlas.db.
    """
    global _DB
    if not profiles.valid_id(body.id):
        raise HTTPException(400, "invalid profile id")
    if not profiles.exists(body.id):
        raise HTTPException(404, "unknown profile")
    profiles.set_active(body.id)  # persist registry.json "active"
    paths.set_profile(body.id)  # re-point the path globals
    with _DB_LOCK:  # reopen the shared connection on the new profile's DB
        if _DB is not None:
            _DB.close()
        _DB = DB(check_same_thread=False)
    return {"ok": True, "active": body.id}


# ── Serve the built frontend (if present) ────────────────────────────────────
# Mounted LAST so it never shadows the /api/* routes.
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
