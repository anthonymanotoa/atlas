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

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import engine.paths as paths
from engine import analytics, intents, profiles
from engine.db.models import DB
from engine.discovery import reverse
from engine.discovery.registry import resolve_ats
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


class CriteriaBody(BaseModel):
    criteria: dict
    prose: str = ""


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
    language: Literal["en", "es"] | None = None  # None → the profile's own language


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


# ── Intents (F4 §7.1): la web encola trabajo LLM; el brain lo drena — nunca la web ──
class IntentBody(BaseModel):
    type: str
    job_id: str | None = None
    payload: dict = {}


class CvReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "es"] | None = None


class LegitimacyBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_ids: list[str] = Field(min_length=1, max_length=100)


class UpskillPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    states: list[str] = ["shortlisted", "tailored", "drafted", "ready", "applied"]


class InterviewPrepDeepPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interview_id: int
    language: Literal["en", "es"] | None = None


class ProfileExpandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    github_user: str | None = None
    portfolio_url: str | None = None
    cert_names: list[str] = []


class CoverLetterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "es"] | None = None


PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "cv_review": CvReviewPayload,
    "legitimacy_batch": LegitimacyBatchPayload,
    "upskill_report": UpskillPayload,
    "interview_prep_deep": InterviewPrepDeepPayload,
    "profile_expand": ProfileExpandPayload,
    "cover_letter": CoverLetterPayload,
}
_JOB_SCOPED_INTENTS = frozenset({"cv_review", "cover_letter"})


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
    """Jobs grouped by the columns shown on the kanban board, plus the dismissed bin."""
    columns = ["shortlisted", "tailored", "ready", "applied", "responded", "interview", "offer"]
    # one query; preserves fit_score/discovered_at ordering. "dismissed" is fetched too but
    # kept out of `jobs` so it never shows on the board / in the command palette.
    rows = db.list_jobs(states=[*columns, "dismissed"])
    grouped: dict[str, list] = {c: [] for c in columns}
    dismissed: list = []
    for j in rows:
        annotated = analytics.annotate(j)
        if j["state"] == "dismissed":
            dismissed.append(annotated)
        else:
            grouped[j["state"]].append(annotated)
    return {"columns": columns, "jobs": grouped, "dismissed": dismissed}


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
    from engine.config import load_criteria
    from engine.outreach import followups

    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    if not db.get_job(job_id):
        raise HTTPException(404, "job not found")
    db.set_state(job_id, body.state, {"via": "dashboard"})
    if body.state == "applied":
        db.snapshot_posting(job_id)  # archive the posting as evidence (F2)
    # Cadencia v2 (F3 §6.1): applied/responded/interview siembran su follow-up; responded
    # además cancela los pendientes (nunca insistir tras una respuesta — regla plan 006).
    if body.state == "responded":
        followups.register_reply(db, job_id)  # cancel pending touches — never pester after a reply
    if body.state in followups.CADENCE_STATES:
        followups.seed_for_state(db, job_id, body.state, load_criteria())
    return {"ok": True, "state": body.state}


@app.post("/api/jobs/{job_id}/applied", dependencies=[Depends(require_trusted_origin)])
def api_mark_applied(job_id: str, db: DB = Depends(get_db)):
    from engine.config import load_criteria
    from engine.outreach import followups

    db.set_state(job_id, "applied", {"via": "dashboard"})
    db.snapshot_posting(job_id)  # archive the posting as evidence (F2)
    followups.seed_for_state(db, job_id, "applied", load_criteria())  # +7d, máx 2 → cold
    return {"ok": True}


@app.post("/api/jobs/{job_id}/prep", dependencies=[Depends(require_trusted_origin)])
def api_prep(job_id: str, body: PrepBody, db: DB = Depends(get_db)):
    from engine.config import default_language
    from engine.cv.build import build_for_job
    from engine.outreach.build import build_outreach, write_package

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    # Generate in the language the body requests, else the PROFILE's own language (so a
    # Spanish-only profile always produces its CV/messages in Spanish, not the offer's language).
    language = body.language or default_language()
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


