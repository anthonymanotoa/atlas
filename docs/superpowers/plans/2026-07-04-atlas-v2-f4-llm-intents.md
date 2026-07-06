# Atlas v2 — Fase 4: Features LLM + guided handoff — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la sección 7 del spec (`docs/superpowers/specs/2026-07-04-atlas-v2-design.md`): las features que requieren juicio LLM (reviewer de CV/carta, legitimidad de postings, upskill/gap analysis, interview prep profundo, expand de perfil, carta personalizada), ejecutadas por el brain (Claude Code) y pedidas desde la web mediante una cola de `intents` + guided handoff — sin que el backend llame jamás a una API LLM.

**Architecture:** La web encola filas en una tabla nueva `intents` (`POST /api/intents`, origin-guarded) y las muestra en un panel "Tareas del Brain" con la frase universal ("Abre Claude Code en `~/dev/personal/atlas` y di: `corre atlas`"). El brain gana un **paso 0**: drena la cola vía CLI (`atlas intents list/start/context/complete/fail`), ejecuta cada intent con su prompt de `brain/prompts/<type>.md`, y la completa con un JSON que `engine/intents.apply_result()` **valida deterministamente** y escribe en las tablas destino (`cv_reviews`, `jobs.legitimacy_*`, `upskill_reports`, `interviews.deep_prep_md`, `profile_expansions`, `messages`). La web luego solo LEE esas tablas. Los prompts son el producto: van completos y committeados en `brain/prompts/`.

**Tech Stack:** Python 3.12 + Typer + FastAPI + Pydantic + SQLite (engine/backend), React + TS + shadcn/Radix + Vitest (frontend), Markdown prompts (brain), pytest.

## Global Constraints

- **Doctrina $0 (innegociable):** el backend NUNCA llama a una API LLM, no importa `ANTHROPIC_API_KEY`, no SDK. Todo lo LLM ocurre en la corrida del brain (sesión de Claude Code en la suscripción del usuario). La web solo encola y muestra.
- **Escrituras LLM→DB siempre validadas:** el brain nunca escribe SQL a mano; entrega un JSON a `atlas intents complete --result-file` y `apply_result()` valida forma/enums/existencia antes de tocar tablas. JSON inválido → el intent queda `running` y el CLI sale con código 2 (el brain corrige y reintenta); tarea imposible → `atlas intents fail`.
- Tests backend: `rtk uv run --group dev pytest <archivo> -q` (NUNCA `--extra dev`, NUNCA pytest pelado). Suite completa hoy verde — debe seguir verde.
- Tests frontend: `npm --prefix dashboard/frontend test`; build: `npm --prefix dashboard/frontend run build`.
- Todos los POST nuevos llevan `dependencies=[Depends(require_trusted_origin)]` (patrón plan 020).
- Migraciones: patrón existente — columna nueva en `CREATE TABLE` de `schema.sql` **y** `_ensure_column()` en `DB._migrate()`; tabla nueva solo en `schema.sql` (`CREATE TABLE IF NOT EXISTS`).
- Repo PÚBLICO: los prompts en `brain/prompts/` se committean (son genéricos); datos personales JAMÁS (perfiles/DB/outbox están gitignorados; `profile_expand` escribe solo en `paths.MASTER_CV_PATH`, que vive en rutas gitignoradas).
- Este plan asume F1–F3 mergeadas (fases secuenciales). Donde toca el shell/rutas de F1 o `match_stories` de F3, el punto de integración queda explícito y el código degrada con gracia si falta (import guardado, anclas actuales de `App.tsx`/`DetailDrawer.tsx` como fallback).
- Commits por tarea, archivos por nombre (nunca `git add .`/`-A`), trailer: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- UI nueva sigue el skill `atlas-design-system` (primitivos de `src/components/ui/*`, copy en español).
- Líneas Python ≤ 100 chars (ruff `line-length = 100`).

## File Structure

- `engine/db/schema.sql` — tablas `intents`, `cv_reviews`, `upskill_reports`, `profile_expansions`; columnas nuevas en `jobs` e `interviews`.
- `engine/db/models.py` — `_migrate()` + métodos: `add_cv_review/get_cv_review/cv_reviews_for/set_cv_review_edits/set_cv_review_flags`, `set_legitimacy`, `add_upskill_report/get_upskill_report/list_upskill_reports/latest_upskill_report`, `set_interview_deep_prep/set_interview_debrief`, `add_profile_expansion/get_profile_expansion/set_profile_expansion`.
- `engine/intents.py` — **nuevo**: cola (`enqueue/get_intent/list_intents/list_pending/mark_running/mark_done/mark_error`), `context_for()` (+ builders por tipo), `apply_result()` (+ writers por tipo), constantes `INTENT_TYPES/INTENT_STATUSES/PROMPT_FILES`.
- `engine/cv/review.py` — **nuevo**: `dump_tailored_cv()`, `apply_edit()`, `resolve_flag()`.
- `engine/upskill.py` — **nuevo**: `hard_skill_gaps()` (pasada 1 determinista).
- `engine/profile_expand.py` — **nuevo**: `apply_items()` (escritura aditiva al YAML del perfil).
- `engine/cli.py` — subcomando `intents` (list/start/context/complete/fail) + `cv dump`.
- `brain/run_brain.py` — paso 0: `intents_pending` en summary + sección en el brief.
- `brain/SKILL.md` — paso 0 de drenaje, trigger "corre atlas", style rules + verificación visual de PDF.
- `brain/prompts/` — **nuevo**: `style_rules.md`, `cv_review.md`, `cover_letter.md`, `legitimacy.md`, `upskill.md`, `interview_prep_deep.md`, `profile_expand.md`.
- `dashboard/backend/main.py` — endpoints: `POST/GET /api/intents`, `GET /api/intents/{id}`, `GET /api/jobs/{id}/cv-reviews`, `POST /api/cv-reviews/{id}/apply-edit`, `POST /api/cv-reviews/{id}/resolve-flag`, `GET /api/upskill`, `GET /api/upskill/{id}`, `POST /api/interviews/{id}/debrief`, `GET /api/profile-expansions`, `POST /api/profile-expansions/{id}/apply`.
- `dashboard/frontend/src/api.ts` — tipos + métodos nuevos.
- `dashboard/frontend/src/components/` — **nuevos**: `BrainTasksPanel.tsx`, `IntentConfirmDialog.tsx`, `CvReviewPanel.tsx`, `UpskillView.tsx`, `ProfileExpandSection.tsx`; **modificados**: `DetailDrawer.tsx`, `Board.tsx`, `InterviewPanel.tsx`, `SettingsModal.tsx`, shell (`App.tsx` o el shell de F1).
- `tests/` — `test_intents.py`, `test_intents_api.py`, `test_cv_review.py`, `test_upskill.py`, `test_brain_intents.py` (+ ampliaciones).
- `dashboard/frontend/src/components/BrainTasksPanel.test.tsx`.

---

### Task 1: Tabla `intents` + módulo `engine/intents.py` (cola)

**Files:**
- Modify: `engine/db/schema.sql`
- Create: `engine/intents.py`
- Test: `tests/test_intents.py`

**Interfaces:**
- `intents.INTENT_TYPES: tuple[str, ...]` = `("cv_review", "legitimacy_batch", "upskill_report", "interview_prep_deep", "profile_expand", "cover_letter")`
- `intents.INTENT_STATUSES: tuple[str, ...]` = `("pending", "running", "done", "error")`
- `intents.enqueue(db: DB, type_: str, payload: dict | None = None, job_id: str | None = None) -> str` (id `in_<hex12>`; type inválido → `ValueError`)
- `intents.get_intent(db: DB, intent_id: str) -> dict | None` (payload ya parseado a dict)
- `intents.list_intents(db: DB, status: str | None = None, limit: int = 200) -> list[dict]`
- `intents.list_pending(db: DB) -> list[dict]`
- `intents.mark_running(db, intent_id) -> None` (solo desde `pending`/`error`, si no `ValueError`)
- `intents.mark_done(db, intent_id, result_ref: str) -> None` (solo desde `running`)
- `intents.mark_error(db, intent_id, error: str) -> None`

- [ ] **Step 1: Test que falla**

```python
# tests/test_intents.py
"""Cola de intents (F4): enqueue/list/transiciones. Los writers por tipo se testean
en las tareas de cada tipo; aquí solo el ciclo de vida genérico."""

from __future__ import annotations

import pytest

from engine import intents
from engine.db.models import DB


@pytest.fixture
def db(tmp_path):
    with DB(tmp_path / "t.db") as d:
        yield d


def test_enqueue_and_list_pending(db):
    iid = intents.enqueue(db, "cv_review", {"language": "en"}, job_id=None)
    assert iid.startswith("in_")
    rows = intents.list_intents(db, status="pending")
    assert [r["id"] for r in rows] == [iid]
    assert rows[0]["payload"] == {"language": "en"}
    assert rows[0]["status"] == "pending" and rows[0]["created_at"]


def test_enqueue_unknown_type_raises(db):
    with pytest.raises(ValueError):
        intents.enqueue(db, "world_peace", {})


def test_lifecycle_pending_running_done(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    assert intents.get_intent(db, iid)["status"] == "running"
    intents.mark_done(db, iid, "upskill_report:1")
    row = intents.get_intent(db, iid)
    assert row["status"] == "done"
    assert row["result_ref"] == "upskill_report:1"
    assert row["completed_at"]


def test_mark_running_only_from_pending_or_error(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_done(db, iid, "x:1")
    with pytest.raises(ValueError):
        intents.mark_running(db, iid)


def test_error_intent_can_be_retried(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_error(db, iid, "boom")
    row = intents.get_intent(db, iid)
    assert row["status"] == "error" and row["error"] == "boom" and row["completed_at"]
    intents.mark_running(db, iid)  # reintento permitido
    assert intents.get_intent(db, iid)["status"] == "running"


def test_mark_done_requires_running(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):
        intents.mark_done(db, iid, "x:1")
```

- [ ] **Step 2: Correr, esperar FAIL** — `rtk uv run --group dev pytest tests/test_intents.py -q` → `ModuleNotFoundError: No module named 'engine.intents'` (o `no such table: intents`).

- [ ] **Step 3: Schema.** Añadir al final de `engine/db/schema.sql`:

```sql
-- Intent queue (F4): guided handoff web → brain. The web enqueues; the brain (Claude Code)
-- drains as step 0 of `corre atlas` and completes each intent with a validated result JSON.
CREATE TABLE IF NOT EXISTS intents (
    id           TEXT PRIMARY KEY,              -- in_<hex12>
    type         TEXT NOT NULL,                 -- cv_review | legitimacy_batch | upskill_report
                                                --  | interview_prep_deep | profile_expand | cover_letter
    job_id       TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    payload      TEXT NOT NULL DEFAULT '{}',    -- json, validated per-type at the API
    status       TEXT NOT NULL DEFAULT 'pending', -- pending | running | done | error
    result_ref   TEXT,                          -- e.g. cv_review:3, jobs:12, message:7
    error        TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_intents_status ON intents(status, created_at);
CREATE INDEX IF NOT EXISTS idx_intents_job ON intents(job_id);
```

- [ ] **Step 4: Implementar `engine/intents.py`:**

```python
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
        "id", "title", "company", "location", "is_remote", "workplace_type", "url",
        "apply_url", "salary_min", "salary_max", "salary_currency", "date_posted",
        "fit_score", "match_score", "state",
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
```

- [ ] **Step 5: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_intents.py -q` → `6 passed`.
- [ ] **Step 6: Suite completa verde** — `rtk uv run --group dev pytest -q` (la migración es aditiva; nada más cambia).
- [ ] **Step 7: Commit** — `rtk git add engine/db/schema.sql engine/intents.py tests/test_intents.py && rtk git commit -m "feat(intents): intent queue table + engine module (F4 §7.1)" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 2: API de intents (`POST /api/intents`, `GET /api/intents`, `GET /api/intents/{id}`)

**Files:**
- Modify: `dashboard/backend/main.py`
- Test: `tests/test_intents_api.py`

**Interfaces:**
- `POST /api/intents` (origin-guarded) body `{"type": str, "job_id": str | null, "payload": dict}` → `{"ok": true, "id": "in_..."}`; 400 si type desconocido o payload inválido para el type; 404 si `job_id`/`job_ids`/`interview_id` no existen.
- `GET /api/intents?status=pending` → `{"intents": [...], "pending": int}` (payload parseado; 400 si status inválido).
- `GET /api/intents/{intent_id}` → la fila, o 404.
- Modelos de payload por tipo (Pydantic, `extra="forbid"`): `CvReviewPayload{language?}`, `LegitimacyBatchPayload{job_ids: list[str] (1..100)}`, `UpskillPayload{states: list[str]}`, `InterviewPrepDeepPayload{interview_id: int, language?}`, `ProfileExpandPayload{github_user?, portfolio_url?, cert_names: list[str]}`, `CoverLetterPayload{language?}`.

- [ ] **Step 1: Test que falla**

```python
# tests/test_intents_api.py
"""Endpoints de la cola de intents (F4 §7.1): validación por tipo + origin guard."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job() -> str:
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        db.upsert_job(
            Job(source="greenhouse", source_job_id="1", title="Data Scientist",
                company="Acme", url="https://x/1")
        )
        return db.list_jobs()[0]["id"]


def test_enqueue_unknown_type_is_400(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/intents", json={"type": "world_peace", "payload": {}})
    assert r.status_code == 400


def test_enqueue_cv_review_requires_existing_job(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/intents", json={"type": "cv_review", "job_id": "nope"})
    assert r.status_code == 404


def test_enqueue_cv_review_happy_path_and_listing(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        r = client.post(
            "/api/intents", json={"type": "cv_review", "job_id": jid, "payload": {}}
        )
        assert r.status_code == 200 and r.json()["ok"] is True
        iid = r.json()["id"]
        lst = client.get("/api/intents?status=pending").json()
        assert lst["pending"] == 1
        assert [i["id"] for i in lst["intents"]] == [iid]
        one = client.get(f"/api/intents/{iid}")
        assert one.status_code == 200 and one.json()["type"] == "cv_review"


def test_enqueue_legitimacy_batch_validates_job_ids(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        bad = client.post(
            "/api/intents",
            json={"type": "legitimacy_batch", "payload": {"job_ids": []}},
        )
        assert bad.status_code == 400  # lista vacía
        ghost = client.post(
            "/api/intents",
            json={"type": "legitimacy_batch", "payload": {"job_ids": [jid, "nope"]}},
        )
        assert ghost.status_code == 404
        ok = client.post(
            "/api/intents",
            json={"type": "legitimacy_batch", "payload": {"job_ids": [jid]}},
        )
        assert ok.status_code == 200


def test_enqueue_rejects_extra_payload_keys(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        r = client.post(
            "/api/intents",
            json={"type": "cv_review", "job_id": jid, "payload": {"rm": "-rf"}},
        )
    assert r.status_code == 400


def test_enqueue_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/intents",
            json={"type": "upskill_report", "payload": {}},
            headers={"Origin": "https://evil.example"},
        )
    assert r.status_code == 403


def test_intents_list_invalid_status_is_400(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.get("/api/intents?status=bogus").status_code == 400
        assert client.get("/api/intents/unknown-id").status_code == 404
```

- [ ] **Step 2: Correr, esperar FAIL** — `rtk uv run --group dev pytest tests/test_intents_api.py -q` → 404 (ruta no existe) en todos.

- [ ] **Step 3: Implementar en `dashboard/backend/main.py`.** Imports: añadir `from pydantic import BaseModel, ConfigDict, Field, ValidationError` (ampliando el import existente de `pydantic`) y `from engine import intents` junto a los imports de `engine`. Luego, tras los modelos Pydantic existentes:

```python
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
```

y los endpoints (junto al bloque de discover):

```python
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
    if body.type in _JOB_SCOPED_INTENTS:
        if not body.job_id or not db.get_job(body.job_id):
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
```

- [ ] **Step 4: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_intents_api.py -q` → `7 passed`.
- [ ] **Step 5: Suite + lint** — `rtk uv run --group dev pytest -q` y `uv run ruff check dashboard/backend/main.py`.
- [ ] **Step 6: Commit** — `rtk git add dashboard/backend/main.py tests/test_intents_api.py && rtk git commit -m "feat(api): intent queue endpoints with per-type payload validation" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 3: CLI `atlas intents` (list/start/context/complete/fail) + `atlas cv dump`

**Files:**
- Modify: `engine/cli.py`
- Modify: `engine/cv/review.py` (se crea aquí solo con `dump_tailored_cv`; el resto llega en Task 7)
- Test: `tests/test_intents.py` (ampliar), `tests/test_cv_review.py` (crear)

**Interfaces:**
- CLI: `atlas intents list [--status pending|running|done|error|all] [--json]`, `atlas intents start <id>`, `atlas intents context <id> --json`, `atlas intents complete <id> --result-file <path.json>`, `atlas intents fail <id> --error <msg>`.
- `engine.cv.review.dump_tailored_cv(db: DB, job_id: str, language: str | None = None) -> Path` — escribe `data/outbox/<job_id>/cv_for_review.yaml` (dump YAML del CV tailoreado, `width=1000` para 1 línea por bullet) y devuelve la ruta.
- CLI: `atlas cv dump <job_id>` — expone lo anterior (lo usa también la verificación visual de PDF del SKILL).

- [ ] **Step 1: Test que falla (dump)**

```python
# tests/test_cv_review.py
"""engine/cv/review.py — dump del CV tailoreado + (Task 7) apply_edit/resolve_flag."""

from __future__ import annotations

import pytest
import yaml

import engine.paths as paths
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    with DB(tmp_path / "t.db") as d:
        d.upsert_job(
            Job(source="greenhouse", source_job_id="1", title="Data Scientist",
                company="Acme", url="https://x/1",
                description="We need Python and SQL for analytics.")
        )
        yield d


def test_dump_tailored_cv_writes_parseable_yaml(db):
    from engine.cv.review import dump_tailored_cv

    jid = db.list_jobs()[0]["id"]
    path = dump_tailored_cv(db, jid)
    assert path.name == "cv_for_review.yaml"
    cv = yaml.safe_load(path.read_text())
    assert isinstance(cv, dict)  # estructura de master_cv tailoreada


def test_dump_unknown_job_raises(db):
    from engine.cv.review import dump_tailored_cv

    with pytest.raises(ValueError):
        dump_tailored_cv(db, "nope")
```

- [ ] **Step 2: Correr, esperar FAIL** — `rtk uv run --group dev pytest tests/test_cv_review.py -q`.

- [ ] **Step 3: Crear `engine/cv/review.py` (versión Task 3):**

