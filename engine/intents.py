"""Intent queue — guided handoff entre la web y el brain (Claude Code).

Doctrina $0: el backend NUNCA llama a una API LLM. La web solo ENCOLA una fila en
`intents`; el brain la drena como paso 0 de "corre atlas" (ver brain/SKILL.md), ejecuta
cada intent con su prompt de brain/prompts/<type>.md y la completa con un JSON que
`apply_result()` valida y escribe en las tablas destino. La web luego solo LEE esas tablas.

Los writers (`_RESULT_WRITERS`) y builders de contexto (`_CONTEXT_BUILDERS`) por tipo se
registran en este módulo a medida que cada feature aterriza (ver tareas 7-12 del plan F4).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from engine.db.models import DB
from engine.normalize import now_iso

INTENT_TYPES = (
    "cv_review",
    "legitimacy_batch",
    "upskill_report",
    "interview_prep_deep",
    "profile_expand",
    "cover_letter",
)
INTENT_STATUSES = ("pending", "running", "done", "error")

# type -> prompt file the brain must read (brain/prompts/<file>).
PROMPT_FILES = {
    "cv_review": "cv_review.md",
    "legitimacy_batch": "legitimacy.md",
    "upskill_report": "upskill.md",
    "interview_prep_deep": "interview_prep_deep.md",
    "profile_expand": "profile_expand.md",
    "cover_letter": "cover_letter.md",
}

_CONTEXT_BUILDERS: dict[str, Callable[[DB, dict], dict]] = {}
_RESULT_WRITERS: dict[str, Callable[[DB, dict, dict], str]] = {}


def enqueue(db: DB, type_: str, payload: dict | None = None, job_id: str | None = None) -> str:
    if type_ not in INTENT_TYPES:
        raise ValueError(f"unknown intent type {type_!r}; allowed: {INTENT_TYPES}")
    intent_id = f"in_{uuid4().hex[:12]}"
    db.conn.execute(
        """INSERT INTO intents (id, type, job_id, payload, status, created_at)
           VALUES (?,?,?,?, 'pending', ?)""",
        (intent_id, type_, job_id, json.dumps(payload or {}), now_iso()),
    )
    db.conn.commit()
    return intent_id


def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["payload"] = json.loads(d.get("payload") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["payload"] = {}
    return d


def get_intent(db: DB, intent_id: str) -> dict | None:
    row = db.conn.execute("SELECT * FROM intents WHERE id=?", (intent_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_intents(db: DB, status: str | None = None, limit: int = 200) -> list[dict]:
    q, params = "SELECT * FROM intents", []
    if status:
        q += " WHERE status=?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    return [_row_to_dict(r) for r in db.conn.execute(q, params).fetchall()]


def list_pending(db: DB) -> list[dict]:
    return list_intents(db, status="pending")


def count_pending(db: DB) -> int:
    row = db.conn.execute("SELECT COUNT(*) n FROM intents WHERE status='pending'").fetchone()
    return int(row["n"])


def _require(db: DB, intent_id: str, allowed: tuple[str, ...]) -> dict:
    intent = get_intent(db, intent_id)
    if not intent:
        raise ValueError(f"intent {intent_id} not found")
    if intent["status"] not in allowed:
        raise ValueError(f"intent {intent_id} is {intent['status']!r}; expected one of {allowed}")
    return intent


def mark_running(db: DB, intent_id: str) -> None:
    _require(db, intent_id, ("pending", "error"))  # error → reintento permitido
    db.conn.execute(
        "UPDATE intents SET status='running', error=NULL, completed_at=NULL WHERE id=?",
        (intent_id,),
    )
    db.conn.commit()


def mark_done(db: DB, intent_id: str, result_ref: str) -> None:
    _require(db, intent_id, ("running",))
    db.conn.execute(
        "UPDATE intents SET status='done', result_ref=?, completed_at=? WHERE id=?",
        (result_ref, now_iso(), intent_id),
    )
    db.conn.commit()


def mark_error(db: DB, intent_id: str, error: str) -> None:
    _require(db, intent_id, ("running", "pending"))
    db.conn.execute(
        "UPDATE intents SET status='error', error=?, completed_at=? WHERE id=?",
        (str(error)[:500], now_iso(), intent_id),
    )
    db.conn.commit()


# ── contexto determinista por intent (lo consume el brain vía `atlas intents context`) ──
def _job_brief(job: dict | None, desc_chars: int = 6000) -> dict | None:
    if not job:
        return None
    keys = (
        "id",
        "title",
        "company",
        "location",
        "is_remote",
        "workplace_type",
        "url",
        "apply_url",
        "salary_min",
        "salary_max",
        "salary_currency",
        "date_posted",
        "fit_score",
        "match_score",
        "state",
    )
    out = {k: job.get(k) for k in keys}
    out["description"] = (job.get("description") or "")[:desc_chars]
    return out


def context_for(db: DB, intent_id: str) -> dict:
    """Todo lo determinista que el brain necesita para ejecutar el intent, en un JSON."""
    intent = get_intent(db, intent_id)
    if not intent:
        raise ValueError(f"intent {intent_id} not found")
    ctx: dict[str, Any] = {
        "intent": {k: intent[k] for k in ("id", "type", "job_id", "status")},
        "payload": intent["payload"],
        "prompt_file": f"brain/prompts/{PROMPT_FILES[intent['type']]}",
    }
    if intent["job_id"]:
        ctx["job"] = _job_brief(db.get_job(intent["job_id"]))
    builder = _CONTEXT_BUILDERS.get(intent["type"])
    if builder:
        ctx.update(builder(db, intent))
    return ctx


def apply_result(db: DB, intent_id: str, result: dict) -> str:
    """Valida y escribe el resultado del brain en las tablas destino; marca done.

    Lanza ValueError (sin tocar la DB destino) si el JSON no cumple el contrato del tipo —
    el intent queda `running` para que el brain corrija y reintente.
    """
    intent = _require(db, intent_id, ("running",))
    if not isinstance(result, dict):
        raise ValueError("result must be a JSON object")
    writer = _RESULT_WRITERS.get(intent["type"])
    if writer is None:
        raise ValueError(f"no result writer registered for type {intent['type']!r}")
    ref = writer(db, intent, result)
    mark_done(db, intent_id, ref)
    return ref


# ── cv_review (F4 §7.2) ────────────────────────────────────────────────────────
# The context builder feeds the brain a deterministic snapshot (the tailored CV, the
# drafted messages, the JD keyword gaps, the master-CV path). The writer only VALIDATES
# and PERSISTS what the brain produced — it NEVER calls an LLM ($0 invariant).
_CRITIQUE_CATEGORIES = ("missed_keywords", "company_angles", "reframing", "tone_register")
_FLAG_CLASSES = ("OK", "Flag", "Never")


def _ctx_cv_review(db: DB, intent: dict) -> dict:
    import engine.paths as paths
    from engine.cv.review import EDIT_FILES, dump_tailored_cv

    job_id = intent["job_id"]
    path = dump_tailored_cv(db, job_id)
    job = db.get_job(job_id) or {}
    messages = [
        {"id": m["id"], "kind": m["kind"], "subject": m.get("subject"), "body": m["body"]}
        for m in db.messages_for(job_id)
        if m["kind"] in EDIT_FILES
    ]
    return {
        "cv_yaml_path": str(path),
        "cv_yaml": path.read_text(),
        "messages": messages,
        "match_missing": json.loads(job.get("match_missing") or "[]"),
        "master_cv_path": str(paths.MASTER_CV_PATH),
    }


def _write_cv_review(db: DB, intent: dict, result: dict) -> str:
    from engine.cv.review import EDIT_FILES

    critique = result.get("critique")
    if not isinstance(critique, dict) or set(_CRITIQUE_CATEGORIES) - set(critique):
        raise ValueError(f"critique must contain all of {_CRITIQUE_CATEGORIES}")
    edits = result.get("edits", [])
    for e in edits:
        if not isinstance(e, dict) or e.get("file") not in EDIT_FILES:
            raise ValueError(f"every edit needs file ∈ {EDIT_FILES}")
        if not (e.get("old_string") and e.get("new_string") and e.get("reason")):
            raise ValueError("every edit needs old_string, new_string and reason")
    flags = result.get("flags", [])
    for f in flags:
        if not isinstance(f, dict) or f.get("classification") not in _FLAG_CLASSES:
            raise ValueError(f"every flag needs classification ∈ {_FLAG_CLASSES}")
        if not f.get("bullet") or not f.get("reason"):
            raise ValueError("every flag needs bullet and reason")
        if f["classification"] == "Flag" and not f.get("softened"):
            raise ValueError("Flag entries need a softened alternative")
    versions = db.cv_versions_for(intent["job_id"])
    rid = db.add_cv_review(
        intent["job_id"],
        intent_id=intent["id"],
        cv_version_id=versions[0]["id"] if versions else None,
        edits=edits,
        critique=critique,
        flags=flags,
    )
    return f"cv_review:{rid}"


_CONTEXT_BUILDERS["cv_review"] = _ctx_cv_review
_RESULT_WRITERS["cv_review"] = _write_cv_review


# ── cover_letter (F4 §7.2) ─────────────────────────────────────────────────────
# Context feeds the brain the master-CV path (exclusive source of truth), what past
# outcomes taught us about this company, and the drafts already on the job (so the brain
# improves on the deterministic letter instead of duplicating it). The writer only
# VALIDATES the brain's JSON and PERSISTS it as a message — no LLM here ($0 invariant).
_COVER_LETTER_LANGS = ("en", "es")


def _ctx_cover_letter(db: DB, intent: dict) -> dict:
    import engine.paths as paths

    job = db.get_job(intent["job_id"]) or {}
    return {
        "master_cv_path": str(paths.MASTER_CV_PATH),
        "learnings": db.learnings_for_company(job.get("company", "")),
        "existing_messages": [
            {"kind": m["kind"], "subject": m.get("subject"), "body": m["body"]}
            for m in db.messages_for(intent["job_id"])
        ],
    }


def _write_cover_letter(db: DB, intent: dict, result: dict) -> str:
    subject = (result.get("subject") or "").strip()
    body = (result.get("body") or "").strip()
    if not subject or not body:
        raise ValueError("cover_letter result needs non-empty subject and body")
    language = result.get("language") or "en"
    if language not in _COVER_LETTER_LANGS:
        raise ValueError(f"language must be one of {_COVER_LETTER_LANGS}")
    mid = db.add_message(
        intent["job_id"],
        channel="email",
        kind="cover_letter",
        body=body,
        subject=subject,
        variant="brain",
        language=language,
        state="draft",
    )
    return f"message:{mid}"


_CONTEXT_BUILDERS["cover_letter"] = _ctx_cover_letter
_RESULT_WRITERS["cover_letter"] = _write_cover_letter


# ── legitimacy_batch (F4 §7.2, Block G) ────────────────────────────────────────
# Assesses posting LEGITIMACY (ghost-job triage) — ORTHOGONAL to fit: it writes only
# jobs.legitimacy_tier + legitimacy_notes, never the scores. The context hands the brain a
# per-job brief + today's date (posting age is the strongest signal). The writer VALIDATES a
# per-job_id {tier, notes} batch and PERSISTS each — no LLM here ($0 invariant). Every entry
# must reference a job_id from the intent's payload (the brain can only rate the shortlist it
# was handed); a malformed batch raises and leaves the intent `running` for a corrected retry.
_LEGITIMACY_TIERS = ("high", "medium", "low")


def _ctx_legitimacy(db: DB, intent: dict) -> dict:
    briefs = []
    for jid in intent["payload"].get("job_ids", []):
        b = _job_brief(db.get_job(jid), desc_chars=2000)
        if b:
            briefs.append(b)
    return {"jobs": briefs, "today": now_iso()[:10]}


def _write_legitimacy(db: DB, intent: dict, result: dict) -> str:
    rows = result.get("jobs")
    if not isinstance(rows, list) or not rows:
        raise ValueError("result.jobs must be a non-empty list")
    allowed = set(intent["payload"].get("job_ids", []))
    for r in rows:
        if not isinstance(r, dict) or r.get("job_id") not in allowed:
            raise ValueError("every entry needs a job_id from the intent's payload.job_ids")
        if r.get("tier") not in _LEGITIMACY_TIERS:
            raise ValueError(f"tier must be one of {_LEGITIMACY_TIERS}")
        if not (r.get("notes") or "").strip():
            raise ValueError("every entry needs non-empty notes (signal-based observations)")
    for r in rows:
        db.set_legitimacy(r["job_id"], r["tier"], r["notes"].strip())
    return f"jobs:{len(rows)}"


_CONTEXT_BUILDERS["legitimacy_batch"] = _ctx_legitimacy
_RESULT_WRITERS["legitimacy_batch"] = _write_legitimacy


# ── upskill_report (F4 §7.2) ──────────────────────────────────────────────────
# Two passes. Pass 1 (engine.upskill.hard_skill_gaps) is DETERMINISTIC ($0): the weighted
# missing-skill inventory over the jobs in scope. The context builder injects it plus the
# previous report so the brain can diff. Pass 2 is the brain synthesizing the study plan +
# severity heatmap (brain/prompts/upskill.md). The writer only VALIDATES the brain's JSON
# (non-empty report_md + a heatmap of {skill, severity ∈ _SEVERITIES, note}) and PERSISTS it
# alongside a fresh pass-1 snapshot — no LLM here. Malformed → raises, leaving the intent
# `running` for a corrected retry.
_SEVERITIES = ("Critical", "High", "Medium", "Low")


def _ctx_upskill(db: DB, intent: dict) -> dict:
    from engine.upskill import hard_skill_gaps

    states = intent["payload"].get("states") or ["shortlisted"]
    prev = db.latest_upskill_report()
    return {
        "hard_gaps": hard_skill_gaps(db, states),
        "previous_report": (
            {
                "report_md": prev["report_md"],
                "heatmap": prev["heatmap"],
                "created_at": prev["created_at"],
            }
            if prev
            else None
        ),
    }


def _write_upskill(db: DB, intent: dict, result: dict) -> str:
    report_md = (result.get("report_md") or "").strip()
    if not report_md:
        raise ValueError("upskill result needs a non-empty report_md")
    heatmap = result.get("heatmap", [])
    if not isinstance(heatmap, list):
        raise ValueError("heatmap must be a list")
    for h in heatmap:
        if not isinstance(h, dict) or h.get("severity") not in _SEVERITIES:
            raise ValueError(f"every heatmap entry needs severity ∈ {_SEVERITIES}")
        if not (h.get("skill") or "").strip():
            raise ValueError("every heatmap entry needs a skill")
    states = intent["payload"].get("states") or ["shortlisted"]
    from engine.upskill import hard_skill_gaps

    rid = db.add_upskill_report(
        intent_id=intent["id"],
        report_md=report_md,
        heatmap=heatmap,
        hard_gaps=hard_skill_gaps(db, states),
    )
    return f"upskill_report:{rid}"


_CONTEXT_BUILDERS["upskill_report"] = _ctx_upskill
_RESULT_WRITERS["upskill_report"] = _write_upskill


# ── interview_prep_deep (F4 §7.2) ─────────────────────────────────────────────
# Upgrades the DETERMINISTIC prep doc (engine.interview.interview_prep.gen_prep_doc, $0) into
# an audience-mapped, source-cited, story-matched pack. The context builder hands the brain the
# baseline prep as the floor + the F3 story bank's ranked matches (via match_stories, also $0).
# The writer only VALIDATES the brain's JSON (non-empty prep_md) and PERSISTS deep_prep_md — no
# LLM here. Malformed → raises, leaving the intent `running` for a corrected retry.
def _match_stories_safe(db: DB, query_text: str) -> list[dict]:
    """F3 story bank matcher, guarded so F4 lands even if F3 hasn't merged yet."""
    try:
        from engine.config import load_ontology
        from engine.stories import format_story, match_stories
    except ImportError:
        return []
    stories = db.list_stories() if hasattr(db, "list_stories") else []
    if not stories:
        return []
    ranked = match_stories(stories, query_text, load_ontology())
    return [{"story": format_story(s), "score": score} for s, score in ranked[:5]]