# ── Follow-ups v2 (F3 §6.1): buckets + confirmación humana de envío ───────────
class FollowupSentBody(BaseModel):
    confirm: bool = False


@app.get("/api/followups")
def api_followups(db: DB = Depends(get_db)):
    from datetime import UTC, datetime

    from engine.config import default_language, load_criteria, load_master_cv
    from engine.outreach import followups as fu

    criteria = load_criteria()
    candidate = (load_master_cv().get("basics") or {}).get("name", "")
    language = default_language()
    highlight = criteria.core_keywords[0] if criteria.core_keywords else ""
    buckets = fu.bucket_followups(db.pending_followups(), datetime.now(UTC))
    out: dict[str, list[dict]] = {}
    for name, rows in buckets.items():
        items = []
        for f in rows:
            d = fu.draft_followup(
                {"company": f.get("company"), "title": f.get("title")},
                candidate,
                f.get("kind") or "applied",
                f.get("touch_number") or 1,
                language=language,
                highlight=highlight,
            )
            items.append(
                {
                    "id": f["id"],
                    "job_id": f["job_id"],
                    "title": f.get("title"),
                    "company": f.get("company"),
                    "kind": f.get("kind"),
                    "touch_number": f.get("touch_number"),
                    "due_at": f.get("due_at"),
                    "days_overdue": f.get("days_overdue"),
                    "draft": {"subject": d.subject, "body": d.body},
                }
            )
        out[name] = items
    out["cold"] = fu.cold_jobs(db, criteria)
    return {"buckets": out}


@app.post("/api/followups/{followup_id}/sent", dependencies=[Depends(require_trusted_origin)])
def api_followup_sent(followup_id: int, body: FollowupSentBody, db: DB = Depends(get_db)):
    """Registro de envío SOLO con confirmación explícita del usuario (§6.1)."""
    from engine.config import load_criteria
    from engine.outreach import followups as fu

    if not body.confirm:
        raise HTTPException(400, "confirmación explícita requerida (confirm: true)")
    res = fu.register_sent(db, followup_id, load_criteria())
    if not res["ok"]:
        raise HTTPException(404, "followup not found")
    return res


# ── Analytics + loop de aprendizaje (F3 §6.2) ─────────────────────────────────
# GET expone funnel/score_floor/conversiones/tiempos/recomendaciones (determinista, $0).
# apply-rec cierra el loop: aplica UNA recomendación editando criteria.md por el mutator
# validado (update_criteria_fields → sólo el frontmatter del perfil activo, gitignorado,
# nunca el .example). Allowlist de campos: un rec jamás toca roles/deal_breakers/etc.
APPLY_REC_CRITERIA_FIELDS = frozenset({"shortlist_threshold"})


class RecBody(BaseModel):
    id: str
    action_type: str
    payload: dict = {}


@app.get("/api/analytics")
def api_analytics(db: DB = Depends(get_db)):
    from engine.config import load_criteria

    return analytics.analytics_payload(db, load_criteria())


@app.post("/api/analytics/apply-rec", dependencies=[Depends(require_trusted_origin)])
def api_apply_rec(body: RecBody):
    from engine.config import load_criteria, update_criteria_fields

    if body.action_type == "set_criteria":
        from pydantic import ValidationError

        field, value = body.payload.get("field"), body.payload.get("value")
        if field not in APPLY_REC_CRITERIA_FIELDS:
            raise HTTPException(400, f"campo no aplicable por rec: {field}")
        try:
            update_criteria_fields({field: value})
        except (ValueError, ValidationError):
            raise HTTPException(400, f"valor inválido para {field}: {value!r}") from None
        return {"ok": True, "applied": f"{field}={value}"}
    if body.action_type == "block_company":
        company = str(body.payload.get("company") or "").strip()
        if not company:
            raise HTTPException(400, "payload.company requerido")
        current = load_criteria().company_blocklist
        if company not in current:
            update_criteria_fields({"company_blocklist": [*current, company]})
        return {"ok": True, "applied": f"blocked:{company}"}
    raise HTTPException(400, f"action_type no soportado: {body.action_type}")


