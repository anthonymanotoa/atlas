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
# anyway. The threat is CSRF: a remote page (evil.com) tricking the browser into POSTing
# to 127.0.0.1. The browser stamps such a request with evil.com's Origin — it CANNOT forge
# a loopback Origin — so we accept any loopback origin (127.0.0.1 / localhost / [::1] on ANY
# port: Atlas may be served from any port the user picks) and reject everything else. Extra
# explicit origins can still be allow-listed via ATLAS_ALLOWED_ORIGINS (comma-list).
_LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1", "[::1]"))
ALLOWED_ORIGINS = frozenset(
    o.strip() for o in os.environ.get("ATLAS_ALLOWED_ORIGINS", "").split(",") if o.strip()
)


def _is_loopback_origin(origin: str) -> bool:
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and (parts.hostname or "") in _LOOPBACK_HOSTS


def require_trusted_origin(request: Request) -> None:
    """Reject state-mutating requests from an untrusted browser origin (403).

    Same-origin and non-browser requests omit Origin and are allowed (this is
    load-bearing for production "served-from-FastAPI" mode); a present Origin/Referer must be
    a loopback host (any port) or an explicitly allow-listed origin.
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
    if _is_loopback_origin(origin) or origin in ALLOWED_ORIGINS:
        return
    raise HTTPException(403, "origin not allowed")


class StateBody(BaseModel):
    state: str


class PrepBody(BaseModel):
    # constrained: never reaches the CV output path as a raw string.
    # None → auto-pick from the posting's detected language (create it in the offer's language).
    language: Literal["en", "es"] | None = None


class ProfileBody(BaseModel):
    id: str


class LabelBody(BaseModel):
    label: str


class SettingBody(BaseModel):
    key: str
    value: str


class OutcomeBody(BaseModel):
    final_state: str  # rejected | responded | interviewed | offer | ghosted
    response_days: int | None = None
    interview_count: int = 0
    offer_made: bool = False
    recruiter_source: str | None = None
    reason: str | None = None
    notes: str | None = None


class FeedbackBody(BaseModel):
    feedback_type: str  # agree | disagree
    reasoning: str = ""


class InterviewBody(BaseModel):
    scheduled_at: str | None = None
    round: str | None = None
    mode: str | None = None
    notes: str | None = None


class InterviewerBody(BaseModel):
    name: str
    title: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    research_notes: str | None = None


class PrepLangBody(BaseModel):
    language: Literal["en", "es"] = "en"


class PortfolioBody(BaseModel):
    include_github: bool = False


class PeerBody(BaseModel):
    peer_name: str
    role_match: str | None = None
    peer_profile_url: str | None = None
    peer_portfolio_url: str | None = None
    key_strengths: list[str] | None = None
    how_to_emulate: list[str] | None = None
    source_url: str | None = None
    notes: str | None = None


class SocialMentionBody(BaseModel):
    platform: str = "linkedin"
    source_url: str | None = None
    recruiter_name: str | None = None
    recruiter_linkedin: str | None = None
    recruiter_email: str | None = None
    post_title: str | None = None
    post_excerpt: str | None = None
    context_type: str | None = None


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
    # Filter BEFORE applying the limit, so a salary/language/freshness filter can't
    # silently under-report by capping rows first.
    jobs = [analytics.annotate(j) for j in db.list_jobs(state=state)]
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
    return {"jobs": jobs[:limit], "states": STATES}


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


def _run_discover_and_score(only: set[str] | None, profile_id: str | None) -> None:
    global _discovering
    try:
        from engine.config import load_criteria
        from engine.discovery.runner import discover as run_discover
        from engine.scoring.run import score_jobs

        # Re-pin the profile captured at enqueue time so a concurrent dashboard switch
        # can't make this run land in another profile's DB/criteria.
        if profile_id is not None:
            paths.set_profile(profile_id)
        with DB() as db:  # own connection — see note above
            run_discover(db, only=only)
            # rescore=True so a "Buscar" also re-evaluates already discovered/scored/
            # shortlisted jobs with the current scorer (e.g. after a criteria change) —
            # never regressing a job already tailored/applied. Keeps the shortlist honest.
            score_jobs(db, load_criteria(), rescore=True)
    except Exception as e:  # noqa: BLE001 — record the failure instead of dropping it silently
        try:
            with DB() as db:
                db.log_event(None, "error", {"stage": "discover_bg", "error": str(e)[:200]})
        except Exception:  # noqa: BLE001
            pass
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
    background.add_task(_run_discover_and_score, only_set, paths.PROFILE_ID)
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
    from engine.config import load_master_cv
    from engine.cv.naming import cv_filename

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
    # Company/role-aware filename so the user can tell which CV is for which company.
    job = db.get_job(job_id) or {}
    cv_name = (load_master_cv().get("basics") or {}).get("name")
    nice = cv_filename(
        cv_name, job.get("company"), job.get("title"), version.get("language") or "en", fmt
    )
    return FileResponse(str(p), filename=nice, media_type=media)


@app.get("/api/cv/library")
def api_cv_library():
    """The per-profile folder where every tailored CV is saved (so the user can browse them
    all in Finder), plus a listing of what's there. Read-only; download stays per-version."""
    from engine.cv.naming import library_dir

    d = library_dir()
    files = sorted(
        (
            {"name": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
            for f in d.glob("*")
            if f.is_file()
        ),
        key=lambda x: x["modified"],
        reverse=True,
    )
    return {"dir": str(d), "count": len(files), "files": files}


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


# ── Self-improving learning (P2-D): human-confirmed outcomes → per-company learnings ──
@app.post("/api/jobs/{job_id}/outcome", dependencies=[Depends(require_trusted_origin)])
def api_record_outcome(job_id: str, body: OutcomeBody, db: DB = Depends(get_db)):
    from engine.learning.runner import auto_learn

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    company = job.get("company", "")
    db.record_outcome(
        job_id,
        company,
        final_state=body.final_state,
        response_days=body.response_days,
        interview_count=body.interview_count,
        offer_made=body.offer_made or body.final_state == "offer",
        recruiter_source=body.recruiter_source,
        reason=body.reason,
        notes=body.notes,
    )
    auto_learn(db, company)
    return {"ok": True, "learnings": db.learnings_for_company(company)}


@app.get("/api/learnings")
def api_learnings(company: str | None = None, db: DB = Depends(get_db)):
    return {"learnings": db.learnings_for_company(company) if company else db.all_learnings()}


@app.post("/api/learnings/{learning_id}/feedback", dependencies=[Depends(require_trusted_origin)])
def api_learning_feedback(learning_id: int, body: FeedbackBody, db: DB = Depends(get_db)):
    # Guard the FK: a stale/unknown id would otherwise raise an IntegrityError → 500.
    if not db.conn.execute("SELECT 1 FROM learnings WHERE id=?", (learning_id,)).fetchone():
        raise HTTPException(404, "learning not found")
    db.record_learning_feedback(
        learning_id, feedback_type=body.feedback_type, reasoning=body.reasoning
    )
    return {"ok": True}


# ── Portfolio + peers (P3-F): local generation, never auto-published ──────────
@app.get("/api/portfolio/latest")
def api_portfolio_latest(db: DB = Depends(get_db)):
    return {"portfolio": db.latest_portfolio()}


@app.post("/api/portfolio/generate", dependencies=[Depends(require_trusted_origin)])
def api_portfolio_generate(body: PortfolioBody):
    """Generate the portfolio. NOT under get_db: with --github this makes a ~15s network
    call, and holding the global _DB_LOCK that long would freeze every other request. We
    build first (no lock), then persist via a short-lived own connection (WAL-safe)."""
    from datetime import UTC, datetime

    from engine.config import load_master_cv
    from engine.portfolio.builder import generate_portfolio

    version = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    path = generate_portfolio(load_master_cv(), version=version, include_github=body.include_github)
    with DB() as db:  # own connection — does not hold the shared API lock
        pid = db.add_portfolio(version=version, path_html=str(path))
    return {"ok": True, "id": pid, "version": version, "path": str(path)}


@app.get("/api/portfolio/{portfolio_id}/preview")
def api_portfolio_preview(portfolio_id: int, db: DB = Depends(get_db)):
    row = next((p for p in db.list_portfolios() if p["id"] == portfolio_id), None)
    if not row or not row.get("path_html"):
        raise HTTPException(404, "portfolio not found")
    p = Path(row["path_html"]).resolve()
    # Confine to the outbox: never serve a file outside data/outbox, whatever the row says.
    if not p.is_relative_to(paths.OUTBOX_DIR.resolve()) or not p.exists():
        raise HTTPException(404, "portfolio file not available")
    return FileResponse(str(p), media_type="text/html")


@app.get("/api/portfolio/research")
def api_portfolio_research():
    """Curated, verified reference portfolios + the patterns behind them + a detailed,
    personalized LLM prompt (built from the user's CV) to commission their own portfolio.
    Everything the user needs to review the examples and brief an LLM, in one place."""
    from engine.config import load_master_cv
    from engine.portfolio.peer_examples import PEER_EXAMPLES, PORTFOLIO_PATTERNS
    from engine.portfolio.prompt import build_portfolio_prompt

    return {
        "examples": PEER_EXAMPLES,
        "patterns": PORTFOLIO_PATTERNS,
        "prompt": build_portfolio_prompt(load_master_cv()),
    }


@app.get("/api/peers")
def api_peers(db: DB = Depends(get_db)):
    return {"peers": db.list_peer_portfolios()}


@app.post("/api/peers", dependencies=[Depends(require_trusted_origin)])
def api_add_peer(body: PeerBody, db: DB = Depends(get_db)):
    pid = db.add_peer_portfolio(**body.model_dump())
    return {"ok": True, "id": pid}


# ── Interview prep (P3-E): manual entry + deterministic prep-doc generation ───
@app.get("/api/jobs/{job_id}/interviews")
def api_interviews_for_job(job_id: str, db: DB = Depends(get_db)):
    out = []
    for iv in db.interviews_for_job(job_id):
        iv["interviewers"] = db.interviewers_for(iv["id"])
        out.append(iv)
    return {"interviews": out}


@app.post("/api/jobs/{job_id}/interview", dependencies=[Depends(require_trusted_origin)])
def api_add_interview(job_id: str, body: InterviewBody, db: DB = Depends(get_db)):
    if not db.get_job(job_id):
        raise HTTPException(404, "job not found")
    iid = db.add_interview(
        job_id, scheduled_at=body.scheduled_at, round=body.round, mode=body.mode, notes=body.notes
    )
    return {"ok": True, "id": iid}


@app.post(
    "/api/interview/{interview_id}/interviewer", dependencies=[Depends(require_trusted_origin)]
)
def api_add_interviewer(interview_id: int, body: InterviewerBody, db: DB = Depends(get_db)):
    if not db.get_interview(interview_id):
        raise HTTPException(404, "interview not found")
    iid = db.add_interviewer(interview_id, **body.model_dump())
    return {"ok": True, "id": iid}


@app.post("/api/interview/{interview_id}/prep", dependencies=[Depends(require_trusted_origin)])
def api_interview_prep(interview_id: int, body: PrepLangBody, db: DB = Depends(get_db)):
    from engine.interview.interview_prep import gen_prep_doc

    if not db.get_interview(interview_id):
        raise HTTPException(404, "interview not found")
    path = gen_prep_doc(db, interview_id, language=body.language)
    return {"ok": True, "path": str(path), "markdown": path.read_text()}


# ── Social signal (P2-C): supervised LinkedIn/X lookup — never auto-contacts ──
@app.get("/api/jobs/{job_id}/social_mentions")
def api_social_mentions(job_id: str, db: DB = Depends(get_db)):
    return {"mentions": db.social_mentions_for(job_id)}


@app.post("/api/jobs/{job_id}/start-social-search", dependencies=[Depends(require_trusted_origin)])
def api_start_social_search(job_id: str, db: DB = Depends(get_db)):
    """Queue a (human-run) social search and return ready-to-paste queries for Chrome."""
    from engine.social import search

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    search.queue_search(db, job_id, job.get("company", ""), job.get("title", ""))
    return {
        "ok": True,
        "queries": search.search_queries(job.get("company", ""), job.get("title", "")),
    }


@app.post("/api/jobs/{job_id}/social_mentions", dependencies=[Depends(require_trusted_origin)])
def api_add_social_mention(job_id: str, body: SocialMentionBody, db: DB = Depends(get_db)):
    """Save a mention the human confirmed in the supervised Chrome session."""
    from engine.social import search

    if not db.get_job(job_id):
        raise HTTPException(404, "job not found")
    mid = db.add_social_mention(job_id, **body.model_dump())
    search.clear_search(db, job_id)
    return {"ok": True, "id": mid}


@app.get("/api/pending-searches")
def api_pending_searches(db: DB = Depends(get_db)):
    from engine.social import search

    return {"pending": search.pending_searches(db)}


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


@app.get("/api/cv/audit")
def api_cv_audit(db: DB = Depends(get_db)):
    """CV audit (score + recommendations) for the active profile, available any time —
    not just during onboarding. Same deterministic `atlas advise` engine, re-read live so
    editing master_cv.yaml + reopening reflects instantly."""
    from engine.advisor import audit_dict
    from engine.config import load_master_cv

    cv = load_master_cv()
    return {"cv_present": bool(cv), "audit": audit_dict(cv)}


# ── Profiles (selector, no password — profile *selection* on a trusted local box) ─────
@app.get("/api/profiles")
def api_profiles():
    # Self-heal placeholder labels (e.g. the legacy "Dueño") to the real CV name on read.
    profiles.reconcile_labels()
    return {"profiles": profiles.list_profiles(), "active": paths.PROFILE_ID or profiles.OWNER_ID}


@app.post("/api/profiles/{profile_id}/label", dependencies=[Depends(require_trusted_origin)])
def api_rename_profile(profile_id: str, body: LabelBody):
    """Rename a profile's display label (the name shown in the selector)."""
    if not profiles.valid_id(profile_id) or not profiles.exists(profile_id):
        raise HTTPException(404, "unknown profile")
    try:
        label = profiles.set_label(profile_id, body.label)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True, "id": profile_id, "label": label}


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