def _ctx_interview_prep_deep(db: DB, intent: dict) -> dict:
    import engine.paths as paths
    from engine.interview.interview_prep import gen_prep_doc

    ivid = intent["payload"]["interview_id"]
    iv = db.get_interview(ivid)
    if not iv:
        raise ValueError(f"interview {ivid} not found")
    job = db.get_job(iv["job_id"]) or {}
    lang = intent["payload"].get("language")
    prep_path = gen_prep_doc(db, ivid, language=lang)  # deterministic baseline
    query = f"{job.get('title', '')} {job.get('description', '')}"
    return {
        "interview": {
            "id": ivid,
            "round": iv.get("round"),
            "mode": iv.get("mode"),
            "scheduled_at": iv.get("scheduled_at"),
        },
        "interviewers": db.interviewers_for(ivid),
        "job": _job_brief(job),
        "deterministic_prep": prep_path.read_text(),
        "matched_stories": _match_stories_safe(db, query),
        "debrief_md": iv.get("debrief_md"),
        "master_cv_path": str(paths.MASTER_CV_PATH),
    }


def _write_interview_prep_deep(db: DB, intent: dict, result: dict) -> str:
    prep_md = (result.get("prep_md") or "").strip()
    if not prep_md:
        raise ValueError("interview_prep_deep result needs a non-empty prep_md")
    ivid = intent["payload"]["interview_id"]
    if not db.get_interview(ivid):
        raise ValueError(f"interview {ivid} vanished")
    db.set_interview_deep_prep(ivid, prep_md)
    return f"interview:{ivid}"


_CONTEXT_BUILDERS["interview_prep_deep"] = _ctx_interview_prep_deep
_RESULT_WRITERS["interview_prep_deep"] = _write_interview_prep_deep