# ── Story bank STAR+R (F3 §6.3) ───────────────────────────────────────────────
# CRUD sobre el banco de historias + un matcher determinista. El matcher rankea las
# historias por solape (skills 3x + tokens) contra la query, canonicalizando ambos lados
# con la ontología del perfil (engine.stories.match_stories), y devuelve el bloque STAR+R
# ya formateado y pegable (format_story). $0: sin red ni LLM.
class StoryBody(BaseModel):
    title: str
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""
    skills: list[str] = []


class StoryPatchBody(BaseModel):
    title: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    reflection: str | None = None
    skills: list[str] | None = None


@app.get("/api/stories")
def api_stories(db: DB = Depends(get_db)):
    return {"stories": db.list_stories()}  # skills ya parseado a list[str] por el helper


@app.get("/api/stories/match")
def api_match_stories(q: str = "", db: DB = Depends(get_db)):
    """Historias rankeadas por relevancia a la query, con su bloque STAR+R pegable (top 5)."""
    from engine.config import load_ontology
    from engine.stories import format_story, match_stories

    ranked = match_stories(db.list_stories(), q, load_ontology())[:5]
    return {
        "matches": [
            {"story": s, "score": score, "formatted": format_story(s)} for s, score in ranked
        ]
    }


@app.post("/api/stories", dependencies=[Depends(require_trusted_origin)])
def api_add_story(body: StoryBody, db: DB = Depends(get_db)):
    sid = db.add_story(**body.model_dump())
    return {"ok": True, "id": sid}


@app.put("/api/stories/{story_id}", dependencies=[Depends(require_trusted_origin)])
def api_update_story(story_id: int, body: StoryPatchBody, db: DB = Depends(get_db)):
    # Solo campos presentes (parche); id desconocido → 404 limpio, nunca un no-op silencioso.
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not db.get_story(story_id):
        raise HTTPException(404, "story not found")
    db.update_story(story_id, fields)
    return {"ok": True}


@app.delete("/api/stories/{story_id}", dependencies=[Depends(require_trusted_origin)])
def api_delete_story(story_id: int, db: DB = Depends(get_db)):
    if not db.delete_story(story_id):  # rowcount 0 → id desconocido
        raise HTTPException(404, "story not found")
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


# ── Intents queue (F4 §7.1) — la web SOLO encola; el brain drena y ejecuta el LLM ──
# $0 INVARIANT: estos endpoints jamás llaman a una API LLM. POST escribe una fila `pending`
# en `intents` (via engine.intents.enqueue) tras validar type + payload por tipo + existencia
# de las entidades referenciadas; el brain la ejecuta después con brain/prompts/<type>.md.
@app.post("/api/intents", dependencies=[Depends(require_trusted_origin)])
def api_enqueue_intent(body: IntentBody, db: DB = Depends(get_db)):
    """Encola trabajo LLM para el brain. Valida type + payload por tipo; NUNCA ejecuta LLM."""
    model = PAYLOAD_MODELS.get(body.type)
    if model is None:
        raise HTTPException(400, f"unknown intent type; allowed: {sorted(PAYLOAD_MODELS)}")
    try:
        payload = model.model_validate(body.payload).model_dump()
    except ValidationError as e:
        first = e.errors()[0]
        raise HTTPException(
            400, f"invalid payload for {body.type}: {first['loc']}: {first['msg']}"
        ) from None
    if body.type in _JOB_SCOPED_INTENTS and (not body.job_id or not db.get_job(body.job_id)):
        raise HTTPException(404, "job not found")
    if body.type == "legitimacy_batch":
        missing = [j for j in payload["job_ids"] if not db.get_job(j)]
        if missing:
            raise HTTPException(404, f"unknown job ids: {missing[:3]}")
    if body.type == "upskill_report":
        bad = [s for s in payload["states"] if s not in STATES]
        if bad:
            raise HTTPException(400, f"invalid states: {bad}")
    if body.type == "interview_prep_deep":
        iv = db.get_interview(payload["interview_id"])
        if not iv:
            raise HTTPException(404, "interview not found")
        body.job_id = iv["job_id"]  # liga el intent a su vacante para el panel
    iid = intents.enqueue(db, body.type, payload, job_id=body.job_id)
    return {"ok": True, "id": iid}


