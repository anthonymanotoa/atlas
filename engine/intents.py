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