```python
"""CV/carta review (F4 §7.2) — dump del CV tailoreado para el reviewer del brain,
y aplicación mecánica de sus edits/flags (Task 7). El LLM nunca escribe archivos:
propone strings; aquí se validan y aplican deterministamente."""

from __future__ import annotations

from pathlib import Path

import yaml

import engine.paths as paths
from engine.config import load_master_cv, load_ontology
from engine.cv import tailor as tailor_mod
from engine.db.models import DB


def dump_tailored_cv(db: DB, job_id: str, language: str | None = None) -> Path:
    """Escribe el CV tailoreado (dict → YAML) a data/outbox/<job_id>/cv_for_review.yaml.

    width=1000 mantiene cada bullet en UNA línea: los old_string del reviewer se copian
    verbatim de este texto y el apply hace replace exacto (Task 7).
    `language` no cambia el dump (el tailor es agnóstico); se acepta para simetría de API.
    """
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    result = tailor_mod.tailor(load_master_cv(), job, load_ontology())
    out = paths.OUTBOX_DIR / job_id / "cv_for_review.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(result.cv, allow_unicode=True, sort_keys=False, width=1000))
    return out
```

- [ ] **Step 4: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_cv_review.py -q` → `2 passed`.

- [ ] **Step 5: CLI.** En `engine/cli.py`, junto a los otros sub-typers:

```python
# ── intents (F4) — la cola que el brain drena como paso 0 de "corre atlas" ─────
intents_app = typer.Typer(help="Cola de intents (handoff web → brain). El brain la drena.")
app.add_typer(intents_app, name="intents")


@intents_app.command("list")
def intents_list(
    status: str = typer.Option("pending", help="pending|running|done|error|all"),
    json_out: bool = typer.Option(False, "--json", help="JSON para el brain."),
) -> None:
    """List queued intents (the brain drains these as step 0)."""
    import json as _json

    from engine import intents as eng_intents

    with _db() as db:
        rows = eng_intents.list_intents(db, status=None if status == "all" else status)
    if json_out:
        print(_json.dumps(rows, indent=2, ensure_ascii=False))
        return
    table = Table(title=f"Intents ({status})")
    for col in ("id", "type", "job", "status", "created", "result/error"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r["id"], r["type"], (r.get("job_id") or "—")[:18], r["status"],
            (r.get("created_at") or "")[:16], (r.get("result_ref") or r.get("error") or "")[:30],
        )
    console.print(table)