@app.get("/api/intents")
def api_list_intents(status: str | None = None, db: DB = Depends(get_db)):
    if status is not None and status not in intents.INTENT_STATUSES:
        raise HTTPException(400, f"invalid status; allowed: {intents.INTENT_STATUSES}")
    return {
        "intents": intents.list_intents(db, status=status),
        "pending": intents.count_pending(db),
    }


@app.get("/api/intents/{intent_id}")
def api_get_intent(intent_id: str, db: DB = Depends(get_db)):
    row = intents.get_intent(db, intent_id)
    if not row:
        raise HTTPException(404, "intent not found")
    return row


# ── upskill reports (F4 §7.2): the /upskill view reads the latest gap report. ──
# Read-only ($0): pass 1 (hard_gaps) is deterministic and pass 2 (the study plan) was written
# by the brain offline; these endpoints only surface the persisted row.
@app.get("/api/upskill/latest")
def api_upskill_latest(db: DB = Depends(get_db)):
    return {"report": db.latest_upskill_report()}


@app.get("/api/upskill/{report_id}")
def api_upskill_report(report_id: int, db: DB = Depends(get_db)):
    row = db.get_upskill_report(report_id)
    if not row:
        raise HTTPException(404, "upskill report not found")
    return row


# ── profile expansions (F4 §7.2): additive, source-annotated CV enrichment ─────
# GET surfaces the brain's DRAFT proposals (latest first); apply writes ONLY the confirmed item
# indices to the (gitignored) master CV via engine.profile_expand.apply_items. Deterministic
# ($0): no LLM here — the scan was the brain offline. apply is additive + idempotent and never
# clobbers existing CV content, so the origin-guarded POST is the sole confirmation gate.
class ApplyExpansionBody(BaseModel):
    indices: list[int]


@app.get("/api/profile-expansions")
def api_profile_expansions(db: DB = Depends(get_db)):
    return {"expansions": db.list_profile_expansions()}


@app.post(
    "/api/profile-expansions/{exp_id}/apply",
    dependencies=[Depends(require_trusted_origin)],
)
def api_apply_expansion(exp_id: int, body: ApplyExpansionBody, db: DB = Depends(get_db)):
    from engine.profile_expand import apply_items

    if not db.get_profile_expansion(exp_id):
        raise HTTPException(404, "expansion not found")
    try:
        return apply_items(exp_id, body.indices)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


# ── cv_reviews (F4 §7.2): read a job's reviews + apply edits / resolve flags ───
# apply-edit and resolve-flag are DETERMINISTIC ($0): no LLM. They replay a structured
# edit the brain already produced onto the tailored CV / message body and re-render.
# A non-matching / out-of-range request FAILS gracefully as a 400, never a 500.
class EditIndexBody(BaseModel):
    index: int


class FlagResolveBody(BaseModel):
    index: int
    action: Literal["keep", "soften", "drop"]


@app.get("/api/jobs/{job_id}/cv-reviews")
def api_cv_reviews(job_id: str, db: DB = Depends(get_db)):
    if not db.get_job(job_id):
        raise HTTPException(404, "job not found")
    return {"reviews": db.cv_reviews_for(job_id)}


@app.post(
    "/api/cv-reviews/{review_id}/apply-edit",
    dependencies=[Depends(require_trusted_origin)],
)
def api_apply_cv_edit(review_id: int, body: EditIndexBody, db: DB = Depends(get_db)):
    from engine.cv.review import apply_edit

    try:
        return apply_edit(db, review_id, body.index)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post(
    "/api/cv-reviews/{review_id}/resolve-flag",
    dependencies=[Depends(require_trusted_origin)],
)
def api_resolve_cv_flag(review_id: int, body: FlagResolveBody, db: DB = Depends(get_db)):
    from engine.cv.review import resolve_flag

    try:
        return resolve_flag(db, review_id, body.index, body.action)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


# ── Liveness sweep (F2 hygiene) — same fire-and-forget model as /api/discover ─
# Expire dead postings (404/410/tombstone) on demand. Deterministic HTTP-only
# checks (engine.discovery.liveness — no LLM, no key), so still $0. Like the
# discover task, the background worker opens its OWN short-lived `with DB()`
# connection: a sweep does N paced network calls and must never hold the API lock.
_LIVENESS_LOCK = Lock()
_liveness_running = False


def _run_liveness_sweep(limit: int, profile_id: str | None) -> None:
    global _liveness_running
    try:
        from engine.discovery.liveness import sweep_liveness

        # Re-pin the profile captured at enqueue time so a concurrent dashboard
        # switch can't make this run land in another profile's DB.
        if profile_id is not None:
            paths.set_profile(profile_id)
        with DB() as db:  # own connection — never holds the API lock on network
            sweep_liveness(db, limit=limit)
    except Exception as e:  # noqa: BLE001 — record the failure instead of dropping it silently
        try:
            with DB() as db:
                db.log_event(None, "error", {"stage": "liveness_bg", "error": str(e)[:200]})
        except Exception:  # noqa: BLE001
            pass
    finally:
        with _LIVENESS_LOCK:
            _liveness_running = False


@app.post("/api/liveness/sweep", dependencies=[Depends(require_trusted_origin)])
def api_liveness_sweep(background: BackgroundTasks, limit: int = 40):
    """Expire dead postings (404/410/tombstone) in the background. One sweep at a time."""
    global _liveness_running
    with _LIVENESS_LOCK:
        if _liveness_running:
            return {"started": False, "running": True}
        _liveness_running = True
    background.add_task(_run_liveness_sweep, max(1, min(int(limit), 200)), paths.PROFILE_ID)
    return {"started": True}


@app.get("/api/liveness/status")
def api_liveness_status():
    with _LIVENESS_LOCK:
        return {"running": _liveness_running}


@app.get("/api/brief")
def api_brief():
    path = paths.OUTBOX_DIR / "MORNING_BRIEF.md"
    return {
        "markdown": path.read_text()
        if path.exists()
        else "# Sin resumen todavía\n\nEjecuta `atlas brain`."
    }


def _outbox_safe(path: str | None) -> Path | None:
    """Resolve a stored CV path and confine it to the outbox; None if missing/escaping."""
    if not path:
        return None
    p = Path(path).resolve()
    if not p.is_relative_to(paths.OUTBOX_DIR.resolve()) or not p.exists():
        return None
    return p


@app.get("/api/cv/{job_id}/{version_id}/download")
def api_cv_download(job_id: str, version_id: int, fmt: str = "docx", db: DB = Depends(get_db)):
    from engine.config import load_master_cv
    from engine.cv.naming import cv_filename

    fmt = "pdf" if fmt == "pdf" else "docx"  # normalize (also guards the SQL column name below)
    version = next((v for v in db.cv_versions_for(job_id) if v["id"] == version_id), None)
    if not version:
        raise HTTPException(404, "cv version not found")
    from engine.config import default_language

    language = version.get("language") or default_language()
    p = _outbox_safe(version.get("path_pdf") if fmt == "pdf" else version.get("path_docx"))

    # Self-heal: a CV file can be missing (an older prep whose PDF render failed, an outbox
    # that was cleaned, or a CV edited since). Rather than 404, regenerate it from the CURRENT
    # master CV (no new version, no state change) and persist the fresh path so next time is fast.
    if p is None:
        try:
            from engine.cv.build import render_cv_files

            docx_path, pdf_path, _ = render_cv_files(db, job_id, language=language)
        except (ValueError, OSError):
            docx_path = pdf_path = None
        p = _outbox_safe(str(pdf_path) if (fmt == "pdf" and pdf_path) else None) or _outbox_safe(
            str(docx_path) if (fmt == "docx" and docx_path) else None
        )
        if p is not None:
            col = "path_pdf" if fmt == "pdf" else "path_docx"
            db.conn.execute(f"UPDATE cv_versions SET {col}=? WHERE id=?", (str(p), version_id))
            db.conn.commit()
    if p is None:
        raise HTTPException(
            404,
            f"no se pudo generar el {fmt.upper()} — revisa tu CV en Ajustes y vuelve a preparar",
        )

    media = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # Company/role-aware filename so the user can tell which CV is for which company.
    job = db.get_job(job_id) or {}
    cv_name = (load_master_cv().get("basics") or {}).get("name")
    nice = cv_filename(cv_name, job.get("company"), job.get("title"), language, fmt)
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