@intents_app.command("start")
def intents_start(intent_id: str) -> None:
    """Mark an intent running and print which prompt file drives it."""
    from engine import intents as eng_intents

    with _db() as db:
        try:
            eng_intents.mark_running(db, intent_id)
            row = eng_intents.get_intent(db, intent_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    console.print(
        f"[green]✓[/] {intent_id} → running. Prompt: "
        f"brain/prompts/{eng_intents.PROMPT_FILES[row['type']]}"
    )


@intents_app.command("context")
def intents_context(intent_id: str) -> None:
    """Print the deterministic context JSON the brain needs for this intent."""
    import json as _json

    from engine import intents as eng_intents

    with _db() as db:
        try:
            ctx = eng_intents.context_for(db, intent_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    print(_json.dumps(ctx, indent=2, ensure_ascii=False))


@intents_app.command("complete")
def intents_complete(
    intent_id: str,
    result_file: str = typer.Option(..., "--result-file", help="JSON con el resultado."),
) -> None:
    """Validate the brain's result JSON and write it to the destination tables."""
    import json as _json
    from pathlib import Path

    from engine import intents as eng_intents

    p = Path(result_file).expanduser()
    if not p.exists():
        console.print(f"[red]✗[/] no existe: {p}")
        raise typer.Exit(2)
    try:
        result = _json.loads(p.read_text())
    except _json.JSONDecodeError as e:
        console.print(f"[red]✗ JSON inválido:[/] {e}")
        raise typer.Exit(2) from None
    with _db() as db:
        try:
            ref = eng_intents.apply_result(db, intent_id, result)
        except ValueError as e:
            console.print(f"[red]✗ resultado rechazado:[/] {e}\n  (el intent sigue running — corrige el JSON y reintenta)")
            raise typer.Exit(2) from None
    console.print(f"[green]✓[/] {intent_id} → done ({ref})")


@intents_app.command("fail")
def intents_fail(
    intent_id: str,
    error: str = typer.Option(..., "--error", help="Por qué no se pudo ejecutar."),
) -> None:
    """Mark an intent as errored (visible in the web panel)."""
    from engine import intents as eng_intents

    with _db() as db:
        try:
            eng_intents.mark_error(db, intent_id, error)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    console.print(f"[yellow]![/] {intent_id} → error registrado")
```

y el sub-typer de CV:

```python
cv_app = typer.Typer(help="Utilidades de CV para el brain.")
app.add_typer(cv_app, name="cv")


@cv_app.command("dump")
def cv_dump(job_id: str) -> None:
    """Dump the tailored CV YAML for a job (input for the LLM reviewer / PDF fixes)."""
    from engine.cv.review import dump_tailored_cv

    with _db() as db:
        try:
            path = dump_tailored_cv(db, job_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    console.print(f"[green]✓[/] {path}")
```

- [ ] **Step 6: Test del ciclo CLI-nivel-engine** (ampliar `tests/test_intents.py`):

```python
def test_context_for_includes_prompt_file_and_job(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="greenhouse", source_job_id="9", title="ML Engineer",
            company="Beta", url="https://x/9", description="d" * 9000)
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {"language": "en"}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["prompt_file"] == "brain/prompts/cover_letter.md"
    assert ctx["job"]["id"] == jid
    assert len(ctx["job"]["description"]) == 6000  # recortado


def test_apply_result_requires_running_and_known_writer(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):  # aún pending
        intents.apply_result(db, iid, {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):  # writer no registrado todavía (llega en Task 10)
        intents.apply_result(db, iid, {})
    assert intents.get_intent(db, iid)["status"] == "running"  # no se corrompe el estado
```

- [ ] **Step 7: Correr todo** — `rtk uv run --group dev pytest tests/test_intents.py tests/test_cv_review.py -q` → `10 passed`. Smoke manual: `uv run atlas intents list` (tabla vacía) y `uv run atlas intents list --json` (`[]`).
- [ ] **Step 8: Commit** — `rtk git add engine/cli.py engine/cv/review.py tests/test_intents.py tests/test_cv_review.py && rtk git commit -m "feat(cli): atlas intents list/start/context/complete/fail + cv dump" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 4: Brain paso 0 — drenaje de intents (`run_brain.py` + `SKILL.md`, trigger "corre atlas")

**Files:**
- Modify: `brain/run_brain.py` (summary + brief muestran la cola)
- Modify: `brain/SKILL.md` (paso 0 de drenaje; trigger "corre atlas")
- Test: `tests/test_brain_intents.py`

**Interfaces:**
- `brain.run_brain.run(...)` → el dict summary gana `"intents_pending": list[{"id","type","job_id"}]` (lo que quedó pendiente al terminar la parte determinista — el drenaje real lo hace la sesión de Claude siguiendo el SKILL).
- `MORNING_BRIEF.md` gana la sección `## 🤖 Tareas del Brain en cola` cuando hay pendientes.

- [ ] **Step 1: Test que falla**

```python
# tests/test_brain_intents.py
"""El brain reporta la cola de intents en el summary y el morning brief (F4 paso 0)."""

from __future__ import annotations

import engine.paths as paths
from engine import intents
from engine.db.models import DB


def test_run_reports_pending_intents_in_summary_and_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    from brain.run_brain import run

    with DB(tmp_path / "t.db") as db:
        intents.enqueue(db, "upskill_report", {})
        summary = run(db, do_discover=False)
    assert [i["type"] for i in summary["intents_pending"]] == ["upskill_report"]
    brief = (tmp_path / "MORNING_BRIEF.md").read_text()
    assert "Tareas del Brain en cola" in brief
    assert "upskill_report" in brief


def test_run_with_empty_queue_has_no_intents_section(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    from brain.run_brain import run

    with DB(tmp_path / "t.db") as db:
        summary = run(db, do_discover=False)
    assert summary["intents_pending"] == []
    assert "Tareas del Brain en cola" not in (tmp_path / "MORNING_BRIEF.md").read_text()
```

- [ ] **Step 2: Correr, esperar FAIL** — `rtk uv run --group dev pytest tests/test_brain_intents.py -q` → `KeyError: 'intents_pending'`.

- [ ] **Step 3: Implementar en `brain/run_brain.py`.** Import: `from engine import intents as intent_queue`. En `run()`, justo antes de `summary["downtime_hours"] = ...`:

```python
    # F4 paso 0 (parte determinista): reportar la cola. El drenaje REAL lo hace la sesión
    # de Claude que invoca esto (SKILL.md paso 0) — aquí solo se hace visible lo pendiente.
    summary["intents_pending"] = [
        {"id": i["id"], "type": i["type"], "job_id": i["job_id"]}
        for i in intent_queue.list_pending(db)
    ]
```

En `write_morning_brief()`, tras el bloque de `health`:

```python
    pend = summary.get("intents_pending") or []
    if pend:
        lines += ["", "## 🤖 Tareas del Brain en cola (pídele a Claude: `corre atlas`)"]
        lines += [
            f"- `{p['id']}` · {p['type']}" + (f" · job {p['job_id']}" if p["job_id"] else "")
            for p in pend
        ]
```

- [ ] **Step 4: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_brain_intents.py -q` → `2 passed`.

- [ ] **Step 5: Reescribir `brain/SKILL.md`** con este contenido completo (reemplaza el archivo; conserva la doctrina existente y añade el paso 0 + trigger):

```markdown
---
name: atlas-job-brain
description: Daily local job-search brain — drain the web-queued intent queue, then discover, score, tailor CVs, draft outreach, update the tracker. Sends nothing. Trigger phrase: "corre atlas".
---

# Atlas — Daily Job-Search Brain

You are the daily brain for **Atlas**, a personal, local job-search cockpit. This runs as a
Claude Cowork/Desktop scheduled task or an interactive Claude Code session on the user's
**subscription** (NOT `claude -p`, NOT the Agent SDK). When the user says **"corre atlas"**,
execute ALL the steps below. Keep it short and deterministic. **You never send or submit
anything** — the human reviews and sends from the dashboard. Today's work is idempotent;
safe to re-run.

## Steps

0. **Drain the intent queue (web → brain handoff).** The dashboard queues LLM work as
   `intents`. This step is the whole reason the user said "corre atlas" — never skip it.
   ```bash
   cd /path/to/atlas && uv run atlas --profile owner intents list --status pending --json
   ```
   For EACH pending intent, in order:
   1. `uv run atlas --profile owner intents start <id>` — it prints the prompt file.
   2. `uv run atlas --profile owner intents context <id>` — the deterministic context JSON
      (job, CV dump path, gaps, previous reports…). Everything you may claim comes from
      here or from the files it points to. Nothing else exists.
   3. Read `brain/prompts/style_rules.md` first if the intent writes prose, then the
      intent's own prompt (`brain/prompts/<type>.md`) and follow it EXACTLY.
   4. Write the result JSON (schema at the bottom of each prompt) to a scratch file.
   5. `uv run atlas --profile owner intents complete <id> --result-file <scratch.json>`
      - Validation error (exit 2): fix the JSON and retry — the intent stays `running`.
      - Task impossible (job vanished, no data): `uv run atlas --profile owner intents fail <id> --error "<why>"`.

1. **Run the deterministic pipeline.**
   ```bash
   cd /path/to/atlas && uv run atlas --profile owner brain --limit 8 --language en --json
   ```
   `--profile owner` pins the auto-run to the owner's profile. The brain refuses to run for
   any non-owner profile. This discovers, scores, shortlists, tailors CVs (DOCX+PDF), drafts
   outreach, writes per-job `package.md`, updates `data/atlas.db` and
   `data/outbox/MORNING_BRIEF.md`.

2. **Read the brief.** Open `data/outbox/MORNING_BRIEF.md`. Mention any downtime warning
   first. If it still lists queued intents, go back to step 0.

3. **(Optional) Sharpen the top 3.** For the 3 highest-fit *ready* jobs you may lightly
   improve the drafted messages in their `package.md` — applying
   `brain/prompts/style_rules.md` (Tier 1 everywhere; Tier 2 voice ONLY for letters/
   outreach, never the CV). Only facts already in `profile/master_cv.yaml`. **Never invent
   metrics, skills, or experience.**

4. **Visual PDF check (every job prepared today).** For each entry in the run summary's
   `prepared` list, Read `data/outbox/<job_id>/cv_<lang>.pdf` and verify:
   - page count is exactly what `config/cv_layout.yaml` targets (default: ≤ 2 pages; a 3rd
     page with under 5 lines is a fail),
   - no section heading orphaned at the bottom of a page,
   - fonts/sizes consistent (no mixed families).
   If a check fails: `uv run atlas --profile owner cv dump <job_id>`, edit the dumped
   `data/outbox/<job_id>/cv_for_review.yaml` (trim the least JD-relevant highlights — never
   reword facts), re-render and re-check:
   ```bash
   uv run python -c "
   import yaml
   from engine.db.models import DB
   from engine.cv.build import build_for_job
   cv = yaml.safe_load(open('data/outbox/<job_id>/cv_for_review.yaml'))
   with DB() as db: build_for_job(db, '<job_id>', language='<lang>', cv_override=cv)"
   ```
   Iterate at most 2 times; if still failing, report it in your summary instead of looping.

5. **(Optional) Create Gmail drafts — never send.** Unchanged: for top ready jobs with a
   known recruiter/HM/referral email, use the Gmail connector (`create_draft`) to create a
   DRAFT. Skip jobs with no email. No attachments.

6. **Report.** Post a short Spanish summary: intents drained (type + outcome each), how many
   new, how many ready to send, the top 3 opportunities (apply link + referral), and any
   source-health problems.

## Hard rules
- **Send nothing. Submit nothing. No browser automation.** Drafts only.
- Stay on the user's subscription: no `claude -p`, no Agent SDK, no API key.
- Only act on what the pipeline/context produced; never invent jobs, contacts, or numbers.
- Results reach the DB ONLY through `atlas intents complete` — never hand-written SQL.
- If a command fails, report the error and stop — do not improvise a workaround.
```

- [ ] **Step 6: Suite completa** — `rtk uv run --group dev pytest -q` verde.
- [ ] **Step 7: Commit** — `rtk git add brain/run_brain.py brain/SKILL.md tests/test_brain_intents.py && rtk git commit -m "feat(brain): step 0 drains the intent queue; SKILL triggered by 'corre atlas'" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 5: Panel "Tareas del Brain" + diálogo de confirmación (frontend)

**Files:**
- Modify: `dashboard/frontend/src/api.ts`
- Create: `dashboard/frontend/src/components/BrainTasksPanel.tsx`
- Create: `dashboard/frontend/src/components/IntentConfirmDialog.tsx`
- Modify: shell — `dashboard/frontend/src/App.tsx` hoy; si F1 ya extrajo el shell (p. ej. `src/routes/Shell.tsx`), montar ahí
- Test: `dashboard/frontend/src/components/BrainTasksPanel.test.tsx`

**Interfaces:**
- `api.intents(status?: string) => Promise<{ intents: Intent[]; pending: number }>`
- `api.enqueueIntent(type: string, payload?: Record<string, unknown>, jobId?: string) => Promise<{ ok: boolean; id: string }>`
- `<BrainTasksPanel />` — botón con badge de pendientes (poll 30 s) + Sheet con la cola y el bloque copiable.
- `<IntentConfirmDialog buttonLabel title what produces where type jobId? payload? onQueued? />` — mini-diálogo estándar de TODOS los botones LLM (qué hace / qué produce / dónde aparece).
- `BRAIN_PHRASE = "Abre Claude Code en ~/dev/personal/atlas y di: corre atlas"` (export const, única frase universal).

- [ ] **Step 1: api.ts.** Añadir el tipo y los métodos:

```ts
export type Intent = {
  id: string;
  type: string;
  job_id?: string | null;
  payload?: Record<string, unknown>;
  status: "pending" | "running" | "done" | "error";
  result_ref?: string | null;
  error?: string | null;
  created_at: string;
  completed_at?: string | null;
};
```

y dentro de `export const api = { ... }`:

```ts
  intents: (status?: string) =>
    get<{ intents: Intent[]; pending: number }>(
      `/api/intents${status ? `?status=${status}` : ""}`,
    ),
  enqueueIntent: (type: string, payload?: Record<string, unknown>, jobId?: string) =>
    post<{ ok: boolean; id: string }>("/api/intents", {
      type,
      job_id: jobId,
      payload: payload ?? {},
    }),
```

- [ ] **Step 2: Test que falla**

```tsx
// dashboard/frontend/src/components/BrainTasksPanel.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BrainTasksPanel } from "./BrainTasksPanel";

const payload = {
  intents: [
    {
      id: "in_abc123",
      type: "cv_review",
      job_id: "j1",
      status: "pending",
      created_at: "2026-07-04T09:00:00Z",
    },
  ],
  pending: 1,
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })),
  );
});

describe("BrainTasksPanel", () => {
  it("muestra el badge de pendientes y la frase universal al abrir", async () => {
    render(<BrainTasksPanel />);
    expect(await screen.findByText("1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /tareas del brain/i }));
    expect(await screen.findByText(/corre atlas/)).toBeInTheDocument();
    expect(screen.getByText("Revisión LLM de CV/carta")).toBeInTheDocument();
    expect(screen.getByText("pendiente")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Correr, esperar FAIL** — `npm --prefix dashboard/frontend test` → módulo `./BrainTasksPanel` no existe.

- [ ] **Step 4: Implementar `BrainTasksPanel.tsx`:**

```tsx
import { BrainCircuit, Check, Copy, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Intent } from "../api";
import { copy } from "../lib";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { ScrollArea } from "./ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "./ui/sheet";

export const INTENT_LABEL: Record<string, string> = {
  cv_review: "Revisión LLM de CV/carta",
  legitimacy_batch: "Legitimidad de vacantes",
  upskill_report: "Análisis de gaps (upskill)",
  interview_prep_deep: "Prep profundo de entrevista",
  profile_expand: "Expandir perfil",
  cover_letter: "Carta personalizada",
};

const STATUS_ES: Record<Intent["status"], string> = {
  pending: "pendiente",
  running: "en curso",
  done: "lista",
  error: "error",
};

// La ÚNICA frase que el usuario debe aprenderse (spec §7.1). El SKILL del brain hace el resto.
export const BRAIN_PHRASE = "Abre Claude Code en ~/dev/personal/atlas y di: corre atlas";

export function BrainTasksPanel() {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Intent[]>([]);
  const [pending, setPending] = useState(0);
  const [copied, setCopied] = useState(false);
  const refresh = useCallback(() => {
    api
      .intents()
      .then((r) => {
        setRows(r.intents);
        setPending(r.pending);
      })
      .catch(() => {});
  }, []);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 30_000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        aria-label="Tareas del Brain"
        onClick={() => {
          refresh();
          setOpen(true);
        }}
      >
        <BrainCircuit className="size-3.5" /> Tareas del Brain
        {pending > 0 && <Badge className="ml-1">{pending}</Badge>}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="w-[420px] sm:max-w-[420px]">
          <SheetTitle>Tareas del Brain</SheetTitle>
          <SheetDescription>
            Trabajos que necesitan LLM. La web solo los encola ($0): se ejecutan cuando corres
            el brain en Claude Code, y los resultados aparecen aquí y en cada vacante.
          </SheetDescription>
          <Card className="mt-3 space-y-2 p-3.5 text-sm">
            <div className="text-caption text-muted-foreground uppercase">Para ejecutarlas</div>
            <pre className="rounded-lg bg-background/60 p-2.5 font-mono text-[0.78rem] whitespace-pre-wrap">
              {BRAIN_PHRASE}
            </pre>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                await copy(BRAIN_PHRASE);
                setCopied(true);
                setTimeout(() => setCopied(false), 1200);
              }}
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{" "}
              {copied ? "Copiado" : "Copiar instrucción"}
            </Button>
          </Card>
          <div className="mt-3 flex items-center justify-between">
            <div className="text-caption text-muted-foreground uppercase">
              Cola ({rows.length})
            </div>
            <Button variant="secondary" size="icon-sm" aria-label="Refrescar" onClick={refresh}>
              <RefreshCw className="size-3.5" />
            </Button>
          </div>
          <ScrollArea className="mt-2 max-h-[55vh]">
            <div className="space-y-2 pr-2">
              {rows.length === 0 && (
                <div className="text-[0.8rem] text-muted-foreground">
                  Sin tareas. Encólalas desde los botones LLM de cada vacante.
                </div>
              )}
              {rows.map((it) => (
                <Card key={it.id} className="p-2.5 text-[0.8rem]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{INTENT_LABEL[it.type] || it.type}</span>
                    <Badge variant="secondary">{STATUS_ES[it.status]}</Badge>
                  </div>
                  <div className="mt-0.5 text-muted-foreground">
                    {it.job_id ? `Vacante ${it.job_id} · ` : ""}
                    {(it.created_at || "").slice(0, 16).replace("T", " ")}
                  </div>
                  {it.status === "done" && it.result_ref && (
                    <div className="mt-1 text-muted-foreground">→ {it.result_ref}</div>
                  )}
                  {it.error && <div className="mt-1 text-[0.76rem]">⚠︎ {it.error}</div>}
                </Card>
              ))}
            </div>
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </>
  );
}
```

- [ ] **Step 5: Implementar `IntentConfirmDialog.tsx`** (el mini-diálogo obligatorio de cada botón LLM — spec §7.1):

```tsx
import { Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./ui/dialog";

type Props = {
  buttonLabel: string;
  title: string;
  what: string; // qué hace
  produces: string; // qué producirá
  where: string; // dónde aparecerá el resultado
  type: string;
  jobId?: string;
  payload?: Record<string, unknown>;
  onQueued?: (intentId: string) => void;
};

// Todo botón LLM de la web pasa por aquí: explica qué hace, qué produce y dónde aparecerá,
// y deja claro que NO corre ahora — queda en la cola del brain (guided handoff, $0).
export function IntentConfirmDialog({
  buttonLabel,
  title,
  what,
  produces,
  where,
  type,
  jobId,
  payload,
  onQueued,
}: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function queue() {
    setBusy(true);
    try {
      const r = await api.enqueueIntent(type, payload, jobId);
      toast.success("Encolado. Corre el brain para ejecutarlo (panel Tareas del Brain).");
      onQueued?.(r.id);
      setOpen(false);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <Sparkles className="size-3.5" /> {buttonLabel}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-2 text-sm">
              <p>
                <b>Qué hace:</b> {what}
              </p>
              <p>
                <b>Qué produce:</b> {produces}
              </p>
              <p>
                <b>Dónde aparece:</b> {where}
              </p>
              <p className="text-muted-foreground">
                No corre ahora: queda en la cola del brain. Para ejecutarla, abre Claude Code
                en <code>~/dev/personal/atlas</code> y di <code>corre atlas</code>.
              </p>
            </div>
          </DialogDescription>
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" disabled={busy} onClick={queue}>
              Encolar para el brain
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 6: Montar en el shell.** En el header del app shell (hoy `App.tsx`: el `<header>` sticky con el logo y las acciones; post-F1: el componente de shell equivalente), añadir `<BrainTasksPanel />` junto al grupo de botones existente (al lado del botón del brief/settings), con su import. Es un componente autocontenido: no necesita props ni estado del shell.
- [ ] **Step 7: Correr, esperar PASS** — `npm --prefix dashboard/frontend test` verde; `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend run lint`.
- [ ] **Step 8: QA visual** — levantar backend + frontend (preview tools), abrir el panel, verificar badge/frase/copy.
- [ ] **Step 9: Commit** — `rtk git add dashboard/frontend/src/api.ts dashboard/frontend/src/components/BrainTasksPanel.tsx dashboard/frontend/src/components/IntentConfirmDialog.tsx dashboard/frontend/src/components/BrainTasksPanel.test.tsx dashboard/frontend/src/App.tsx && rtk git commit -m "feat(ui): Tareas del Brain panel + universal intent confirm dialog" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 6: Reglas transversales de escritura (`brain/prompts/style_rules.md`)

**Files:**
- Create: `brain/prompts/style_rules.md`

**Interfaces:**
- Referenciado por: `brain/SKILL.md` (pasos 0.3 y 3 — ya escrito en Task 4) y por los prompts `cv_review.md`, `cover_letter.md`, `upskill.md`, `interview_prep_deep.md` (Tasks 7-11). Es el paso previo de TODA generación de prosa del brain.

- [ ] **Step 1: Crear `brain/prompts/style_rules.md`** con este contenido completo:

```markdown
# Atlas brain — Style rules (transversal)

Read this BEFORE writing any prose (CV text, cover letters, outreach, reports, prep docs).
Every other prompt in this directory assumes you have. **Accuracy always wins over style**:
if a stylistic improvement changes the meaning of a claim, keep the ugly true version.

## Tier 1 — Anti-slop (applies to EVERYTHING you write)

- No em-dashes (—). Use a period or a comma.
- Banned words/phrases: "passionate", "results-driven", "proven track record", "dynamic",
  "synergy", "leverage" (as a verb), "cutting-edge", "fast-paced environment",
  "team player", "go-getter", "delve", "showcase", "seamless", "game-changer",
  "spearheaded" (allowed at most once per document), "robust" (unless describing a tested
  system property).
- No negative parallelisms. Never "not just X, but Y", "it's not about X, it's about Y",
  "more than a Z".
- No filler intensifiers: "very", "extremely", "incredibly", "truly", "highly".
- One idea per sentence. If a sentence carries two verbs and a subordinate clause, split it.
- Concrete beats abstract: name the system, the tool, the number — or say nothing.

## Tier 2 — Conversational voice (ONLY cover letters, outreach, LinkedIn notes)

NEVER apply this tier to the CV or any ATS-parsed document.

- Contractions are good ("I've", "I'm", "don't"; in Spanish: natural spoken register).
- Human hedging is allowed where honest ("I haven't run X in production, but I've built Y
  which shares its core problem").
- Write like a competent person talking to another competent person, not a press release.
- CV/ATS documents stay in neutral, compact, factual register: no contractions, no first
  person, no adjectives without a number nearby.

## Recruiter-side risk map (run BEFORE drafting any CV/letter)

Before writing, build a private scratch table of the recruiter's likely doubts for THIS job
and THIS profile:

| Doubt type | The doubt in one line | Evidence we have | Fix in the draft |
| --- | --- | --- | --- |

Doubt types to check every time: **stack** (missing or adjacent tools), **seniority** (over/
under-qualified), **domain** (industry mismatch), **logistics** (location, timezone, visa,
salary), **generic** (does the application smell like spray-and-pray?).

Every "Fix" must actually appear in the draft. Doubts with no evidence are handled by honest
framing of ADJACENT experience — never by invention, never by hiding.

## Six-second gate

The top third of page 1 of the CV must make the fit impossible to miss for THIS posting:
the exact target title, 2-3 JD-matching skills, and one quantified outcome. If a recruiter
reads only that and stops, they should already want the screen. If the top third fails this
test, fix it before anything else.

## Bullet formula

Action verb + system/scope + tool + outcome + proof.
Shape: "Built <system> covering <scope> with <tool>, cutting <metric> by <X%> (<where it
can be verified>)". Metrics are READ from the CV at evaluation time — never from memory,
never rounded up, never merged across projects.
```

- [ ] **Step 2: Verificar** que `brain/SKILL.md` (Task 4) referencia `brain/prompts/style_rules.md` en los pasos 0.3 y 3 (ya lo hace; si Task 4 aún no corrió, este archivo simplemente queda listo).
- [ ] **Step 3: Commit** — `rtk git add brain/prompts/style_rules.md && rtk git commit -m "feat(brain): transversal style rules (voice DNA two tiers + risk map + six-second gate)" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 7: `cv_review` — reviewer hiring-manager proxy (prompt + tabla + apply-edit/flags + UI)

**Files:**
- Create: `brain/prompts/cv_review.md`
- Modify: `engine/db/schema.sql` (tabla `cv_reviews`), `engine/db/models.py` (métodos)
- Modify: `engine/intents.py` (context builder + result writer)
- Modify: `engine/cv/review.py` (`apply_edit`, `resolve_flag`)
- Modify: `dashboard/backend/main.py` (3 endpoints)
- Create: `dashboard/frontend/src/components/CvReviewPanel.tsx`; Modify: `api.ts`, `DetailDrawer.tsx`
- Test: `tests/test_cv_review.py`, `tests/test_intents.py`, `tests/test_intents_api.py` (ampliar)

**Interfaces:**
- Tabla `cv_reviews(id INTEGER pk, intent_id TEXT, job_id TEXT NOT NULL, cv_version_id INTEGER, edits TEXT json, critique TEXT json, flags TEXT json, created_at TEXT)`.
- `DB.add_cv_review(job_id: str, *, intent_id: str | None, cv_version_id: int | None, edits: list, critique: dict, flags: list) -> int`
- `DB.get_cv_review(review_id: int) -> dict | None`; `DB.cv_reviews_for(job_id: str) -> list[dict]` (edits/critique/flags parseados)
- `DB.set_cv_review_edits(review_id: int, edits: list) -> None`; `DB.set_cv_review_flags(review_id: int, flags: list) -> None`
- `review.EDIT_FILES = ("cv", "cover_letter", "recruiter", "hiring_manager")`
- `review.apply_edit(db: DB, review_id: int, index: int) -> dict` — file=="cv": replace exacto sobre `cv_for_review.yaml` (old_string debe aparecer EXACTAMENTE 1 vez) + `build_for_job(cv_override=...)` re-renderiza DOCX/PDF; file==kind de mensaje: replace sobre el body del último mensaje de ese kind. Marca `edit["applied"]=True` + `applied_ref`.
- `review.resolve_flag(db: DB, review_id: int, index: int, action: Literal["keep","soften","drop"]) -> dict` — keep: solo anota; soften: sustituye el bullet por `flag["softened"]` (estructural, sobre el YAML parseado); drop: elimina el bullet; soften/drop re-renderizan.
- Writer `_write_cv_review(db, intent, result) -> "cv_review:<id>"` — exige `critique` con las 4 categorías, `edits[].file ∈ EDIT_FILES`, `flags[].classification ∈ ("OK","Flag","Never")`.
- Endpoints: `GET /api/jobs/{job_id}/cv-reviews`; `POST /api/cv-reviews/{id}/apply-edit` body `{"index": int}`; `POST /api/cv-reviews/{id}/resolve-flag` body `{"index": int, "action": "keep"|"soften"|"drop"}` (ambos origin-guarded).
- `api.cvReviews(jobId)`, `api.applyCvReviewEdit(id, index)`, `api.resolveCvReviewFlag(id, index, action)`; tipo `CvReview`.

- [ ] **Step 1: Prompt.** Crear `brain/prompts/cv_review.md` completo:

```markdown
# CV/letter reviewer — hiring manager proxy

You are a REVIEWER with FRESH context: if you are the main brain session, spawn this review
as a subagent (Agent tool) so the drafter's context does not leak into the review. Persona:
the hiring manager for this exact role. You are skeptical, busy, and deciding in minutes
whether this candidate gets a screen.

## Inputs

From `uv run atlas --profile owner intents context <id>`:
- `cv_yaml` + `cv_yaml_path` — the tailored CV as YAML text (the draft under review).
- `messages` — the drafted cover letter / recruiter / hiring-manager messages, inline.
- `job` — title, company, description, url.
- `match_missing` — JD keywords the CV does not evidence (deterministic).
- `master_cv_path` — Read this file. It is the EXCLUSIVE source of truth for what the
  candidate can claim. Anything not in it does not exist.

Before reviewing: research the company on the web (site, engineering blog, recent news,
product pages). RE-VERIFY every company fact you plan to use in a suggestion — never rely
on memory. A fact you cannot verify right now is a fact you do not use.

Read `brain/prompts/style_rules.md` first; apply Tier 1 to every string you propose
(Tier 2 additionally to letter/outreach edits). Run the recruiter-side risk map and the
six-second gate from that file against the draft — their findings feed the critique.

## Non-negotiable rules (anti-fabrication)

1. Sources of truth are EXCLUSIVE: the master CV file + the provided context. Nothing else.
2. Keywords get REFORMULATED, never fabricated. A keyword from `match_missing` may only be
   added if the master CV evidences it under another name.
3. Tool-of-trade conflation is the most common fabrication pattern: "uses X" ≠ "built X".
   Never upgrade usage into authorship, contribution into ownership, or exposure into
   expertise.
4. Silence on a topic beats manufactured detail.
5. Metrics are read from the CV at evaluation time. Never invent one, never round one up,
   never merge two metrics into a better-sounding one.
6. Where there is a REAL gap: say so honestly in the critique and suggest how to frame
   ADJACENT experience — never how to hide the gap.

## Backtrack test (career-ops)

For EVERY bullet your edits reframe, ask: "could the candidate explain this in an interview
without walking anything back?" and classify:
- **OK** — fully defensible; ship the edit.
- **Flag** — defensible only with careful wording; a pointed follow-up could hurt. Ship the
  edit ONLY as a flag entry with a `softened` alternative — the human decides
  keep/soften/drop in the web.
- **Never** — indefensible. Do NOT propose the edit at all; mention what tempted you and
  why it is off-limits in the `reframing` critique instead.

## Output — exactly one JSON object (becomes `atlas intents complete <id> --result-file`)

```json
{
  "edits": [
    {
      "file": "cv",
      "old_string": "<copied VERBATIM from cv_yaml, unique in the file>",
      "new_string": "<replacement>",
      "reason": "<why, one line>"
    }
  ],
  "critique": {
    "missed_keywords": ["<JD keyword underused + where it could truthfully live>"],
    "company_angles": ["<verified company-specific angle + how to use it>"],
    "reframing": ["<actionable reframing grounded in the master CV>"],
    "tone_register": ["<tone/register issue vs the profile and style_rules.md>"]
  },
  "flags": [
    {
      "file": "cv",
      "bullet": "<the exact CURRENT bullet text (one highlight line from cv_yaml)>",
      "classification": "Flag",
      "reason": "<the interview question that would hurt>",
      "softened": "<the safer wording>"
    }
  ]
}
```

Hard constraints on the output:
- `file` ∈ `cv | cover_letter | recruiter | hiring_manager`. For `cv`, `old_string` must
  appear EXACTLY once in `cv_yaml` (the web applies it as a mechanical replacement). For
  message files, `old_string` must appear in that message's current body.
- All four critique categories are mandatory. If one is genuinely empty, write a single
  honest entry like "nothing found — the draft already covers this well". Never pad.
- Every flag needs `bullet` (a current highlight, verbatim), `classification`
  (`OK|Flag|Never`), `reason`, and `softened` (required when classification is `Flag`).
  `Never` entries mean you already refused the edit — include them so the human sees why.
- Write suggestion strings in the language of the draft (cv_yaml/messages), critique prose
  in the profile's language.
```

- [ ] **Step 2: Test que falla (writer + apply + flags).** Ampliar `tests/test_cv_review.py`:

```python
def _review_result() -> dict:
    return {
        "edits": [
            {
                "file": "cv",
                "old_string": "Data Scientist",
                "new_string": "Data Scientist, Analytics",
                "reason": "mirror the posting title",
            }
        ],
        "critique": {
            "missed_keywords": ["sql: ya está en skills, súbelo al summary"],
            "company_angles": ["Acme publica su stack en el blog — cita dbt"],
            "reframing": ["el bullet de ETL puede enmarcarse hacia analytics"],
            "tone_register": ["nada que señalar"],
        },
        "flags": [
            {
                "file": "cv",
                "bullet": "",  # se rellena en el test con un highlight real
                "classification": "Flag",
                "reason": "¿lideraste tú el proyecto o participaste?",
                "softened": "Contributed to the ETL redesign that cut runtime 40%",
            }
        ],
    }


def test_cv_review_writer_persists_and_marks_done(db):
    from engine import intents

    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cv_review", {}, job_id=jid)
    intents.mark_running(db, iid)
    result = _review_result()
    result["flags"] = []  # este test no ejercita flags
    ref = intents.apply_result(db, iid, result)
    assert ref.startswith("cv_review:")
    review = db.cv_reviews_for(jid)[0]
    assert review["critique"]["company_angles"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_cv_review_writer_rejects_missing_critique_category(db):
    from engine import intents

    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cv_review", {}, job_id=jid)
    intents.mark_running(db, iid)
    bad = _review_result()
    del bad["critique"]["tone_register"]
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, bad)
    assert intents.get_intent(db, iid)["status"] == "running"  # queda reintentable


def test_apply_edit_on_cv_rewrites_dump_and_rerenders(db):
    from engine.cv.review import apply_edit, dump_tailored_cv

    jid = db.list_jobs()[0]["id"]
    dump_path = dump_tailored_cv(db, jid)
    old = "Data Scientist"  # el label/target title siempre está en el dump
    assert dump_path.read_text().count(old) >= 1
    rid = db.add_cv_review(
        jid,
        intent_id=None,
        cv_version_id=None,
        edits=[{"file": "cv", "old_string": old, "new_string": "Lead Data Scientist",
                "reason": "t"}],
        critique={"missed_keywords": [], "company_angles": [], "reframing": [],
                  "tone_register": []},
        flags=[],
    )
    # old_string debe ser único: si aparece >1 vez, apply_edit debe rechazarlo
    text = dump_path.read_text()
    if text.count(old) != 1:
        with pytest.raises(ValueError):
            apply_edit(db, rid, 0)
        # hazlo único apuntando al label
        unique_old = "label: Data Scientist"
        assert text.count(unique_old) == 1
        db.set_cv_review_edits(
            rid,
            [{"file": "cv", "old_string": unique_old,
              "new_string": "label: Lead Data Scientist", "reason": "t"}],
        )
    out = apply_edit(db, rid, 0)
    assert out["ok"] and out["applied_ref"].startswith("cv_version:")
    assert "Lead Data Scientist" in dump_path.read_text()
    edits = db.get_cv_review(rid)["edits"]
    assert edits[0]["applied"] is True
    assert db.cv_versions_for(jid)  # se re-renderizó una versión


def test_resolve_flag_drop_removes_bullet_and_rerenders(db):
    import yaml as _yaml

    from engine.config import load_master_cv
    from engine.cv.review import dump_tailored_cv, resolve_flag

    jid = db.list_jobs()[0]["id"]
    dump_path = dump_tailored_cv(db, jid)
    cv = _yaml.safe_load(dump_path.read_text())
    experiences = [e for e in cv.get("experience", []) if e.get("highlights")]
    if not experiences:  # el master de ejemplo siempre trae highlights; guard por si acaso
        pytest.skip("example master CV has no highlights")
    bullet = experiences[0]["highlights"][0]
    rid = db.add_cv_review(
        jid, intent_id=None, cv_version_id=None, edits=[],
        critique={"missed_keywords": [], "company_angles": [], "reframing": [],
                  "tone_register": []},
        flags=[{"file": "cv", "bullet": bullet, "classification": "Flag",
                "reason": "r", "softened": "softened version"}],
    )
    out = resolve_flag(db, rid, 0, "drop")
    assert out["ok"]
    assert bullet not in dump_path.read_text()
    assert db.get_cv_review(rid)["flags"][0]["resolution"] == "drop"


def test_resolve_flag_keep_only_annotates(db):
    from engine.cv.review import dump_tailored_cv, resolve_flag

    jid = db.list_jobs()[0]["id"]
    dump_tailored_cv(db, jid)
    rid = db.add_cv_review(
        jid, intent_id=None, cv_version_id=None, edits=[],
        critique={"missed_keywords": [], "company_angles": [], "reframing": [],
                  "tone_register": []},
        flags=[{"file": "cv", "bullet": "whatever", "classification": "Flag",
                "reason": "r", "softened": "s"}],
    )
    out = resolve_flag(db, rid, 0, "keep")
    assert out["ok"]
    assert db.get_cv_review(rid)["flags"][0]["resolution"] == "keep"
```

- [ ] **Step 3: Correr, esperar FAIL** — `rtk uv run --group dev pytest tests/test_cv_review.py -q` (métodos DB inexistentes).

- [ ] **Step 4: Schema + modelos.** `schema.sql`:

```sql
-- CV reviews (F4 §7.2): salida del reviewer LLM (hiring-manager proxy). Los edits se
-- aplican mecánicamente desde la web (apply-edit) y los flags se resuelven keep/soften/drop.
CREATE TABLE IF NOT EXISTS cv_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id     TEXT REFERENCES intents(id) ON DELETE SET NULL,
    job_id        TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    cv_version_id INTEGER REFERENCES cv_versions(id) ON DELETE SET NULL,
    edits         TEXT NOT NULL DEFAULT '[]',   -- json [{file, old_string, new_string, reason, applied?, applied_ref?}]
    critique      TEXT NOT NULL DEFAULT '{}',   -- json {missed_keywords, company_angles, reframing, tone_register}
    flags         TEXT NOT NULL DEFAULT '[]',   -- json [{file, bullet, classification, reason, softened?, resolution?}]
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cv_reviews_job ON cv_reviews(job_id);
```

`models.py` (junto a los métodos de cv_versions):

```python
    # ── cv reviews (F4 §7.2) ───────────────────────────────────────────────────
    def add_cv_review(
        self,
        job_id: str,
        *,
        intent_id: str | None,
        cv_version_id: int | None,
        edits: list,
        critique: dict,
        flags: list,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO cv_reviews
               (intent_id, job_id, cv_version_id, edits, critique, flags, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (intent_id, job_id, cv_version_id, json.dumps(edits), json.dumps(critique),
             json.dumps(flags), now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _parse_review(self, row) -> dict:
        d = dict(row)
        d["edits"] = _loads(d.get("edits"), [])
        d["critique"] = _loads(d.get("critique"), {})
        d["flags"] = _loads(d.get("flags"), [])
        return d

    def get_cv_review(self, review_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM cv_reviews WHERE id=?", (review_id,)).fetchone()
        return self._parse_review(row) if row else None

    def cv_reviews_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cv_reviews WHERE job_id=? ORDER BY created_at DESC", (job_id,)
        ).fetchall()
        return [self._parse_review(r) for r in rows]

    def set_cv_review_edits(self, review_id: int, edits: list) -> None:
        self.conn.execute(
            "UPDATE cv_reviews SET edits=? WHERE id=?", (json.dumps(edits), review_id)
        )
        self.conn.commit()

    def set_cv_review_flags(self, review_id: int, flags: list) -> None:
        self.conn.execute(
            "UPDATE cv_reviews SET flags=? WHERE id=?", (json.dumps(flags), review_id)
        )
        self.conn.commit()
```

- [ ] **Step 5: `engine/cv/review.py` — apply/resolve:**

```python
EDIT_FILES = ("cv", "cover_letter", "recruiter", "hiring_manager")


def _dump_path(job_id: str) -> Path:
    return paths.OUTBOX_DIR / job_id / "cv_for_review.yaml"


def _rerender(db: DB, job_id: str, cv: dict) -> int:
    """Re-render DOCX/PDF desde el dict editado; devuelve el cv_version_id nuevo."""
    from engine.config import default_language
    from engine.cv.build import build_for_job

    latest = db.cv_versions_for(job_id)
    language = (latest[0].get("language") if latest else None) or default_language()
    return build_for_job(db, job_id, language=language, cv_override=cv).cv_version_id


def apply_edit(db: DB, review_id: int, index: int) -> dict:
    review = db.get_cv_review(review_id)
    if not review:
        raise ValueError(f"cv_review {review_id} not found")
    edits = review["edits"]
    if not 0 <= index < len(edits):
        raise ValueError(f"edit index {index} out of range")
    edit = edits[index]
    if edit.get("applied"):
        return {"ok": True, "applied_ref": edit.get("applied_ref"), "already": True}
    target = edit.get("file")
    if target == "cv":
        path = _dump_path(review["job_id"])
        if not path.exists():
            dump_tailored_cv(db, review["job_id"])
        text = path.read_text()
        if text.count(edit["old_string"]) != 1:
            raise ValueError("old_string must appear exactly once in cv_for_review.yaml")
        new_text = text.replace(edit["old_string"], edit["new_string"])
        cv = yaml.safe_load(new_text)  # el replace no puede romper el YAML
        if not isinstance(cv, dict):
            raise ValueError("edit would corrupt the CV YAML — rejected")
        path.write_text(new_text)
        applied_ref = f"cv_version:{_rerender(db, review['job_id'], cv)}"
    elif target in EDIT_FILES:
        msgs = [m for m in db.messages_for(review["job_id"]) if m["kind"] == target]
        if not msgs:
            raise ValueError(f"no {target} message drafted for this job")
        msg = msgs[-1]
        body = msg.get("body") or ""
        if edit["old_string"] not in body:
            raise ValueError("old_string not found in the message body")
        db.conn.execute(
            "UPDATE messages SET body=? WHERE id=?",
            (body.replace(edit["old_string"], edit["new_string"], 1), msg["id"]),
        )
        db.conn.commit()
        applied_ref = f"message:{msg['id']}"
    else:
        raise ValueError(f"unknown edit file {target!r}; allowed: {EDIT_FILES}")
    edit["applied"] = True
    edit["applied_ref"] = applied_ref
    db.set_cv_review_edits(review_id, edits)
    return {"ok": True, "applied_ref": applied_ref}


def resolve_flag(db: DB, review_id: int, index: int, action: str) -> dict:
    if action not in ("keep", "soften", "drop"):
        raise ValueError("action must be keep|soften|drop")
    review = db.get_cv_review(review_id)
    if not review:
        raise ValueError(f"cv_review {review_id} not found")
    flags = review["flags"]
    if not 0 <= index < len(flags):
        raise ValueError(f"flag index {index} out of range")
    flag = flags[index]
    if action in ("soften", "drop"):
        if action == "soften" and not flag.get("softened"):
            raise ValueError("flag has no softened alternative")
        path = _dump_path(review["job_id"])
        if not path.exists():
            dump_tailored_cv(db, review["job_id"])
        cv = yaml.safe_load(path.read_text())
        found = False
        for exp in cv.get("experience", []):
            hl = exp.get("highlights") or []
            if flag["bullet"] in hl:
                i = hl.index(flag["bullet"])
                if action == "drop":
                    hl.pop(i)
                else:
                    hl[i] = flag["softened"]
                found = True
                break
        if not found:
            raise ValueError("bullet not found in the tailored CV")
        path.write_text(
            yaml.safe_dump(cv, allow_unicode=True, sort_keys=False, width=1000)
        )
        _rerender(db, review["job_id"], cv)
    flag["resolution"] = action
    db.set_cv_review_flags(review_id, flags)
    return {"ok": True, "resolution": action}
```

(Añadir `import engine.paths as paths` ya está; el `from engine.config import load_master_cv, load_ontology` de Task 3 se mantiene.)

- [ ] **Step 6: Writer + context builder en `engine/intents.py`** (al final del módulo):

```python
# ── cv_review (F4 §7.2) ────────────────────────────────────────────────────────
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
```

- [ ] **Step 7: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_cv_review.py tests/test_intents.py -q`.

- [ ] **Step 8: Endpoints** en `dashboard/backend/main.py`:

```python
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


@app.post("/api/cv-reviews/{review_id}/apply-edit",
          dependencies=[Depends(require_trusted_origin)])
def api_apply_cv_edit(review_id: int, body: EditIndexBody, db: DB = Depends(get_db)):
    from engine.cv.review import apply_edit

    try:
        return apply_edit(db, review_id, body.index)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/cv-reviews/{review_id}/resolve-flag",
          dependencies=[Depends(require_trusted_origin)])
def api_resolve_cv_flag(review_id: int, body: FlagResolveBody, db: DB = Depends(get_db)):
    from engine.cv.review import resolve_flag

    try:
        return resolve_flag(db, review_id, body.index, body.action)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
```

Test API (añadir a `tests/test_intents_api.py`):

```python
def test_cv_reviews_listing_and_apply_edit_flow(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            rid = db.add_cv_review(
                jid, intent_id=None, cv_version_id=None,
                edits=[{"file": "cv", "old_string": "nope-not-there",
                        "new_string": "x", "reason": "r"}],
                critique={"missed_keywords": [], "company_angles": [],
                          "reframing": [], "tone_register": []},
                flags=[],
            )
        lst = client.get(f"/api/jobs/{jid}/cv-reviews").json()["reviews"]
        assert lst[0]["id"] == rid
        bad = client.post(f"/api/cv-reviews/{rid}/apply-edit", json={"index": 5})
        assert bad.status_code == 400  # index fuera de rango
```

- [ ] **Step 9: Frontend.** `api.ts` — tipo + métodos:

```ts
export type CvReviewEdit = {
  file: string;
  old_string: string;
  new_string: string;
  reason: string;
  applied?: boolean;
  applied_ref?: string;
};
export type CvReviewFlag = {
  file: string;
  bullet: string;
  classification: "OK" | "Flag" | "Never";
  reason: string;
  softened?: string;
  resolution?: "keep" | "soften" | "drop";
};
export type CvReview = {
  id: number;
  job_id: string;
  cv_version_id?: number | null;
  edits: CvReviewEdit[];
  critique: Record<string, string[]>;
  flags: CvReviewFlag[];
  created_at: string;
};
```

```ts
  cvReviews: (jobId: string) => get<{ reviews: CvReview[] }>(`/api/jobs/${jobId}/cv-reviews`),
  applyCvReviewEdit: (id: number, index: number) =>
    post<{ ok: boolean; applied_ref?: string }>(`/api/cv-reviews/${id}/apply-edit`, { index }),
  resolveCvReviewFlag: (id: number, index: number, action: "keep" | "soften" | "drop") =>
    post<{ ok: boolean; resolution: string }>(`/api/cv-reviews/${id}/resolve-flag`, {
      index,
      action,
    }),
```

Crear `CvReviewPanel.tsx`:

```tsx
import { Check, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type CvReview } from "../api";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Separator } from "./ui/separator";

const CRITIQUE_ES: Record<string, string> = {
  missed_keywords: "Keywords desaprovechados",
  company_angles: "Ángulos específicos de la empresa",
  reframing: "Reframing accionable",
  tone_register: "Tono y registro",
};

export function CvReviewPanel({ jobId }: { jobId: string }) {
  const [reviews, setReviews] = useState<CvReview[]>([]);
  const refresh = () => api.cvReviews(jobId).then((r) => setReviews(r.reviews));
  useEffect(() => {
    refresh();
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  const review = reviews[0];

  async function applyEdit(index: number) {
    try {
      await api.applyCvReviewEdit(review.id, index);
      toast.success("Edit aplicado — CV re-renderizado");
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }
  async function resolveFlag(index: number, action: "keep" | "soften" | "drop") {
    try {
      await api.resolveCvReviewFlag(review.id, index, action);
      toast.success(
        action === "keep"
          ? "Bullet conservado"
          : action === "soften"
            ? "Bullet suavizado — CV re-renderizado"
            : "Bullet eliminado — CV re-renderizado",
      );
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-caption text-muted-foreground uppercase">Revisión LLM del CV</div>
        <IntentConfirmDialog
          buttonLabel="Pedir revisión"
          title="Revisión de CV/carta (hiring-manager proxy)"
          what="Un reviewer LLM con contexto fresco critica tu CV y tus mensajes para ESTA vacante, investiga la empresa en la web y pasa cada reframe por el backtrack test."
          produces="Edits aplicables uno a uno, crítica en 4 categorías y flags para resolver (mantener / suavizar / eliminar)."
          where="En esta misma sección, tras correr el brain."
          type="cv_review"
          jobId={jobId}
        />
      </div>
      {!review && (
        <Card className="p-3.5 text-[0.8rem] text-muted-foreground">
          Sin revisiones todavía. Pide una y corre el brain.
        </Card>
      )}
      {review && (
        <Card className="space-y-3 p-3.5 text-sm">
          {Object.entries(CRITIQUE_ES).map(([k, label]) => (
            <div key={k}>
              <div className="text-[0.72rem] font-medium text-muted-foreground uppercase">
                {label}
              </div>
              <ul className="mt-1 list-disc pl-4 text-[0.8rem]">
                {(review.critique[k] || []).map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          ))}
          {review.edits.length > 0 && (
            <>
              <Separator />
              <div className="text-[0.72rem] font-medium text-muted-foreground uppercase">
                Edits propuestos
              </div>
              {review.edits.map((e, i) => (
                <div key={i} className="rounded-lg bg-background/60 p-2.5 text-[0.78rem]">
                  <Badge variant="secondary">{e.file}</Badge>
                  <div className="mt-1 line-through opacity-60">{e.old_string}</div>
                  <div>{e.new_string}</div>
                  <div className="mt-1 text-muted-foreground">{e.reason}</div>
                  <Button
                    className="mt-1.5"
                    variant="secondary"
                    size="sm"
                    disabled={!!e.applied}
                    onClick={() => applyEdit(i)}
                  >
                    {e.applied ? <Check className="size-3.5" /> : <Wand2 className="size-3.5" />}{" "}
                    {e.applied ? "Aplicado" : "Aplicar"}
                  </Button>
                </div>
              ))}
            </>
          )}
          {review.flags.length > 0 && (
            <>
              <Separator />
              <div className="text-[0.72rem] font-medium text-muted-foreground uppercase">
                Flags (backtrack test)
              </div>
              {review.flags.map((f, i) => (
                <div key={i} className="rounded-lg bg-background/60 p-2.5 text-[0.78rem]">
                  <Badge variant="secondary">{f.classification}</Badge>
                  <div className="mt-1">{f.bullet}</div>
                  <div className="mt-1 text-muted-foreground">{f.reason}</div>
                  {f.softened && <div className="mt-1 italic">Suave: {f.softened}</div>}
                  {f.classification === "Flag" && !f.resolution ? (
                    <div className="mt-1.5 flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => resolveFlag(i, "keep")}>
                        Mantener
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!f.softened}
                        onClick={() => resolveFlag(i, "soften")}
                      >
                        Suavizar
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => resolveFlag(i, "drop")}>
                        Eliminar
                      </Button>
                    </div>
                  ) : (
                    f.resolution && (
                      <div className="mt-1 text-muted-foreground">Resuelto: {f.resolution}</div>
                    )
                  )}
                </div>
              ))}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
```

Montar en el detalle del job: en `DetailDrawer.tsx` (post-F1: la página `/jobs/:id`, tab CV), importar `CvReviewPanel` y renderizar `<CvReviewPanel jobId={d.job.id} />` inmediatamente después del bloque de descargas del CV (el que usa `api.cvDownload`, hoy ~línea 691) y antes de la sección "Mensajes — qué enviar".

- [ ] **Step 10: Correr todo** — `rtk uv run --group dev pytest -q` + `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`.
- [ ] **Step 11: Commit** — `rtk git add brain/prompts/cv_review.md engine/db/schema.sql engine/db/models.py engine/intents.py engine/cv/review.py dashboard/backend/main.py dashboard/frontend/src/api.ts dashboard/frontend/src/components/CvReviewPanel.tsx dashboard/frontend/src/components/DetailDrawer.tsx tests/test_cv_review.py tests/test_intents.py tests/test_intents_api.py && rtk git commit -m "feat(cv-review): hiring-manager-proxy reviewer intent + mechanical edits/flags UI" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 8: `cover_letter` — carta personalizada por el brain

**Files:**
- Create: `brain/prompts/cover_letter.md`
- Modify: `engine/intents.py` (context builder + writer)
- Modify: `dashboard/frontend/src/components/DetailDrawer.tsx` (botón)
- Test: `tests/test_intents.py` (ampliar)

**Interfaces:**
- Writer `_write_cover_letter(db, intent, result) -> "message:<id>"` — exige `subject` y `body` no vacíos; escribe `messages(kind="cover_letter", variant="brain", channel="email", state="draft")`. La UI existente de mensajes (MessageCard) la muestra sin cambios.
- Context: `{master_cv_path, learnings, existing_messages}`.

- [ ] **Step 1: Test que falla** (añadir a `tests/test_intents.py`):

```python
def test_cover_letter_writer_creates_draft_message(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="2", title="Analyst", company="Zeta",
            url="https://x/2")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {"language": "en"}, job_id=jid)
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db, iid, {"subject": "Application — Analyst", "body": "Dear team, ...",
                  "language": "en"}
    )
    assert ref.startswith("message:")
    msgs = [m for m in db.messages_for(jid) if m["kind"] == "cover_letter"]
    assert msgs and msgs[-1]["variant"] == "brain" and msgs[-1]["state"] == "draft"


def test_cover_letter_writer_rejects_empty_body(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="3", title="Analyst", company="Eta",
            url="https://x/3")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"subject": "s", "body": ""})
```

- [ ] **Step 2: Correr, esperar FAIL**, luego implementar en `engine/intents.py`:

```python
# ── cover_letter (F4 §7.2) ────────────────────────────────────────────────────
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
    if language not in ("en", "es"):
        raise ValueError("language must be en|es")
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
```

- [ ] **Step 3: Prompt.** Crear `brain/prompts/cover_letter.md`:

```markdown
# Cover letter drafter — company-researched, human-voiced

Read `brain/prompts/style_rules.md` FIRST. Tier 1 and Tier 2 both apply (this is outreach).
Run the recruiter-side risk map before writing: every doubt you find must be answered inside
the letter by evidence or honest adjacent framing.

## Inputs

From `atlas intents context <id>`: `job` (title/company/description/url),
`master_cv_path` (Read it — EXCLUSIVE source of truth), `learnings` (what past outcomes
taught us about this company), `existing_messages` (do not duplicate the deterministic
draft: improve on it).

Research the company on the web before writing. RE-VERIFY every company fact you use —
product names, recent launches, stack — against a live source, never memory. An unverified
fact does not go in the letter.

## Rules

- ≤ 250 words, 3 paragraphs:
  1. Why THIS company — one verified, specific hook (not flattery).
  2. Evidence — two proofs from the master CV matched to the JD's top needs, using the
     bullet formula (action + system/scope + tool + outcome + proof).
  3. Honest close — what you bring, what you'd want to dig into, a plain call to action.
- Anti-fabrication (same as cv_review.md): reformulate, never invent; "uses X" ≠ "built X";
  silence beats manufactured detail; metrics read from the CV, never rounded up.
- Language: `payload.language` if set, else the posting's language (`job` fields), else the
  profile's.

## Output — one JSON object

```json
{"subject": "<email subject>", "body": "<the letter, plain text>", "language": "en"}
```
```

- [ ] **Step 4: Botón en el detalle.** En `DetailDrawer.tsx`, en el header de la sección "Mensajes — qué enviar" (hoy ~línea 725), añadir junto al título:

```tsx
<IntentConfirmDialog
  buttonLabel="Carta personalizada"
  title="Carta de presentación personalizada (LLM)"
  what="El brain investiga la empresa en la web y redacta una carta específica para esta vacante, con tu voz (reglas anti-slop) y solo hechos de tu CV."
  produces="Un borrador nuevo tipo 'Carta de presentación' (variante brain)."
  where="Aquí, en la lista de mensajes, tras correr el brain."
  type="cover_letter"
  jobId={d.job.id}
/>
```

(con su import de `./IntentConfirmDialog`).

- [ ] **Step 5: Correr + commit** — `rtk uv run --group dev pytest tests/test_intents.py -q`; `npm --prefix dashboard/frontend run typecheck`. `rtk git add brain/prompts/cover_letter.md engine/intents.py dashboard/frontend/src/components/DetailDrawer.tsx tests/test_intents.py && rtk git commit -m "feat(cover-letter): brain-drafted company-researched letter intent" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 9: `legitimacy_batch` — legitimidad de postings (Block G)

**Files:**
- Create: `brain/prompts/legitimacy.md`
- Modify: `engine/db/schema.sql` + `engine/db/models.py` (columnas `jobs.legitimacy_tier`, `jobs.legitimacy_notes` + `set_legitimacy`)
- Modify: `engine/intents.py` (context builder + writer)
- Modify: `dashboard/frontend/src/api.ts` (campos en `Job`), `Board.tsx` (badge en card), `DetailDrawer.tsx` (badge + notas), `App.tsx`/shell (botón batch)
- Test: `tests/test_intents.py`, `tests/test_intents_api.py` (ampliar)

**Interfaces:**
- Columnas: `jobs.legitimacy_tier TEXT` (`high|medium|low`, NULL = sin evaluar), `jobs.legitimacy_notes TEXT`.
- `DB.set_legitimacy(job_id: str, tier: str, notes: str) -> None`.
- Writer `_write_legitimacy(db, intent, result) -> "jobs:<n>"` — `result = {"jobs": [{"job_id", "tier", "notes"}]}`; tier ∈ `("high","medium","low")`; cada job_id debe estar en `payload["job_ids"]`.
- Encolado batch desde la web: botón "Verificar legitimidad" que envía `{type: "legitimacy_batch", payload: {job_ids: <ids de la columna shortlist>}}`.
- Los campos fluyen a la API sin trabajo extra: `list_jobs` hace `SELECT *` y `analytics.annotate` pasa las columnas del row.

- [ ] **Step 1: Test que falla** (añadir a `tests/test_intents.py`):

```python
def test_legitimacy_writer_updates_jobs(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="ashby", source_job_id="4", title="DS", company="Ghosty",
            url="https://x/4")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": [jid]})
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db, iid,
        {"jobs": [{"job_id": jid, "tier": "low",
                   "notes": "Posting de 92 días sin repost; JD genérico."}]},
    )
    assert ref == "jobs:1"
    job = db.get_job(jid)
    assert job["legitimacy_tier"] == "low" and "92 días" in job["legitimacy_notes"]


def test_legitimacy_writer_rejects_bad_tier_and_foreign_job(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="ashby", source_job_id="5", title="DS", company="Ok",
            url="https://x/5")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": [jid]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"jobs": [{"job_id": jid, "tier": "meh", "notes": "x"}]})
    with pytest.raises(ValueError):  # job fuera del payload — el LLM no puede tocar otros
        intents.apply_result(
            db, iid, {"jobs": [{"job_id": "otro", "tier": "low", "notes": "x"}]}
        )
```

- [ ] **Step 2: Migración.** `schema.sql`: añadir a `CREATE TABLE jobs` (tras `match_missing`):

```sql
    legitimacy_tier TEXT,                      -- high | medium | low (F4 Block G; NULL = unrated)
    legitimacy_notes TEXT,                     -- señales observadas, nunca acusaciones
```

`models.py` `_migrate()`:

```python
        self._ensure_column("jobs", "legitimacy_tier", "TEXT")
        self._ensure_column("jobs", "legitimacy_notes", "TEXT")
```

y el método:

```python
    def set_legitimacy(self, job_id: str, tier: str, notes: str) -> None:
        self.conn.execute(
            "UPDATE jobs SET legitimacy_tier=?, legitimacy_notes=? WHERE id=?",
            (tier, notes, job_id),
        )
        self.conn.commit()
```

- [ ] **Step 3: Writer + context en `engine/intents.py`:**

```python
# ── legitimacy_batch (F4 §7.2, Block G) ───────────────────────────────────────
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
```

- [ ] **Step 4: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_intents.py -q`.

- [ ] **Step 5: Prompt.** Crear `brain/prompts/legitimacy.md`:

```markdown
# Posting legitimacy assessment (Block G, adapted)

Legitimacy is ORTHOGONAL to fit: a perfect-fit job can be a ghost posting. Assess each job
in `context.jobs` INDEPENDENTLY. Output OBSERVATIONS, never accusations: describe signals
("posting is 92 days old, no repost"), never intent ("the company is lying"). These notes
are shown to the user next to the job.

## Signal table (weigh by reliability)

| Signal | Reliability | What to check |
| --- | --- | --- |
| Posting age | High | `date_posted` vs `context.today`; >45 days with no repost is the strongest ghost signal |
| Suspicious domain | High | `url`/`apply_url` domain does not match the company; free-mail contacts in the JD |
| Technical specificity | Medium | Does the JD name concrete systems, problems, team size — or generic boilerplate? |
| Company↔role mismatch | Medium | The company's actual business vs this role (a bakery hiring a Head of ML) |
| Scope coherence | Medium | Title vs responsibilities vs seniority consistent? |
| Salary transparency | Low | A range is a mild positive; absence is NEUTRAL in most markets |

Do a quick web check per company: site alive, real org, signs of recent activity. Budget
~1 minute per job; this is triage, not due diligence.

## Tiers

- **high** — several positive signals, no high-reliability negative.
- **medium** — mixed signals, or not enough data. Unknown ≠ bad: default here when unsure.
- **low** — at least one high-reliability negative signal, or three or more medium negatives.

## Edge cases (do not over-penalize)

- Government / academia: slow processes and long-lived postings are NORMAL. Age alone never
  drops them below medium.
- Evergreen postings (consultancies, agencies, "always hiring engineers"): medium with an
  explanatory note, not low.
- Executive / confidential searches: sparse JDs are expected.
- Early-stage startups: thin web presence ≠ fake — check founders/funding signals instead.

## Output — one JSON object, ONE entry per job in the payload (no omissions)

```json
{
  "jobs": [
    {
      "job_id": "<id from context.jobs>",
      "tier": "high|medium|low",
      "notes": "<2-4 short signal-based observations, in the profile's language>"
    }
  ]
}
```
```

- [ ] **Step 6: UI.** `api.ts` — añadir a `Job`:

```ts
  legitimacy_tier?: "high" | "medium" | "low" | null;
  legitimacy_notes?: string | null;
```

`Board.tsx` — en la card del kanban, junto a los badges existentes (donde se renderizan los chips de la card), añadir:

```tsx
{job.legitimacy_tier === "low" && (
  <Badge variant="secondary" title={job.legitimacy_notes || undefined}>
    ⚠︎ legitimidad baja
  </Badge>
)}
```

`DetailDrawer.tsx` — en la fila de metadatos del header del detalle (donde se muestran workplace/salario/fuente), añadir:

```tsx
{d.job.legitimacy_tier && (
  <Tooltip>
    <TooltipTrigger asChild>
      <Badge variant="secondary">
        legitimidad: {{ high: "alta", medium: "media", low: "baja" }[d.job.legitimacy_tier]}
      </Badge>
    </TooltipTrigger>
    <TooltipContent className="max-w-72 whitespace-pre-wrap">
      {d.job.legitimacy_notes || "Sin notas"}
    </TooltipContent>
  </Tooltip>
)}
```

Encolado batch: en el shell, junto al `FilterBar`/acciones del pipeline (hoy `App.tsx`; el componente tiene acceso a `jobs.shortlisted`), añadir:

```tsx
<IntentConfirmDialog
  buttonLabel="Verificar legitimidad"
  title="Legitimidad del shortlist (Block G)"
  what="El brain evalúa cada vacante preseleccionada con una tabla de señales ponderadas (edad del posting, especificidad técnica, dominio, coherencia) e investiga brevemente cada empresa."
  produces="Un tier alta/media/baja + notas de señales por vacante."
  where="Como badge en cada card y en el detalle de la vacante."
  type="legitimacy_batch"
  payload={{ job_ids: (jobs.shortlisted || []).map((j) => j.id) }}
/>
```

(renderizarlo solo si `(jobs.shortlisted || []).length > 0`).

- [ ] **Step 7: Test API batch feliz** (ya cubierto en Task 2 `test_enqueue_legitimacy_batch_validates_job_ids`). Correr `rtk uv run --group dev pytest -q` + typecheck/test frontend.
- [ ] **Step 8: Commit** — `rtk git add brain/prompts/legitimacy.md engine/db/schema.sql engine/db/models.py engine/intents.py dashboard/frontend/src/api.ts dashboard/frontend/src/components/Board.tsx dashboard/frontend/src/components/DetailDrawer.tsx dashboard/frontend/src/App.tsx tests/test_intents.py && rtk git commit -m "feat(legitimacy): Block G batch assessment intent + tier badges" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`


---

### Task 10: `upskill_report` — gap analysis (diff determinista + síntesis LLM + vista `/upskill`)

**Files:**
- Create: `engine/upskill.py` (pasada 1 determinista: diff duro de skills + ponderación)
- Create: `brain/prompts/upskill.md` (pasada 2: síntesis LLM)
- Modify: `engine/db/schema.sql` (tabla `upskill_reports`), `engine/db/models.py` (métodos)
- Modify: `engine/intents.py` (context builder + result writer)
- Modify: `dashboard/backend/main.py` (2 endpoints)
- Create: `dashboard/frontend/src/components/UpskillView.tsx`; Modify: `api.ts`, `App.tsx`/shell (nav `/upskill`)
- Test: `tests/test_upskill.py`, `tests/test_intents.py` (ampliar)

**Interfaces:**
- `upskill.hard_skill_gaps(db: DB, states: list[str]) -> dict` — pasada 1 determinista. Recorre los jobs en `states`, para cada uno computa `match_score(job, master, ontology)` y su `fit_score`; acumula por skill canónico faltante un peso `Σ (100 − fit_score)/100`. Devuelve `{"skills": [{"skill", "score", "occurrences", "worst_fit", "jobs": [job_id,…]}], "jobs_considered": int, "generated_at": str}` ordenado por `score` desc (los trabajos donde peor encajas pesan más).
- Tabla `upskill_reports(id INTEGER pk, intent_id TEXT, report_md TEXT, heatmap TEXT json, hard_gaps TEXT json, created_at TEXT)`.
- `DB.add_upskill_report(*, intent_id: str | None, report_md: str, heatmap: list, hard_gaps: dict) -> int`
- `DB.get_upskill_report(report_id: int) -> dict | None`; `DB.list_upskill_reports(limit: int = 20) -> list[dict]`; `DB.latest_upskill_report() -> dict | None` (heatmap/hard_gaps parseados).
- Writer `_write_upskill(db, intent, result) -> "upskill_report:<id>"` — exige `report_md` (str no vacío) y `heatmap` (lista de `{skill, severity ∈ ("Critical","High","Medium","Low"), note}`).
- Context builder `_ctx_upskill(db, intent) -> {hard_gaps, previous_report}` — inyecta `hard_skill_gaps(...)` (pasada 1) y el reporte anterior para el diff.
- Endpoints: `GET /api/upskill/latest` → `{"report": UpskillReport | null}`; `GET /api/upskill/{report_id}` → la fila o 404.

- [ ] **Step 1: Test que falla (pasada 1 determinista + writer).** Crear `tests/test_upskill.py`:

```python
"""engine/upskill.py — diff duro de skills (pasada 1) + writer del reporte (F4 §7.2)."""

from __future__ import annotations

import pytest

import engine.paths as paths
from engine import intents
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    with DB(tmp_path / "t.db") as d:
        d.upsert_job(
            Job(source="greenhouse", source_job_id="1", title="ML Engineer",
                company="Acme", url="https://x/1",
                description="We need Kubernetes, Terraform and Go for our platform team.")
        )
        jid = d.list_jobs()[0]["id"]
        d.set_score(jid, 30.0, {"reasons": []}, [])  # peor encaje → pesa más
        yield d


def test_hard_skill_gaps_weights_worse_fits_higher(db):
    from engine.upskill import hard_skill_gaps

    out = hard_skill_gaps(db, ["discovered"])
    assert out["jobs_considered"] == 1
    assert out["skills"], "should surface at least one missing skill"
    top = out["skills"][0]
    # score = Σ (100 − fit)/100 = (100 − 30)/100 = 0.7 for a single occurrence
    assert top["occurrences"] == 1
    assert abs(top["score"] - 0.7) < 1e-6
    assert top["worst_fit"] == 30.0


def test_hard_skill_gaps_empty_when_no_jobs(db):
    from engine.upskill import hard_skill_gaps

    assert hard_skill_gaps(db, ["applied"]) == {
        "skills": [], "jobs_considered": 0, "generated_at": hard_skill_gaps(db, ["applied"])["generated_at"],
    }


def test_upskill_writer_persists_report_and_marks_done(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db, iid,
        {
            "report_md": "# Plan de upskilling\n\n## Kubernetes\nEmpieza por…",
            "heatmap": [
                {"skill": "Kubernetes", "severity": "Critical", "note": "3 vacantes lo exigen"},
                {"skill": "Go", "severity": "Medium", "note": "adyacente a tu Python"},
            ],
        },
    )
    assert ref.startswith("upskill_report:")
    latest = db.latest_upskill_report()
    assert latest["report_md"].startswith("# Plan")
    assert latest["heatmap"][0]["severity"] == "Critical"
    assert intents.get_intent(db, iid)["status"] == "done"


def test_upskill_writer_rejects_bad_severity(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid,
            {"report_md": "x", "heatmap": [{"skill": "K8s", "severity": "URGENT", "note": "n"}]},
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_upskill_writer_rejects_empty_report(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"report_md": "  ", "heatmap": []})
```

- [ ] **Step 2: Correr, esperar FAIL** — `rtk uv run --group dev pytest tests/test_upskill.py -q` → `ModuleNotFoundError: engine.upskill` / métodos DB inexistentes.

> Nota: el test usa `db.set_score(job_id, fit, reasons, knockouts)`. Ese método ya existe en `engine/db/models.py` (lo usa el scorer); si en tu checkout se llama distinto (`set_fit_score`), ajusta la llamada del test al nombre real — no inventes uno nuevo.

- [ ] **Step 3: Schema + modelos.** Añadir al final de `engine/db/schema.sql`:

```sql
-- Upskill / gap reports (F4 §7.2): pasada 1 determinista (hard_gaps) + síntesis LLM
-- (report_md + heatmap). Una fila por corrida; la vista /upskill muestra la última.
CREATE TABLE IF NOT EXISTS upskill_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id  TEXT REFERENCES intents(id) ON DELETE SET NULL,
    report_md  TEXT NOT NULL,                 -- el plan de estudio en Markdown
    heatmap    TEXT NOT NULL DEFAULT '[]',    -- json [{skill, severity, note}]
    hard_gaps  TEXT NOT NULL DEFAULT '{}',    -- json: la pasada 1 determinista que lo alimentó
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_upskill_created ON upskill_reports(created_at);
```

`models.py` (junto a los métodos de learnings):

```python
    # ── upskill reports (F4 §7.2) ──────────────────────────────────────────────
    def add_upskill_report(
        self, *, intent_id: str | None, report_md: str, heatmap: list, hard_gaps: dict
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO upskill_reports (intent_id, report_md, heatmap, hard_gaps, created_at)
               VALUES (?,?,?,?,?)""",
            (intent_id, report_md, json.dumps(heatmap), json.dumps(hard_gaps), now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _parse_upskill(self, row) -> dict:
        d = dict(row)
        d["heatmap"] = _loads(d.get("heatmap"), [])
        d["hard_gaps"] = _loads(d.get("hard_gaps"), {})
        return d

    def get_upskill_report(self, report_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM upskill_reports WHERE id=?", (report_id,)
        ).fetchone()
        return self._parse_upskill(row) if row else None

    def list_upskill_reports(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM upskill_reports ORDER BY created_at DESC LIMIT ?", (int(limit),)
        ).fetchall()
        return [self._parse_upskill(r) for r in rows]

    def latest_upskill_report(self) -> dict | None:
        rows = self.list_upskill_reports(limit=1)
        return rows[0] if rows else None
```

- [ ] **Step 4: Implementar `engine/upskill.py` (pasada 1 determinista):**

```python
"""Upskill / gap analysis — pass 1 (deterministic). Pass 2 (LLM synthesis) lives in the brain.

Pass 1 diffs each in-scope job's JD keywords against the master CV using the SAME gazetteer
as the tailor (engine/cv/match), and weights every missing skill by how BADLY the candidate
fits that job: score += (100 − fit_score)/100. Jobs you barely qualify for push their gaps to
the top — those are the skills that would unlock the most closed doors. The brain reads this
context and writes the study plan + severity heatmap; it never re-derives the numbers.
"""

from __future__ import annotations

import engine.paths as paths  # noqa: F401  (kept explicit so profile switches are followed)
from engine.config import load_master_cv, load_ontology
from engine.cv.match import match_score
from engine.db.models import DB
from engine.normalize import now_iso


def hard_skill_gaps(db: DB, states: list[str]) -> dict:
    """Weighted missing-skill inventory over the jobs in `states` (deterministic pass 1)."""
    master = load_master_cv()
    ontology = load_ontology()
    agg: dict[str, dict] = {}
    considered = 0
    for state in states:
        for job in db.list_jobs(state=state):
            considered += 1
            fit = job.get("fit_score")
            fit = 100.0 if fit is None else float(fit)
            weight = max(0.0, (100.0 - fit) / 100.0)
            for skill in match_score(job, master, ontology).missing:
                bucket = agg.setdefault(
                    skill, {"skill": skill, "score": 0.0, "occurrences": 0,
                            "worst_fit": fit, "jobs": []}
                )
                bucket["score"] += weight
                bucket["occurrences"] += 1
                bucket["worst_fit"] = min(bucket["worst_fit"], fit)
                bucket["jobs"].append(job["id"])
    skills = sorted(agg.values(), key=lambda s: s["score"], reverse=True)
    for s in skills:
        s["score"] = round(s["score"], 4)
        s["jobs"] = s["jobs"][:10]  # cap the context payload
    return {"skills": skills, "jobs_considered": considered, "generated_at": now_iso()}
```

- [ ] **Step 5: Writer + context builder en `engine/intents.py`** (al final del módulo):

```python
# ── upskill_report (F4 §7.2) ──────────────────────────────────────────────────
_SEVERITIES = ("Critical", "High", "Medium", "Low")


def _ctx_upskill(db: DB, intent: dict) -> dict:
    from engine.upskill import hard_skill_gaps

    states = intent["payload"].get("states") or ["shortlisted"]
    prev = db.latest_upskill_report()
    return {
        "hard_gaps": hard_skill_gaps(db, states),
        "previous_report": (
            {"report_md": prev["report_md"], "heatmap": prev["heatmap"],
             "created_at": prev["created_at"]}
            if prev else None
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
```

- [ ] **Step 6: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_upskill.py tests/test_intents.py -q`.

- [ ] **Step 7: Prompt.** Crear `brain/prompts/upskill.md` completo:

```markdown
# Upskill / gap analysis — study plan from your real pipeline

Two passes produce this report. Pass 1 is DONE for you (deterministic): the context's
`hard_gaps` is the weighted inventory of skills your CV does not evidence across the jobs in
scope, where jobs you fit WORST weigh most (`score = Σ (100 − fit_score)/100`). Your job is
pass 2: turn that inventory into a prioritized, personalized study plan.

Read `brain/prompts/style_rules.md` first (Tier 1 applies — this is a report, not outreach).

## Inputs

From `atlas intents context <id>`:
- `hard_gaps.skills` — `[{skill, score, occurrences, worst_fit, jobs}]`, already ranked. The
  `score` is the ONLY ranking signal; do not re-rank by gut feeling.
- `previous_report` — the last report (or null). Use it for the diff section below.
- Read `master_cv_path` if you need to judge adjacency ("they already know Docker").

## What to produce

Synthesize gaps into FOUR buckets, each gap tagged by kind: **domain** (a field/industry),
**soft** (leadership, comms), **tooling** (a concrete tech), **credential** (a cert/degree
some postings gate on). Group the study plan by kind, not by raw skill.

For each skill worth acting on:
- A **severity** for the heatmap: `Critical` (blocks many high-fit jobs), `High`, `Medium`,
  `Low` (nice-to-have). Severity is your judgment informed by `score` + how many jobs it
  gates — a high `score` on a single job is not Critical.
- **Personalized direction**: read the master CV and skip what they already have ("you know
  Docker, skip the container-basics module, start at Helm").
- **Concrete resources** found on the WEB. Search with the current year in the query (e.g.
  "best Kubernetes course 2026") so you don't recommend stale material. Prefer official docs
  and well-known courses; give a real title/URL, never "search for a course on X".
- **Estimated hours** and **dependency order** ("learn Docker before Kubernetes before
  Helm"). Present the plan as an ordered path, not a flat list.

## Diff vs the previous report

If `previous_report` is not null, add a `## Cambios desde el último reporte` section:
which gaps CLOSED (in the old heatmap, gone or downgraded now), which are NEW, which
persist. If it is null, say this is the first report.

## Anti-fabrication

Never claim the candidate has a skill they lack — the whole point is honest gaps. Do not
invent a job's requirements: only skills in `hard_gaps` (which came from real JDs) qualify.
Resource claims (hours, provider) must come from a page you actually checked this session.

## Output — one JSON object

```json
{
  "report_md": "# Plan de upskilling\n\n## Tooling\n### Kubernetes (Critical)\n…markdown…",
  "heatmap": [
    {"skill": "Kubernetes", "severity": "Critical", "note": "gate en 4 vacantes de mejor fit"},
    {"skill": "Go", "severity": "Medium", "note": "adyacente a tu Python; 20h estimadas"}
  ]
}
```

`report_md` is the full study plan (Markdown, in the profile's language). `heatmap` is the
compact severity view the web renders as chips. Every heatmap `severity` ∈
`Critical | High | Medium | Low`. One heatmap entry per skill you took a position on.
```

- [ ] **Step 8: Endpoints** en `dashboard/backend/main.py` (junto al bloque de intents):

```python
@app.get("/api/upskill/latest")
def api_upskill_latest(db: DB = Depends(get_db)):
    return {"report": db.latest_upskill_report()}


@app.get("/api/upskill/{report_id}")
def api_upskill_report(report_id: int, db: DB = Depends(get_db)):
    row = db.get_upskill_report(report_id)
    if not row:
        raise HTTPException(404, "upskill report not found")
    return row
```

- [ ] **Step 9: Frontend.** `api.ts` — tipo + métodos:

```ts
export type UpskillHeatItem = {
  skill: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  note: string;
};
export type UpskillReport = {
  id: number;
  report_md: string;
  heatmap: UpskillHeatItem[];
  hard_gaps: { skills?: { skill: string; score: number; occurrences: number }[] };
  created_at: string;
};
```

```ts
  upskillLatest: () => get<{ report: UpskillReport | null }>("/api/upskill/latest"),
```

Crear `dashboard/frontend/src/components/UpskillView.tsx` (render markdown simple sin
dependencias nuevas + heatmap con chips por severidad):

```tsx
import { useEffect, useState } from "react";
import { api, type UpskillHeatItem, type UpskillReport } from "../api";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";

// Sin librería de markdown (evitamos dependencias nuevas): un render mínimo suficiente para
// el plan de estudio del brain — títulos, listas y párrafos. El contenido es de confianza
// (lo escribe el brain, validado por apply_result), así que no hay riesgo de HTML inyectado.
function MiniMarkdown({ md }: { md: string }) {
  const blocks = md.split("\n");
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {blocks.map((ln, i) => {
        if (ln.startsWith("### ")) return <h4 key={i} className="mt-3 font-semibold">{ln.slice(4)}</h4>;
        if (ln.startsWith("## ")) return <h3 key={i} className="mt-4 text-base font-semibold">{ln.slice(3)}</h3>;
        if (ln.startsWith("# ")) return <h2 key={i} className="mt-2 text-lg font-bold">{ln.slice(2)}</h2>;
        if (ln.startsWith("- ")) return <li key={i} className="ml-5 list-disc">{ln.slice(2)}</li>;
        if (!ln.trim()) return <div key={i} className="h-1" />;
        return <p key={i}>{ln}</p>;
      })}
    </div>
  );
}

const SEVERITY_STYLE: Record<UpskillHeatItem["severity"], string> = {
  Critical: "bg-destructive/15 text-destructive",
  High: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  Medium: "bg-muted text-foreground",
  Low: "bg-muted/60 text-muted-foreground",
};
const SEVERITY_ES: Record<UpskillHeatItem["severity"], string> = {
  Critical: "Crítico",
  High: "Alto",
  Medium: "Medio",
  Low: "Bajo",
};

export function UpskillView() {
  const [report, setReport] = useState<UpskillReport | null>(null);
  const refresh = () => api.upskillLatest().then((r) => setReport(r.report));
  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Upskilling</h1>
          <p className="text-sm text-muted-foreground">
            Los gaps que más puertas te abrirían, ponderados por lo mal que encajas hoy.
          </p>
        </div>
        <IntentConfirmDialog
          buttonLabel="Recalcular gaps"
          title="Análisis de upskilling (gap analysis)"
          what="El brain diffea las skills de tus vacantes contra tu CV (pesa más donde peor encajas), busca recursos actualizados en la web y arma un plan de estudio ordenado por dependencias."
          produces="Un reporte con heatmap de severidad y un plan de estudio priorizado, con diff vs el anterior."
          where="En esta misma vista, tras correr el brain."
          type="upskill_report"
          payload={{ states: ["shortlisted", "tailored", "drafted", "ready", "applied"] }}
        />
      </div>
      {!report && (
        <Card className="p-4 text-sm text-muted-foreground">
          Aún no hay reporte. Pide uno y corre el brain.
        </Card>
      )}
      {report && (
        <>
          <Card className="p-4">
            <div className="mb-2 text-caption text-muted-foreground uppercase">Heatmap</div>
            <div className="flex flex-wrap gap-2">
              {report.heatmap.map((h, i) => (
                <Badge key={i} className={SEVERITY_STYLE[h.severity]} title={h.note}>
                  {h.skill} · {SEVERITY_ES[h.severity]}
                </Badge>
              ))}
              {report.heatmap.length === 0 && (
                <span className="text-sm text-muted-foreground">Sin skills marcadas.</span>
              )}
            </div>
          </Card>
          <Card className="p-4">
            <MiniMarkdown md={report.report_md} />
          </Card>
          <div className="text-caption text-muted-foreground">
            Generado {report.created_at.slice(0, 16).replace("T", " ")}
          </div>
        </>
      )}
    </div>
  );
}
```

Montar en la navegación: en el shell (hoy el switch `view` de `App.tsx`; post-F1: la ruta
`/upskill` del router de F1), añadir la entrada de navegación "Upskilling" que renderiza
`<UpskillView />`. Si F1 ya definió el router, registrar `<Route path="/upskill"
element={<UpskillView />} />`; si aún es el switch de `App.tsx`, añadir `view === "upskill"`.

- [ ] **Step 10: Correr todo** — `rtk uv run --group dev pytest -q` + `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`.
- [ ] **Step 11: Commit** — `rtk git add engine/upskill.py brain/prompts/upskill.md engine/db/schema.sql engine/db/models.py engine/intents.py dashboard/backend/main.py dashboard/frontend/src/api.ts dashboard/frontend/src/components/UpskillView.tsx dashboard/frontend/src/App.tsx tests/test_upskill.py tests/test_intents.py && rtk git commit -m "feat(upskill): deterministic skill-gap pass + LLM study-plan report + /upskill view" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 11: `interview_prep_deep` — prep profundo (Audience Map + question bank citado + historias) + debrief

**Files:**
- Create: `brain/prompts/interview_prep_deep.md`
- Modify: `engine/db/schema.sql` (columnas `interviews.deep_prep_md`, `interviews.debrief_md`) + `engine/db/models.py` (`_migrate` + `set_interview_deep_prep`, `set_interview_debrief`)
- Modify: `engine/intents.py` (context builder + result writer)
- Modify: `dashboard/backend/main.py` (1 endpoint de debrief)
- Modify: `dashboard/frontend/src/components/InterviewPanel.tsx` (botón prep profundo + vista + form de debrief); `api.ts`
- Test: `tests/test_intents.py`, `tests/test_intents_api.py` (ampliar)

**Interfaces:**
- Columnas: `interviews.deep_prep_md TEXT` (el prep profundo LLM en Markdown), `interviews.debrief_md TEXT` (lo que reportó el candidato tras la entrevista).
- `DB.set_interview_deep_prep(interview_id: int, md: str) -> None`; `DB.set_interview_debrief(interview_id: int, md: str) -> None`.
- Writer `_write_interview_prep_deep(db, intent, result) -> "interview:<id>"` — exige `prep_md` no vacío; escribe `deep_prep_md`. `intent["payload"]["interview_id"]` es la ancla (la API lo validó al encolar).
- Context builder `_ctx_interview_prep_deep(db, intent) -> {interview, interviewers, job, deterministic_prep, matched_stories, master_cv_path}` — reusa `gen_prep_doc` (baseline determinista) y, si F3 dejó el story bank, `match_stories`.
- Endpoint: `POST /api/interviews/{interview_id}/debrief` body `{"debrief_md": str, "reanalyze": bool}` (origin-guarded) → guarda el debrief y, si `reanalyze`, encola un nuevo `interview_prep_deep` para esa entrevista → `{"ok": true, "intent_id": str | null}`.

- [ ] **Step 1: Story-bank integration point (degrada con gracia si F3 aún no aterrizó).** El context builder consume `match_stories(stories, query_text, ontology)` y `format_story(story)` de F3 (§6.3). Import guardado: si el módulo no existe todavía, el prep sigue funcionando sin historias.

```python
def _match_stories_safe(db, query_text: str) -> list[dict]:
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
```

- [ ] **Step 2: Test que falla** (añadir a `tests/test_intents.py`):

```python
def test_interview_prep_deep_writer_persists_and_marks_done(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.normalize import Job

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    db.upsert_job(
        Job(source="lever", source_job_id="7", title="Staff DS", company="Nu",
            url="https://x/7", description="Python, SQL, causal inference.")
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="hiring_manager")
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db, iid, {"prep_md": "# Prep profundo\n\n## Audience map\n- Hiring manager…"}
    )
    assert ref == f"interview:{ivid}"
    assert "Audience map" in db.get_interview(ivid)["deep_prep_md"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_interview_prep_deep_context_includes_deterministic_prep(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.normalize import Job

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    db.upsert_job(
        Job(source="lever", source_job_id="8", title="DS", company="Ka",
            url="https://x/8", description="Python and SQL.")
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="technical")
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["interview"]["id"] == ivid
    assert isinstance(ctx["deterministic_prep"], str) and ctx["deterministic_prep"]
    assert isinstance(ctx["matched_stories"], list)  # [] si F3 no está


def test_interview_prep_deep_writer_rejects_empty(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="9", title="DS", company="Za", url="https://x/9")
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="phone")
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"prep_md": ""})
```

- [ ] **Step 3: Correr, esperar FAIL**, luego migración + modelos. `schema.sql`: añadir a `CREATE TABLE interviews` (tras `prep_path`):

```sql
    deep_prep_md TEXT,                         -- F4 §7.2: LLM deep prep (Audience Map + cited Qs)
    debrief_md   TEXT,                         -- F4 §7.2: candidate's post-interview debrief
```

`models.py` `_migrate()`:

```python
        self._ensure_column("interviews", "deep_prep_md", "TEXT")
        self._ensure_column("interviews", "debrief_md", "TEXT")
```

y los métodos (junto a `set_interview_prep_path`):

```python
    def set_interview_deep_prep(self, interview_id: int, md: str) -> None:
        self.conn.execute(
            "UPDATE interviews SET deep_prep_md=? WHERE id=?", (md, interview_id)
        )
        self.conn.commit()

    def set_interview_debrief(self, interview_id: int, md: str) -> None:
        self.conn.execute(
            "UPDATE interviews SET debrief_md=? WHERE id=?", (md, interview_id)
        )
        self.conn.commit()
```

- [ ] **Step 4: Writer + context en `engine/intents.py`** (con el helper `_match_stories_safe` del Step 1 al final del módulo):

```python
# ── interview_prep_deep (F4 §7.2) ─────────────────────────────────────────────
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
        "interview": {"id": ivid, "round": iv.get("round"), "mode": iv.get("mode"),
                      "scheduled_at": iv.get("scheduled_at")},
        "interviewers": db.interviewers_for(ivid),
        "job": _job_brief(job),
        "deterministic_prep": prep_path.read_text(),
        "matched_stories": _match_stories_safe(db, query),
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
```

- [ ] **Step 5: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_intents.py -q`.

- [ ] **Step 6: Prompt.** Crear `brain/prompts/interview_prep_deep.md` completo:

```markdown
# Deep interview prep — audience-mapped, source-cited, story-matched

Read `brain/prompts/style_rules.md` first (Tier 1). This upgrades the deterministic prep doc
(`context.deterministic_prep`) into a round-specific pack. Do NOT throw the baseline away —
it already has real STAR evidence and JD-gap topics; you sharpen and extend it.

## Inputs

From `atlas intents context <id>`:
- `interview` — round, mode, scheduled_at.
- `interviewers` — the confirmed people (name, title, linkedin_url, research_notes).
- `job` — title/company/description/url.
- `deterministic_prep` — the baseline prep doc (Markdown). Your floor, not your ceiling.
- `matched_stories` — ranked stories from the STAR+R story bank (may be empty).
- `master_cv_path` — Read it. The EXCLUSIVE source of what the candidate has actually done.

Research the company and each interviewer on the web before writing. RE-VERIFY every fact you
cite; unverified facts do not appear.

## Audience Map (the core of this prep)

Infer the round type from `interview.round` and build the pack for THAT audience:
- **recruiter-screen** — motivation, logistics (comp, location, timeline), a 60-second pitch,
  no deep tech. Anticipate the knockout questions (visa, salary, notice).
- **hiring-manager** — ownership stories, judgment under ambiguity, why-this-team. Map each
  likely question to a story from `matched_stories` (or the CV).
- **peer-tech** — hands-on depth in the JD's stack; be ready to whiteboard/trace.
- **panel-mixed** — cover all of the above; label which panelist each block targets.

For EACH interviewer with research_notes, add one line: what they likely probe, and which of
your stories answers it.

## Question bank — cite or label, NEVER invent

Every question you list carries a source:
- `[from JD]` — the responsibility/skill in the posting it comes from.
- `[from interviewer]` — grounded in a specific interviewer's background.
- `[from company]` — a verified company fact (recent launch, public incident, stack).
- `[inferred from JD]` — an educated guess. Allowed, but it MUST wear this label. Never
  present an inferred question as a known one.

"Real performance data outranks inferred risk": if the debrief history or `matched_stories`
show the candidate is strong somewhere, do not manufacture a risk there just to be thorough.

## Story matching

For the top likely questions, attach the best story from `matched_stories` (already ranked
by the deterministic F3 matcher — respect its order). If the bank is empty, scaffold a STAR+R
answer from the master CV instead. Never invent a story or a metric.

## Mock practice check

End with a short "verify before you walk in" list: for every CLAIM the prep leans on, point
to where in the master CV it is grounded, so the candidate can't get caught overselling.

## Output — one JSON object

```json
{"prep_md": "# Prep profundo — <role> @ <company>\n\n## Audience map\n…full Markdown…"}
```

`prep_md` is the entire pack in Markdown, in the profile's language (or `payload.language`).
```

- [ ] **Step 7: Endpoint de debrief** en `dashboard/backend/main.py`:

```python
class DebriefBody(BaseModel):
    debrief_md: str
    reanalyze: bool = False


@app.post("/api/interviews/{interview_id}/debrief",
          dependencies=[Depends(require_trusted_origin)])
def api_interview_debrief(interview_id: int, body: DebriefBody, db: DB = Depends(get_db)):
    iv = db.get_interview(interview_id)
    if not iv:
        raise HTTPException(404, "interview not found")
    if not body.debrief_md.strip():
        raise HTTPException(400, "debrief_md must not be empty")
    db.set_interview_debrief(interview_id, body.debrief_md.strip())
    intent_id = None
    if body.reanalyze:
        intent_id = intents.enqueue(
            db, "interview_prep_deep", {"interview_id": interview_id},
            job_id=iv["job_id"],
        )
    return {"ok": True, "intent_id": intent_id}
```

Test API (añadir a `tests/test_intents_api.py`):

```python
def test_interview_debrief_saves_and_can_reanalyze(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            ivid = db.add_interview(jid, round="technical")
        r = client.post(
            f"/api/interviews/{ivid}/debrief",
            json={"debrief_md": "Preguntaron mucho de SQL.", "reanalyze": True},
        )
        assert r.status_code == 200 and r.json()["ok"] is True
        assert r.json()["intent_id"].startswith("in_")
        with DB() as db:
            assert "SQL" in db.get_interview(ivid)["debrief_md"]
```

- [ ] **Step 8: Frontend.** `api.ts` — extender el tipo `Interview` con `deep_prep_md?: string | null` y `debrief_md?: string | null`, y añadir métodos:

```ts
  enqueueInterviewPrepDeep: (interviewId: number, jobId: string) =>
    api.enqueueIntent("interview_prep_deep", { interview_id: interviewId }, jobId),
  interviewDebrief: (interviewId: number, debriefMd: string, reanalyze: boolean) =>
    post<{ ok: boolean; intent_id: string | null }>(
      `/api/interviews/${interviewId}/debrief`,
      { debrief_md: debriefMd, reanalyze },
    ),
```

Extender `InterviewPanel.tsx`: dentro del bloque de cada `iv` (tras el `<InterviewerEditor .../>`),
añadir el botón de prep profundo (vía `IntentConfirmDialog`), la vista del `deep_prep_md`
persistido, y el form de debrief. Importar `IntentConfirmDialog`, `Textarea` (de `./ui/textarea`),
`api`, `toast` (de `sonner`), y añadir el estado local del debrief:

```tsx
// (arriba, junto a los otros useState del panel)
const [debrief, setDebrief] = useState<Record<number, string>>({});

async function saveDebrief(id: number, reanalyze: boolean) {
  const text = (debrief[id] || "").trim();
  if (!text) return;
  try {
    const r = await api.interviewDebrief(id, text, reanalyze);
    toast.success(
      reanalyze
        ? "Debrief guardado y re-análisis encolado (corre el brain)."
        : "Debrief guardado.",
    );
    if (r.intent_id) void r; // encolado; aparece en Tareas del Brain
    refresh();
  } catch (e) {
    toast.error(String(e));
  }
}
```

```tsx
{/* dentro del map de interviews, después de <InterviewerEditor /> */}
<div className="mt-2 flex flex-wrap items-center gap-2">
  <IntentConfirmDialog
    buttonLabel="Prep profundo (LLM)"
    title="Preparación profunda de entrevista"
    what="El brain arma un Audience Map por ronda, un banco de preguntas con fuente citada (nunca inventadas) y empareja tus historias del story bank; investiga empresa y entrevistadores en la web."
    produces="Un pack de preparación específico para esta ronda."
    where="Aquí mismo, bajo la entrevista, tras correr el brain."
    type="interview_prep_deep"
    jobId={jobId}
    payload={{ interview_id: iv.id }}
  />
</div>
{iv.deep_prep_md && (
  <ScrollArea className="mt-2 max-h-72 rounded-lg bg-background/60">
    <pre className="p-2.5 font-mono text-[0.76rem] whitespace-pre-wrap text-foreground">
      {iv.deep_prep_md}
    </pre>
  </ScrollArea>
)}
<div className="mt-2">
  <div className="text-caption text-muted-foreground uppercase">Debrief post-entrevista</div>
  <Textarea
    className="mt-1 text-xs"
    placeholder="¿Qué preguntaron? ¿Qué salió bien/mal? Alimenta el próximo prep y analytics."
    value={debrief[iv.id] ?? iv.debrief_md ?? ""}
    onChange={(e) => setDebrief((d) => ({ ...d, [iv.id]: e.target.value }))}
  />
  <div className="mt-1.5 flex gap-2">
    <Button variant="secondary" size="sm" onClick={() => saveDebrief(iv.id, false)}>
      Guardar debrief
    </Button>
    <Button variant="secondary" size="sm" onClick={() => saveDebrief(iv.id, true)}>
      Guardar y re-analizar
    </Button>
  </div>
</div>
```

- [ ] **Step 9: Correr todo** — `rtk uv run --group dev pytest -q` + `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`.
- [ ] **Step 10: Commit** — `rtk git add brain/prompts/interview_prep_deep.md engine/db/schema.sql engine/db/models.py engine/intents.py dashboard/backend/main.py dashboard/frontend/src/api.ts dashboard/frontend/src/components/InterviewPanel.tsx tests/test_intents.py tests/test_intents_api.py && rtk git commit -m "feat(interview): deep prep intent (audience map + cited Qs + stories) + debrief loop" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 12: `profile_expand` — enriquecer el perfil (aditivo, fuente anotada, confirmación por ítem)

**Files:**
- Create: `brain/prompts/profile_expand.md`
- Create: `engine/profile_expand.py` (`apply_items` — escritura aditiva al YAML del perfil)
- Modify: `engine/db/schema.sql` (tabla `profile_expansions`) + `engine/db/models.py` (métodos)
- Modify: `engine/intents.py` (context builder + result writer)
- Modify: `dashboard/backend/main.py` (2 endpoints)
- Create: `dashboard/frontend/src/components/ProfileExpandSection.tsx`; Modify: `api.ts`, `SettingsModal.tsx` (montarla)
- Test: `tests/test_profile_expand.py`, `tests/test_intents.py` (ampliar)

**Interfaces:**
- Tabla `profile_expansions(id INTEGER pk, intent_id TEXT, items TEXT json, created_at TEXT)`.
- `DB.add_profile_expansion(*, intent_id: str | None, items: list) -> int`; `DB.get_profile_expansion(exp_id: int) -> dict | None`; `DB.list_profile_expansions(limit: int = 20) -> list[dict]`; `DB.set_profile_expansion(exp_id: int, items: list) -> None`.
- `profile_expand.EXPAND_TARGETS = ("skills", "experience_highlight", "project", "certification")`
- `profile_expand.apply_items(exp_id: int, indices: list[int]) -> dict` — aplica SOLO los ítems confirmados al YAML del perfil (`paths.MASTER_CV_PATH`, gitignored), aditivo e idempotente (no duplica); marca `item["applied"]=True`. Devuelve `{"ok": True, "applied": int, "skipped_existing": int}`.
- Writer `_write_profile_expand(db, intent, result) -> "profile_expansion:<id>"` — `result = {"items": [{target, value, source, ...}]}`; `target ∈ EXPAND_TARGETS`; cada ítem exige `value` y `source` no vacíos.
- Endpoints: `GET /api/profile-expansions` → `{"expansions": [...]}` (última primero); `POST /api/profile-expansions/{id}/apply` body `{"indices": list[int]}` (origin-guarded).

- [ ] **Step 1: Test que falla.** Crear `tests/test_profile_expand.py`:

```python
"""engine/profile_expand.py — aplicación aditiva/idempotente al YAML del perfil (F4 §7.2)."""

from __future__ import annotations

import pytest
import yaml

import engine.paths as paths
from engine import intents
from engine.db.models import DB


@pytest.fixture
def db(tmp_path, monkeypatch):
    # perfil gitignored simulado: un master_cv.yaml en un dir temporal
    master = tmp_path / "master_cv.yaml"
    master.write_text(
        yaml.safe_dump(
            {"basics": {"name": "Ada"}, "skills": ["Python", "SQL"],
             "projects": [], "certifications": []},
            sort_keys=False,
        )
    )
    monkeypatch.setattr(paths, "MASTER_CV_PATH", master)
    with DB(tmp_path / "t.db") as d:
        yield d


def _items() -> list[dict]:
    return [
        {"target": "skills", "value": "Rust", "source": "github.com/ada/ripgrep-fork"},
        {"target": "skills", "value": "Python", "source": "github (ya existe)"},  # idempotente
        {"target": "certification",
         "value": {"name": "CKA", "issuer": "CNCF", "date": "2026"},
         "source": "cncf.io/certification/cka"},
    ]


def test_expand_writer_persists_draft(db):
    iid = intents.enqueue(db, "profile_expand", {"github_user": "ada"})
    intents.mark_running(db, iid)
    ref = intents.apply_result(db, iid, {"items": _items()})
    assert ref.startswith("profile_expansion:")
    exp = db.list_profile_expansions()[0]
    assert len(exp["items"]) == 3
    # nada tocó el YAML todavía (solo draft)
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert cv["skills"] == ["Python", "SQL"]


def test_expand_writer_rejects_bad_target(db):
    iid = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid, {"items": [{"target": "salary", "value": "1M", "source": "dreams"}]}
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_items_is_additive_and_idempotent(db):
    from engine.profile_expand import apply_items

    exp_id = db.add_profile_expansion(intent_id=None, items=_items())
    out = apply_items(exp_id, [0, 1, 2])  # incluye el "Python" ya existente
    assert out["ok"] and out["applied"] == 2 and out["skipped_existing"] == 1
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert "Rust" in cv["skills"]
    assert cv["skills"].count("Python") == 1  # no duplicó
    assert any(c["name"] == "CKA" for c in cv["certifications"])
    # re-aplicar es idempotente
    again = apply_items(exp_id, [0])
    assert again["applied"] == 0 and again["skipped_existing"] == 1
    assert db.get_profile_expansion(exp_id)["items"][0]["applied"] is True
```

- [ ] **Step 2: Correr, esperar FAIL**, luego schema + modelos. `schema.sql`:

```sql
-- Profile expansions (F4 §7.2): additive, source-annotated enrichment drafts from the brain.
-- The web confirms items one by one; only confirmed items are written to the (gitignored)
-- master CV. Nothing here is applied automatically.
CREATE TABLE IF NOT EXISTS profile_expansions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id  TEXT REFERENCES intents(id) ON DELETE SET NULL,
    items      TEXT NOT NULL DEFAULT '[]',    -- json [{target, value, source, applied?}]
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profile_exp_created ON profile_expansions(created_at);
```

`models.py`:

```python
    # ── profile expansions (F4 §7.2) ───────────────────────────────────────────
    def add_profile_expansion(self, *, intent_id: str | None, items: list) -> int:
        cur = self.conn.execute(
            "INSERT INTO profile_expansions (intent_id, items, created_at) VALUES (?,?,?)",
            (intent_id, json.dumps(items), now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_profile_expansion(self, exp_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM profile_expansions WHERE id=?", (exp_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = _loads(d.get("items"), [])
        return d

    def list_profile_expansions(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM profile_expansions ORDER BY created_at DESC LIMIT ?", (int(limit),)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["items"] = _loads(d.get("items"), [])
            out.append(d)
        return out

    def set_profile_expansion(self, exp_id: int, items: list) -> None:
        self.conn.execute(
            "UPDATE profile_expansions SET items=? WHERE id=?", (json.dumps(items), exp_id)
        )
        self.conn.commit()
```

- [ ] **Step 3: Implementar `engine/profile_expand.py`:**

```python
"""Profile expansion — apply the brain's ADDITIVE, source-annotated enrichment to the master
CV, one confirmed item at a time. Idempotent: an item already present is skipped, never
duplicated. Writes ONLY to paths.MASTER_CV_PATH (gitignored) — never anything committed."""

from __future__ import annotations

import yaml

import engine.paths as paths
from engine.db.models import DB

EXPAND_TARGETS = ("skills", "experience_highlight", "project", "certification")


def _load_cv() -> dict:
    path = paths.MASTER_CV_PATH
    if not path.exists():
        raise ValueError(f"master CV not found at {path}; run onboarding first")
    return yaml.safe_load(path.read_text()) or {}


def _dump_cv(cv: dict) -> None:
    paths.MASTER_CV_PATH.write_text(
        yaml.safe_dump(cv, allow_unicode=True, sort_keys=False, width=1000)
    )


def _apply_one(cv: dict, item: dict) -> bool:
    """Add `item` to `cv` if absent. Returns True if it was added, False if already present."""
    target, value = item.get("target"), item.get("value")
    if target == "skills":
        cv.setdefault("skills", [])
        if value in cv["skills"]:
            return False
        cv["skills"].append(value)
        return True
    if target == "experience_highlight":
        exps = cv.get("experience") or []
        if not exps:
            raise ValueError("no experience entry to attach a highlight to")
        # value: {company?, highlight}; attach to the named role or the most recent one.
        target_exp = next(
            (e for e in exps if e.get("company") == (value or {}).get("company")), exps[0]
        )
        hl = target_exp.setdefault("highlights", [])
        text = value["highlight"] if isinstance(value, dict) else value
        if text in hl:
            return False
        hl.append(text)
        return True
    if target == "project":
        cv.setdefault("projects", [])
        name = value.get("name") if isinstance(value, dict) else value
        if any((p.get("name") if isinstance(p, dict) else p) == name for p in cv["projects"]):
            return False
        cv["projects"].append(value)
        return True
    if target == "certification":
        cv.setdefault("certifications", [])
        name = value.get("name") if isinstance(value, dict) else value
        if any(c.get("name") == name for c in cv["certifications"]):
            return False
        cv["certifications"].append(value)
        return True
    raise ValueError(f"unknown target {target!r}; allowed: {EXPAND_TARGETS}")


def apply_items(exp_id: int, indices: list[int]) -> dict:
    """Apply only the confirmed items (by index) to the master CV. Additive + idempotent."""
    with DB() as db:
        exp = db.get_profile_expansion(exp_id)
        if not exp:
            raise ValueError(f"profile_expansion {exp_id} not found")
        items = exp["items"]
        cv = _load_cv()
        applied = skipped = 0
        for i in indices:
            if not 0 <= i < len(items):
                raise ValueError(f"item index {i} out of range")
            item = items[i]
            if item.get("applied"):
                skipped += 1
                continue
            if _apply_one(cv, item):
                item["applied"] = True
                applied += 1
            else:
                item["applied"] = True  # present already → treat as done, don't re-offer
                skipped += 1
        if applied:
            _dump_cv(cv)
        db.set_profile_expansion(exp_id, items)
    return {"ok": True, "applied": applied, "skipped_existing": skipped}
```

- [ ] **Step 4: Writer + context en `engine/intents.py`:**

```python
# ── profile_expand (F4 §7.2) ──────────────────────────────────────────────────
def _ctx_profile_expand(db: DB, intent: dict) -> dict:
    import engine.paths as paths
    from engine.config import load_master_cv

    p = intent["payload"]
    cv = load_master_cv()
    return {
        "master_cv_path": str(paths.MASTER_CV_PATH),
        "current_skills": cv.get("skills") or [],
        "github_user": p.get("github_user"),
        "portfolio_url": p.get("portfolio_url"),
        "cert_names": p.get("cert_names") or [],
    }


def _write_profile_expand(db: DB, intent: dict, result: dict) -> str:
    from engine.profile_expand import EXPAND_TARGETS

    items = result.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("result.items must be a non-empty list")
    for it in items:
        if not isinstance(it, dict) or it.get("target") not in EXPAND_TARGETS:
            raise ValueError(f"every item needs target ∈ {EXPAND_TARGETS}")
        if it.get("value") in (None, "", {}, []):
            raise ValueError("every item needs a non-empty value")
        if not (it.get("source") or "").strip():
            raise ValueError("every item needs a source (provenance is mandatory)")
    exp_id = db.add_profile_expansion(intent_id=intent["id"], items=items)
    return f"profile_expansion:{exp_id}"


_CONTEXT_BUILDERS["profile_expand"] = _ctx_profile_expand
_RESULT_WRITERS["profile_expand"] = _write_profile_expand
```

- [ ] **Step 5: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_profile_expand.py tests/test_intents.py -q`.

- [ ] **Step 6: Prompt.** Crear `brain/prompts/profile_expand.md` completo:

```markdown
# Profile expansion — additive, source-annotated enrichment

You enrich the candidate's master CV by MINING evidence they already produced but never wrote
down: public GitHub repos, their portfolio site, official syllabi of courses/certs they hold.
Every addition is ADDITIVE (you never rewrite or delete), carries a SOURCE, and is idempotent
(if it's already in the CV, don't propose it). The human confirms each item in the web before
anything touches the file.

## Inputs

From `atlas intents context <id>`:
- `current_skills` — what the CV already lists. Do NOT re-propose these.
- `github_user`, `portfolio_url`, `cert_names` — where to look (any may be null).
- `master_cv_path` — Read it for the full current picture before proposing.

## What to scan

- **GitHub** (`github_user`): scan ALL public repos — languages, frameworks, notable projects
  (stars/adoption), topics. A language used across several repos is a real skill; a one-file
  toy is not. Cite the repo URL.
- **Portfolio** (`portfolio_url`): projects, case studies, tools named. Cite the page URL.
- **Certifications** (`cert_names`): fetch each cert's OFFICIAL syllabus on the web and derive
  the concrete skills it certifies (e.g. CKA → "Kubernetes", "Helm"). Cite the syllabus URL.

RE-VERIFY on the live source; never add a skill from memory of what a tool "usually" involves.

## Rules

- Additive only. Never propose removing or rewording existing content.
- Idempotent. Skip anything already in `current_skills` or the CV.
- Source mandatory. Every item needs a real URL or a precise provenance string. No source →
  no item.
- Truthful adjacency, not inflation: "wrote Terraform in 3 repos" is a skill; "starred a
  Kubernetes repo" is not. When unsure, leave it out — the human can't confirm what you can't
  evidence.

## Targets

- `skills` — `value` is a skill string.
- `experience_highlight` — `value` is `{company?, highlight}`; attaches a real, sourced bullet
  to an existing role (or the most recent one).
- `project` — `value` is `{name, description, highlights?}`.
- `certification` — `value` is `{name, issuer, date}`.

## Output — one JSON object

```json
{
  "items": [
    {"target": "skills", "value": "Rust", "source": "github.com/ada — used in 3 repos"},
    {"target": "certification",
     "value": {"name": "CKA", "issuer": "CNCF", "date": "2026"},
     "source": "cncf.io/certification/cka syllabus"}
  ]
}
```

Each item MUST carry `target`, a non-empty `value`, and a non-empty `source`. Order items by
confidence, strongest first.
```

- [ ] **Step 7: Endpoints** en `dashboard/backend/main.py`:

```python
class ApplyExpansionBody(BaseModel):
    indices: list[int]


@app.get("/api/profile-expansions")
def api_profile_expansions(db: DB = Depends(get_db)):
    return {"expansions": db.list_profile_expansions()}


@app.post("/api/profile-expansions/{exp_id}/apply",
          dependencies=[Depends(require_trusted_origin)])
def api_apply_expansion(exp_id: int, body: ApplyExpansionBody, db: DB = Depends(get_db)):
    from engine.profile_expand import apply_items

    if not db.get_profile_expansion(exp_id):
        raise HTTPException(404, "expansion not found")
    try:
        return apply_items(exp_id, body.indices)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
```

- [ ] **Step 8: Frontend.** `api.ts` — tipo + métodos:

```ts
export type ProfileExpandItem = {
  target: "skills" | "experience_highlight" | "project" | "certification";
  value: unknown;
  source: string;
  applied?: boolean;
};
export type ProfileExpansion = {
  id: number;
  items: ProfileExpandItem[];
  created_at: string;
};
```

```ts
  profileExpansions: () => get<{ expansions: ProfileExpansion[] }>("/api/profile-expansions"),
  applyProfileExpansion: (id: number, indices: number[]) =>
    post<{ ok: boolean; applied: number; skipped_existing: number }>(
      `/api/profile-expansions/${id}/apply`,
      { indices },
    ),
```

Crear `dashboard/frontend/src/components/ProfileExpandSection.tsx` (revisión con confirmación
por ítem):

```tsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type ProfileExpandItem, type ProfileExpansion } from "../api";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

const TARGET_ES: Record<ProfileExpandItem["target"], string> = {
  skills: "Skill",
  experience_highlight: "Highlight",
  project: "Proyecto",
  certification: "Certificación",
};

function itemLabel(it: ProfileExpandItem): string {
  if (typeof it.value === "string") return it.value;
  const v = it.value as Record<string, unknown>;
  return String(v.name ?? v.highlight ?? JSON.stringify(v));
}

export function ProfileExpandSection() {
  const [exp, setExp] = useState<ProfileExpansion | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const refresh = () =>
    api.profileExpansions().then((r) => setExp(r.expansions[0] ?? null));
  useEffect(() => {
    refresh();
  }, []);

  function toggle(i: number) {
    setPicked((s) => {
      const n = new Set(s);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });
  }
  async function applyPicked() {
    if (!exp || picked.size === 0) return;
    try {
      const r = await api.applyProfileExpansion(exp.id, [...picked]);
      toast.success(`Aplicados ${r.applied}, ya existían ${r.skipped_existing}.`);
      setPicked(new Set());
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-caption text-muted-foreground uppercase">Expandir perfil</div>
        <IntentConfirmDialog
          buttonLabel="Escanear y proponer"
          title="Expandir perfil desde GitHub / portfolio / certs"
          what="El brain escanea tu GitHub, tu portfolio y los syllabi oficiales de tus certs para encontrar evidencia que aún no está en tu CV. Todo aditivo y con fuente anotada."
          produces="Un borrador de adiciones que confirmas una por una antes de que toquen tu CV."
          where="Aquí, en Ajustes, tras correr el brain."
          type="profile_expand"
        />
      </div>
      {!exp && (
        <Card className="p-3.5 text-[0.8rem] text-muted-foreground">
          Sin propuestas. Pide un escaneo y corre el brain.
        </Card>
      )}
      {exp && (
        <Card className="space-y-2 p-3.5 text-sm">
          {exp.items.map((it, i) => (
            <label
              key={i}
              className="flex items-start gap-2 rounded-lg bg-background/60 p-2.5 text-[0.8rem]"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                disabled={!!it.applied}
                checked={it.applied || picked.has(i)}
                onChange={() => toggle(i)}
              />
              <div>
                <Badge variant="secondary">{TARGET_ES[it.target]}</Badge>{" "}
                <span className="font-medium">{itemLabel(it)}</span>
                <div className="text-muted-foreground">Fuente: {it.source}</div>
                {it.applied && <div className="text-muted-foreground">Aplicado ✓</div>}
              </div>
            </label>
          ))}
          <Button size="sm" disabled={picked.size === 0} onClick={applyPicked}>
            Aplicar seleccionados ({picked.size})
          </Button>
        </Card>
      )}
    </div>
  );
}
```

Montar en `SettingsModal.tsx`: importar `ProfileExpandSection` y renderizar
`<ProfileExpandSection />` como una sección más del modal de ajustes (junto a las secciones
de criteria/companies existentes).

- [ ] **Step 9: Correr todo** — `rtk uv run --group dev pytest -q` + `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`.
- [ ] **Step 10: Commit** — `rtk git add brain/prompts/profile_expand.md engine/profile_expand.py engine/db/schema.sql engine/db/models.py engine/intents.py dashboard/backend/main.py dashboard/frontend/src/api.ts dashboard/frontend/src/components/ProfileExpandSection.tsx dashboard/frontend/src/components/SettingsModal.tsx tests/test_profile_expand.py tests/test_intents.py && rtk git commit -m "feat(profile-expand): additive source-annotated enrichment intent + per-item confirm UI" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 13: Verificación visual del PDF en el pipeline de CV del brain

**Files:**
- Create: `brain/prompts/pdf_check.md` (el checklist que el brain sigue al leer el PDF)
- Create: `engine/cv/pdf_check.py` (`page_count(pdf_path) -> int` + `check_page_count(pdf_path, max_pages, tail_line_slack=5) -> dict` — la parte determinista/comprobable)
- Modify: `brain/run_brain.py` (summary añade `pdf_checks` por job preparado: conteo de páginas determinista, para que el brain sepa cuáles inspeccionar)
- Modify: `brain/SKILL.md` (el paso 4 ya referencia esto — enlazar a `brain/prompts/pdf_check.md`)
- Test: `tests/test_pdf_check.py`

**Interfaces:**
- `pdf_check.page_count(pdf_path: str | Path) -> int` — cuenta páginas del PDF sin dependencias nuevas (usa `pypdf`/`pdfminer` si ya están; si no, cae al conteo de `/Type /Page` en los bytes). `0` si el archivo no existe.
- `pdf_check.check_page_count(pdf_path, *, max_pages: int, tail_line_slack: int = 5) -> dict` → `{"pages": int, "max_pages": int, "ok": bool, "reason": str}`. `ok=False` si `pages > max_pages` (una 3ª página con <5 líneas se considera fail — el brain lo verifica leyendo; aquí solo el conteo duro).
- `run_brain.run(...)` summary gana `"pdf_checks": [{"job_id", "pdf_path", "pages", "ok", "reason"}]` para cada `prepared` con PDF — el brain lee solo los `ok=False` para arreglar y los `ok=True` para el checklist visual (huérfanos/fuentes) que no es determinista.

- [ ] **Step 1: Test que falla.** Crear `tests/test_pdf_check.py`:

```python
"""engine/cv/pdf_check.py — conteo de páginas determinista para la verificación visual (F4)."""

from __future__ import annotations

import pytest

from engine.cv.pdf_check import check_page_count, page_count


def _one_page_pdf(path):
    # PDF mínimo válido de UNA página (suficiente para probar el contador determinista).
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
        b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    return path


def test_page_count_missing_file_is_zero():
    assert page_count("/does/not/exist.pdf") == 0


def test_page_count_single_page(tmp_path):
    pdf = _one_page_pdf(tmp_path / "cv.pdf")
    assert page_count(pdf) == 1


def test_check_page_count_ok_within_limit(tmp_path):
    pdf = _one_page_pdf(tmp_path / "cv.pdf")
    out = check_page_count(pdf, max_pages=2)
    assert out["ok"] is True and out["pages"] == 1 and out["max_pages"] == 2


def test_check_page_count_fails_over_limit(tmp_path, monkeypatch):
    pdf = _one_page_pdf(tmp_path / "cv.pdf")
    # forzamos un conteo de 3 páginas para probar la rama de fallo sin construir un PDF grande
    monkeypatch.setattr("engine.cv.pdf_check.page_count", lambda p: 3)
    out = check_page_count(pdf, max_pages=2)
    assert out["ok"] is False and out["pages"] == 3
    assert "3" in out["reason"] and "2" in out["reason"]
```

- [ ] **Step 2: Correr, esperar FAIL**, luego crear `engine/cv/pdf_check.py`:

```python
"""Deterministic PDF page-count check — the machine-verifiable half of the brain's visual CV
review (F4 §7.2). The brain does the rest by READING the rendered PDF (orphaned headings,
mixed fonts) — that judgment is not deterministic and lives in brain/prompts/pdf_check.md.

No new dependency: use pypdf if it's already installed (it ships with reportlab's ecosystem
in most setups); otherwise fall back to counting `/Type /Page` objects in the raw bytes, which
is exact for the single-column PDFs engine/cv/render.py produces."""

from __future__ import annotations

import re
from pathlib import Path


def page_count(pdf_path: str | Path) -> int:
    p = Path(pdf_path)
    if not p.exists():
        return 0
    try:
        from pypdf import PdfReader  # type: ignore

        return len(PdfReader(str(p)).pages)
    except Exception:  # noqa: BLE001 — any import/parse failure falls back to byte scan
        pass
    data = p.read_bytes()
    # Count page objects, not the /Pages tree node: `/Type /Page` NOT followed by `s`.
    return len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", data)) or 1


def check_page_count(
    pdf_path: str | Path, *, max_pages: int, tail_line_slack: int = 5
) -> dict:
    """Fail when the CV spills past `max_pages`. `tail_line_slack` documents the human rule
    (a 3rd page with under N lines is still a fail); the deterministic gate is the page count,
    the line judgment is the brain's when it reads the PDF."""
    pages = page_count(pdf_path)
    ok = 0 < pages <= max_pages
    if pages == 0:
        reason = "PDF ausente o ilegible"
    elif ok:
        reason = f"{pages} página(s) ≤ {max_pages}"
    else:
        reason = (
            f"{pages} páginas > {max_pages} permitidas (una página extra con menos de "
            f"{tail_line_slack} líneas igual cuenta como fallo)"
        )
    return {"pages": pages, "max_pages": max_pages, "ok": ok, "reason": reason}
```

- [ ] **Step 3: Correr, esperar PASS** — `rtk uv run --group dev pytest tests/test_pdf_check.py -q` → `5 passed`.

- [ ] **Step 4: Cablear en `brain/run_brain.py`.** Import: `from engine.cv.pdf_check import check_page_count`. En `run()`, tras el bucle de preparación (después de que `summary["prepared"]` esté poblado, antes de los follow-ups), añadir:

```python
    # F4 §7.2 — deterministic half of the visual PDF check. Count pages for every CV we
    # prepared today so the brain (SKILL step 4) knows which PDFs to open and fix. The
    # non-deterministic half (orphaned headings, mixed fonts) is the brain reading the PDF.
    from engine.config import load_cv_layout

    max_pages = int((load_cv_layout().get("max_pages") or 2))
    summary["pdf_checks"] = []
    for prep in summary["prepared"]:
        versions = db.cv_versions_for(prep["id"])
        pdf = versions[0].get("path_pdf") if versions else None
        if not pdf:
            continue
        chk = check_page_count(pdf, max_pages=max_pages)
        summary["pdf_checks"].append({"job_id": prep["id"], "pdf_path": pdf, **chk})
```

y en `run()`'s summary dict inicial (junto a `"prepared": []`), añadir `"pdf_checks": []` para
que la clave exista aunque no haya jobs. En `write_morning_brief()`, tras la sección de
`prepare_errors`, listar los PDFs que fallan el conteo:

```python
    bad_pdfs = [c for c in summary.get("pdf_checks", []) if not c["ok"]]
    if bad_pdfs:
        lines += ["", "## ⚠︎ CVs que exceden el límite de páginas (arréglalos antes de enviar)"]
        lines += [f"- {c['job_id']}: {c['reason']}" for c in bad_pdfs]
```

- [ ] **Step 5: Test del cableado** (añadir a `tests/test_brain_intents.py`):

```python
def test_run_reports_pdf_checks_key(tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    from brain.run_brain import run
    from engine.db.models import DB

    with DB(tmp_path / "t.db") as db:
        summary = run(db, do_discover=False)
    assert summary["pdf_checks"] == []  # sin jobs preparados → lista vacía, clave presente
```

- [ ] **Step 6: Prompt.** Crear `brain/prompts/pdf_check.md` (el checklist que sigue SKILL paso 4):

```markdown
# Visual PDF check — the brain reads its own CV output before trusting it

`atlas brain` renders a DOCX+PDF per prepared job and reports a deterministic page count in
the run summary (`pdf_checks`). That count is the machine half. This prompt is the HUMAN half:
open the rendered PDF and judge what a page count can't.

## Procedure (SKILL step 4, per prepared job)

1. Read the run summary's `pdf_checks`. Any entry with `ok: false` already exceeds the page
   limit — fix it first (see below). For every entry, still do the visual pass.
2. **Read the actual PDF** with the Read tool: `data/outbox/<job_id>/cv_<lang>.pdf`. Do not
   reason about a PDF you have not opened.
3. Checklist:
   - **Pages**: exactly within the target (default ≤ 2). A 3rd page carrying fewer than 5
     lines is a FAIL, not a rounding tolerance.
   - **No orphaned headings**: a section title must not sit alone at the bottom of a page with
     its content on the next.
   - **Consistent fonts/sizes**: one family throughout; no stray bold/size jumps.
   - **Six-second gate** (style_rules.md): the top third of page 1 makes the fit obvious.

## Fixing (max 2 iterations)

When a check fails:
1. `uv run atlas --profile owner cv dump <job_id>` → writes
   `data/outbox/<job_id>/cv_for_review.yaml`.
2. Edit that YAML to fix the issue. To lose a page: trim the LEAST JD-relevant highlights
   (drop whole bullets; never reword a fact, never invent one). To fix an orphan: shorten the
   preceding section.
3. Re-render and re-check:
   ```bash
   uv run python -c "
   import yaml
   from engine.db.models import DB
   from engine.cv.build import build_for_job
   cv = yaml.safe_load(open('data/outbox/<job_id>/cv_for_review.yaml'))
   with DB() as db: build_for_job(db, '<job_id>', language='<lang>', cv_override=cv)"
   ```
4. Read the new PDF. Repeat AT MOST twice. If it still fails, report it in your summary
   ("<job_id>: still 3 pages after 2 trims — needs manual attention") instead of looping.

Never fix a layout problem by fabricating or removing TRUE content beyond trimming the least
relevant bullets. Accuracy over layout, always.
```

- [ ] **Step 7: Enlazar desde `brain/SKILL.md`.** El paso 4 (ya escrito en Task 4) describe el
  checklist inline; añadir una línea al inicio de ese paso: "Sigue `brain/prompts/pdf_check.md`
  al pie de la letra." (edición mínima; no reescribir el paso).

- [ ] **Step 8: Correr todo** — `rtk uv run --group dev pytest tests/test_pdf_check.py tests/test_brain_intents.py -q` + suite completa `rtk uv run --group dev pytest -q`.
- [ ] **Step 9: Commit** — `rtk git add engine/cv/pdf_check.py brain/prompts/pdf_check.md brain/run_brain.py brain/SKILL.md tests/test_pdf_check.py tests/test_brain_intents.py && rtk git commit -m "feat(cv): deterministic PDF page-count gate + brain visual-check prompt wired into run" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 14: Gate final F4 — suite completa, build, end-to-end manual, cierre de rama

**Files:**
- (verificación; sin código nuevo salvo posibles fixes que surjan del gate)

**Interfaces:** ninguna nueva — esta tarea VERIFICA que todo lo de F4 encaja y cierra la rama.

- [ ] **Step 1: Backend completo verde** — `rtk uv run --group dev pytest -q`. Debe pasar toda la
  suite (los ~117+ tests previos + los nuevos de F4: `test_intents`, `test_intents_api`,
  `test_cv_review`, `test_upskill`, `test_profile_expand`, `test_pdf_check`, `test_brain_intents`).
  Si algo falla, arréglalo antes de seguir (skill systematic-debugging) — no marques done sin verde.

- [ ] **Step 2: Lint backend** — `uv run ruff check engine dashboard/backend brain` limpio
  (línea ≤ 100). `uv run ruff format --check engine dashboard/backend brain` si el repo lo usa.

- [ ] **Step 3: Frontend verde + build** —
  `npm --prefix dashboard/frontend run typecheck`,
  `npm --prefix dashboard/frontend run lint`,
  `npm --prefix dashboard/frontend test` (incluye `BrainTasksPanel.test.tsx`),
  `npm --prefix dashboard/frontend run build` (o `vite build`) sin errores.

- [ ] **Step 4: Gate del repo** — `./scripts/check.sh` verde de punta a punta.

- [ ] **Step 5: Prueba end-to-end MANUAL documentada** (verification-before-completion). Levantar
  backend + frontend con las preview tools y recorrer el guided handoff de verdad:
  1. En una vacante, abrir el detalle → tab CV → "Pedir revisión" (`IntentConfirmDialog`) →
     confirmar. Verificar el toast "Encolado…".
  2. Abrir el panel "Tareas del Brain" (badge = 1) → ver el intent `cv_review` en `pending` y la
     frase universal copiable.
  3. En una sesión de Claude Code sobre este repo, decir **`corre atlas`**. El brain debe:
     drenar el intent (paso 0), leer `brain/prompts/cv_review.md`, producir el JSON de resultado,
     y completarlo con `atlas intents complete`. Confirmar en consola `✓ … → done (cv_review:N)`.
  4. Volver a la web → refrescar → el intent aparece `done`, y en el detalle del job la
     `CvReviewPanel` muestra la crítica en 4 categorías + edits/flags. Aplicar un edit → toast
     "Edit aplicado — CV re-renderizado" y el PDF/DOCX se regeneran.
  5. Repetir el ciclo abreviado para al menos un tipo más (p. ej. `upskill_report` desde
     `/upskill`, o `legitimacy_batch` desde el shortlist) para confirmar que el drenaje es
     genérico, no cableado a un solo tipo.
  Anotar cada paso y su resultado observado (captura o texto) — evidencia antes de aseverar.

- [ ] **Step 6: Verificar doctrina $0 y privacidad** —
  - `rtk proxy grep -rn "anthropic\|ANTHROPIC_API_KEY\|openai\|import anthropic" dashboard/backend engine`
    NO debe devolver ninguna llamada a una API LLM (la doctrina $0 se mantiene: el backend solo
    encola y lee).
  - `rtk git status` y `rtk git diff --stat`: confirmar que NO se está por commitear ningún dato
    personal — solo prompts genéricos en `brain/prompts/`, código y tests. Los perfiles/DB/outbox
    (`profiles/`, `data/`, `profile/master_cv.yaml`) están gitignorados y NO aparecen en el diff.
    Si algún dato personal aparece staged, quítalo (`rtk git restore --staged <file>`) y avisa.

- [ ] **Step 7: Code review** — invocar `superpowers:requesting-code-review` sobre el diff completo
  de la rama F4 (subagente revisor: Critical/Important/Minor). Resolver los Critical/Important
  antes de cerrar; los Minor a criterio.

- [ ] **Step 8: Cierre de rama** — `superpowers:finishing-a-development-branch`. Verifica tests →
  menú merge/PR/keep/descartar. Atlas es repo personal PERO `master` está protegido (PR + 1
  review, ver memoria "Atlas repo is public"): elegir **crear PR**, NO auto-merge. El PR describe
  F4 (intents + guided handoff + las 6 features LLM + verificación visual de PDF) y enlaza el
  spec §7. Cuerpo del PR con el trailer:

  ```
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  ```

  El merge a `master` es decisión del usuario — NO mergear por iniciativa propia.

---