@app.post("/api/cv/import", dependencies=[Depends(require_trusted_origin)])
async def api_cv_import(file: UploadFile):
    """Extract an uploaded CV (PDF/DOCX) into a reviewable master_cv DRAFT (F2 wizard).

    Deterministic text extraction only (engine/cv/import_cv.py) — never invents structure
    and NEVER touches master_cv.yaml; the human + Cowork map the draft afterwards. The
    upload and the draft live only in the profile's gitignored dirs (repo is public).
    """
    from engine.cv.import_cv import SUPPORTED, build_draft, extract_text

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"formato no soportado {suffix!r}; usa PDF o DOCX")
    paths.ensure_dirs()
    dest = paths.INBOX_DIR / f"cv_import{suffix}"
    dest.write_bytes(await file.read())
    # A malformed/corrupt PDF/DOCX must fail as a clean 400, never a 500: extract_text can raise
    # ValueError (unsupported) but the parsers (python-docx/pdfplumber) raise their own exceptions
    # on garbage bytes, so catch broadly and translate every extraction failure into a 400.
    try:
        text = extract_text(dest)
    except Exception as e:  # noqa: BLE001 — graceful for the user; the message stays generic
        raise HTTPException(
            400, f"no se pudo leer el archivo ({type(e).__name__}); ¿PDF/DOCX válido?"
        ) from None
    if not text.strip():
        raise HTTPException(
            400, "no se pudo extraer texto (¿PDF escaneado/solo imagen?) — prueba otro archivo"
        )
    draft = build_draft(text, domain=profiles.domain_of(paths.PROFILE_ID))
    draft_path = paths.MASTER_CV_PATH.parent / "master_cv.draft.yaml"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(draft)
    return {"ok": True, "draft": draft, "path": str(draft_path), "chars": len(text)}


@app.get("/api/health")
def health():
    return {"ok": True}


def _probe_company_jobs(ats: str, token: str) -> tuple[int, str | None]:
    """Cuenta posiciones del board recién resuelto (preview de confirmación). Nunca lanza:
    si el board no responde devuelve (0, None) — la resolución del ATS ya fue exitosa."""
    from engine.discovery import reverse as _rev
    from engine.discovery.http import get_json, make_client

    urls = {
        "greenhouse": _rev.GREENHOUSE_URL.format(token=token),
        "lever": _rev.LEVER_URL.format(token=token),
        "ashby": _rev.ASHBY_URL.format(token=token),
    }
    url = urls.get(ats)
    if not url:
        return 0, None
    client = make_client(timeout=10)
    try:
        data = get_json(client, url, retries=0)
        titles = [t for t in _rev._titles(ats, data) if t]
        return len(titles), None
    except Exception:  # noqa: BLE001 — preview only; a dead board must not break resolution
        return 0, None
    finally:
        client.close()


# ── Exponer CLI-only en la web (F3 §6.5): resolve/add company, suggest, connections, health ──
class ResolveBody(BaseModel):
    url: str


class CompanyEntryBody(BaseModel):
    # company/ats are optional HERE (not on CompanyTarget) so a bad payload reaches the handler
    # and fails as a clean 400 via save_company's CompanyTarget validation — never a 422 shape
    # error (the contract: add → 400 si la entrada no valida CompanyTarget).
    company: str = ""
    ats: str = ""
    token: str | None = None
    eu: bool = False
    instance: str | None = None
    careers_url: str | None = None


class SuggestBody(BaseModel):
    names: list[str] = []


@app.post("/api/companies/resolve", dependencies=[Depends(require_trusted_origin)])
def api_resolve_company(body: ResolveBody, db: DB = Depends(get_db)):
    """resolve-ats en la web: detecta el ATS de una URL de carreras y previsualiza el board."""
    from engine.config import load_companies
    from engine.normalize import norm_company

    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "url requerida")
    contract = resolve_ats(url)  # None si no hay ATS conocido — NO es un error
    if not contract:
        return {
            "resolved": False,
            "company": None,
            "ats": None,
            "token": None,
            "preview_jobs_count": 0,
            "already_configured": False,
        }
    token = contract.get("token") or ""
    count, company_name = _probe_company_jobs(contract["ats"], token)
    # Nombre sugerido: el que reporte el board, o derivado del host de la URL.
    name = company_name or (urlsplit(url).hostname or "").split(".")[0].title() or token
    known = {norm_company(c.company) for c in load_companies()}
    return {
        "resolved": True,
        "company": name,
        "ats": contract["ats"],
        "token": token,
        "preview_jobs_count": count,
        "already_configured": norm_company(name) in known,
    }


@app.post("/api/companies/add", dependencies=[Depends(require_trusted_origin)])
def api_add_company(body: CompanyEntryBody):
    """Añade la empresa confirmada a companies.yaml del perfil activo (append idempotente)."""
    from engine.config import save_company

    entry = {k: v for k, v in body.model_dump().items() if v not in (None, "", False)}
    try:
        added = save_company(entry)
    except Exception as e:  # noqa: BLE001 — pydantic ValidationError de CompanyTarget → 400 limpio
        raise HTTPException(400, f"empresa inválida: {e}") from None
    return {"ok": True, "added": added}


@app.post("/api/discovery/suggest", dependencies=[Depends(require_trusted_origin)])
def api_suggest_companies(body: SuggestBody):
    """Reverse ATS discovery: nombres (o las seeds del perfil) → empresas que matchean el perfil."""
    from engine.config import load_criteria, load_discovery_seeds

    names = [n.strip() for n in (body.names or []) if n and n.strip()] or load_discovery_seeds()
    suggestions = reverse.suggest_companies(names, load_criteria())
    return {"suggestions": suggestions}


@app.post("/api/connections/import", dependencies=[Depends(require_trusted_origin)])
async def api_import_connections(file: UploadFile, db: DB = Depends(get_db)):
    """Upload de LinkedIn Connections.csv → import_connections_csv (referral detection).

    Bare `UploadFile` (no `File(...)` default) mirrors /api/cv/import and keeps the endpoint
    within the project's ruff B008 policy without whitelisting `fastapi.File`."""
    import tempfile

    from engine.referrals.connections import import_connections_csv

    raw = await file.read()
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)
    try:
        imported = import_connections_csv(db, tmp_path)
    except Exception as e:  # noqa: BLE001 — CSV ilegible → 400 limpio (como F2 cv/import)
        raise HTTPException(400, f"CSV ilegible: {e}") from None
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"ok": True, "imported": imported}


@app.get("/api/system/health")
def api_system_health(db: DB = Depends(get_db)):
    """Consolida `atlas status` (counts, source health, last run) + `atlas doctor` (safeguards $0)."""
    counts = db.counts_by_state()
    health = db.latest_source_health()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    default_base = base_url in (None, "", "https://api.anthropic.com", "https://api.anthropic.com/")
    return {
        "profile": paths.PROFILE_ID or "legacy",
        "db": {
            "path": str(paths.DB_PATH),
            "ok": True,
            "jobs": sum(counts.values()),
        },
        "counts": counts,
        "last_run": db.meta_get("last_run"),
        # canonical heartbeat key (engine writes/reads "last_success_ts"; see engine.heartbeat).
        "last_success": db.meta_get("last_success_ts"),
        "sources": [
            {
                "source": h["source"],
                "ok": bool(h["ok"]),
                "count": h["count"],
                "run_at": h.get("run_at"),
                "error": h.get("error"),
            }
            for h in health
        ],
        "safeguards": {
            "api_key_unset": not api_key,
            "base_url_default": bool(default_base),
        },
    }


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


# ── Criteria (F2 wizard): read/write the active profile's criteria.md frontmatter ─
@app.get("/api/criteria")
def api_get_criteria():
    from engine.config import load_criteria

    c = load_criteria()
    return {"criteria": c.model_dump(exclude={"prose"}), "prose": c.prose}


@app.put("/api/criteria", dependencies=[Depends(require_trusted_origin)])
def api_put_criteria(body: CriteriaBody):
    from pydantic import ValidationError

    from engine.config import Criteria, save_criteria

    # Validate BEFORE touching the file: an invalid payload must 422 and leave the
    # existing criteria.md untouched (never half-write a corrupt file).
    try:
        c = Criteria(**{**body.criteria, "prose": body.prose})
    except ValidationError as e:
        raise HTTPException(422, str(e)) from None
    path = save_criteria(c)
    return {"ok": True, "path": str(path)}


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
    from engine.config import load_criteria, load_cv_layout, load_master_cv, load_ontology
    from engine.portfolio.peer_examples import load_references
    from engine.portfolio.prompt import build_portfolio_prompt
    from engine.profiles import domain_of

    references = load_references(domain_of(paths.PROFILE_ID))
    return {
        "examples": references["examples"],
        "patterns": references["patterns"],
        "prompt": build_portfolio_prompt(
            load_master_cv(),
            layout=load_cv_layout(),
            criteria=load_criteria(),
            ontology=load_ontology(),
        ),
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


class DebriefBody(BaseModel):
    debrief_md: str
    reanalyze: bool = False


@app.post("/api/interview/{interview_id}/debrief", dependencies=[Depends(require_trusted_origin)])
def api_interview_debrief(interview_id: int, body: DebriefBody, db: DB = Depends(get_db)):
    """Save the candidate's post-interview debrief and, if `reanalyze`, re-enqueue an
    interview_prep_deep intent for a follow-up analysis. No LLM here ($0): the brain runs it
    offline. The debrief feeds the next prep (it lands in that intent's context)."""
    iv = db.get_interview(interview_id)
    if not iv:
        raise HTTPException(404, "interview not found")
    if not body.debrief_md.strip():
        raise HTTPException(400, "debrief_md must not be empty")
    db.set_interview_debrief(interview_id, body.debrief_md.strip())
    intent_id = None
    if body.reanalyze:
        intent_id = intents.enqueue(
            db, "interview_prep_deep", {"interview_id": interview_id}, job_id=iv["job_id"]
        )
    return {"ok": True, "intent_id": intent_id}


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
    from engine.config import load_criteria, load_master_cv

    cv = load_master_cv()
    criteria = load_criteria()
    # Domain + a short target label so the UI shows domain-appropriate copy instead of a
    # hardcoded "reposition toward AI/ML". target_label is ONLY the profile's opted-in
    # repositioning target; empty → the UI uses neutral "hacia tu rol objetivo" (never the CV
    # headline, which would read as "reposition toward <your own current title>").
    target_label = criteria.repositioning_target.strip()
    return {
        "complete": db.meta_get("onboarding_complete") == "1",
        "profile": paths.PROFILE_ID or profiles.OWNER_ID,
        "domain": profiles.domain_of(paths.PROFILE_ID),
        "target_label": target_label,
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


# ── Serve the built frontend (SPA) ───────────────────────────────────────────
# Catch-all definido AL FINAL para no sombrear /api/*. Sirve archivos reales del
# build cuando existen y hace fallback a index.html para las rutas del router
# (deep links /pipeline, /jobs/:id, …). Lee _DIST en call-time (testeable).
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str) -> FileResponse:
    if full_path.split("/", 1)[0] == "api":
        raise HTTPException(status_code=404, detail="Not found")
    if full_path:
        candidate = (_DIST / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(_DIST.resolve()):
            return FileResponse(str(candidate))
    index = _DIST / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend no compilado — corre scripts/run.sh (o npm run build).",
        )
    return FileResponse(str(index))
