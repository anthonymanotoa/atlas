# Atlas v2 — Fase 3: Features deterministas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la sección §6 del spec `docs/superpowers/specs/2026-07-04-atlas-v2-design.md`: follow-ups v2 con cadencia por estado y buckets, analytics con loop de aprendizaje accionable, story bank STAR+R con matcher determinista, knock-out pre-scan, reverse ATS discovery honesto, exposición web de los comandos CLI-only (resolve-ats, import-connections, salud del sistema) y machine summary del score persistido por corrida. Todo determinista, $0 en LLM.

**Architecture:** El motor (`engine/`) gana funciones puras nuevas (`engine/outreach/followups.py` extendido, `engine/analytics.py` extendido, `engine/stories.py`, `engine/knockouts.py`, `engine/discovery/reverse.py`) que leen/escriben SQLite vía `engine/db/models.py` (migraciones aditivas con el patrón `_ensure_column` existente + tabla nueva `stories` en `schema.sql`). `dashboard/backend/main.py` expone endpoints nuevos (POSTs origin-guarded con `require_trusted_origin`). El frontend (post-F1: react-router + TanStack Query) añade vistas `/followups`, `/stories`, amplía `/analytics` y `/settings`, y enriquece card/detalle con chips de knock-out y desglose de score. Los writers de configuración (`update_criteria_fields`, `save_company` en `engine/config.py`) escriben SOLO en las rutas del perfil activo (gitignoradas).

**Tech Stack:** Python 3.11 (FastAPI, pydantic v2, httpx, PyYAML, sqlite3 WAL), pytest vía `rtk uv run --group dev pytest`; React 19 + TypeScript + Tailwind v4 + shadcn primitivos existentes (`src/components/ui/*`), react-router v7 + TanStack Query (decididos en F1), Vitest + Testing Library. **Cero dependencias frontend nuevas** (charts en SVG inline). Backend: una dependencia nueva `python-multipart` (upload de Connections.csv).

## Global Constraints

1. **Tests backend SIEMPRE** `rtk uv run --group dev pytest ...` (NUNCA `pytest` a secas ni `--extra dev`). Frontend: `npm --prefix dashboard/frontend test` y `npm --prefix dashboard/frontend run build`.
2. **TDD estricto**: cada step escribe el test primero (RED), luego la implementación mínima (GREEN). Un test nuevo debe FALLAR antes de implementar.
3. **POSTs mutantes** llevan `dependencies=[Depends(require_trusted_origin)]` — sin excepción (patrón plan 020, ya en `dashboard/backend/main.py:88`).
4. **Migraciones**: columnas nuevas SOLO vía `DB._ensure_column()` en `_migrate()` (`engine/db/models.py:62`); tablas nuevas SOLO vía `CREATE TABLE IF NOT EXISTS` en `engine/db/schema.sql`. Idempotentes: corren en cada arranque.
5. **Repo PÚBLICO**: ejemplos y fixtures con datos ficticios ("Acme", "Jane Doe"). Los writers (`criteria.md`, `companies.yaml`, `discovery_seeds.yaml`) escriben en `paths.CRITERIA_PATH`/`paths.COMPANIES_PATH`/`paths.CONFIG_DIR` del perfil activo (gitignorados), jamás en los `.example` commiteados.
6. **Prerequisito**: F1 (router + TanStack Query, `src/hooks/`, vistas por ruta) y F2 (onboarding + geo) mergeadas a `master` antes de ejecutar este plan. Donde este plan integra con archivos creados por F1 (tabla de rutas, vista Settings), el step da el código exacto a insertar y el comando `rtk grep` para localizar el punto de inserción real.
7. **Commits**: añadir archivos POR NOMBRE (`rtk git add <file1> <file2>`, nunca `git add .`/`-A`), un commit por tarea, mensaje `feat(f3): ...` terminado en `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
8. **Paths late-bound**: siempre `import engine.paths as paths` y leer `paths.X` en runtime (nunca `from engine.paths import X`) — regla existente para que el switch de perfil funcione.
9. El fixture `atlas_app` de `tests/conftest.py` ya redirige la DB a un tmp_path — todos los tests de API nuevos lo usan con `TestClient(atlas_app)` como context manager (para que corra el lifespan).

## File Structure

```
engine/
  db/
    schema.sql                     # EDIT: + CREATE TABLE stories
    models.py                      # EDIT: _migrate() (3 columnas), set_fit(+warnings/+breakdown),
                                   #       add_followup(+kind), pending_followups(), stories CRUD
  config.py                        # EDIT: Criteria.followup_cadence; update_criteria_fields();
                                   #       save_company(); load_discovery_seeds()
  outreach/followups.py            # EDIT: cadence_for, seed_for_state, register_sent,
                                   #       bucket_followups, cold_jobs, draft_followup
  analytics.py                     # EDIT: funnel, score_floor, conversion_by, response_times,
                                   #       recommendations, analytics_payload; job_detail parsea
                                   #       knockout_warnings + score_breakdown
  stories.py                       # NEW: match_stories, format_story
  knockouts.py                     # NEW: prescan
  scoring/fit.py                   # EDIT: ScoreResult.factors + breakdown(); score_job registra deltas
  scoring/run.py                   # EDIT: persiste warnings + breakdown al scorear
  discovery/reverse.py             # NEW: slug_candidates, probe_company, suggest_companies
brain/run_brain.py                 # EDIT: el drain salta follow-ups con kind (v2 = confirmación humana)
config/seeds/{default,data,architecture}/discovery_seeds.yaml   # NEW (ejemplos ficticios)
engine/profiles.py                 # EDIT: _SEED_FILES += discovery_seeds.yaml
dashboard/backend/main.py          # EDIT: endpoints F3 (followups, analytics, stories, companies,
                                   #       discovery, connections, system/health)
dashboard/frontend/src/
  api.ts                           # EDIT: tipos + funciones F3 (+ postForm)
  hooks/useFollowups.ts            # NEW
  hooks/useAnalytics.ts            # NEW
  hooks/useStories.ts              # NEW
  hooks/useOps.ts                  # NEW (resolve/add company, suggest, import, health)
  views/FollowupsView.tsx          # NEW (ruta /followups)
  views/StoriesView.tsx            # NEW (ruta /stories)
  views/AnalyticsView.tsx          # EDIT (F1 la crea; F3 la amplía: funnel SVG, conversiones, recs)
  components/KnockoutChips.tsx     # NEW (card + detalle)
  components/ScoreBreakdown.tsx    # NEW (detalle del job)
  components/SettingsOps.tsx       # NEW (salud + empresas + connections, embebido en Settings)
  test/renderWithQuery.tsx         # NEW (helper de tests con QueryClientProvider)
pyproject.toml                     # EDIT: + python-multipart
tests/
  test_f3_db.py                    # NEW
  test_f3_config_writers.py        # NEW
  test_f3_followups_v2.py          # NEW
  test_f3_analytics.py             # NEW
  test_f3_stories.py               # NEW
  test_f3_knockouts.py             # NEW
  test_f3_score_breakdown.py       # NEW
  test_f3_reverse_discovery.py     # NEW
  test_f3_backend_api.py           # NEW
  test_backend_api.py              # EDIT: cadencia applied pasa de 4 touches legacy a 1 seed v2
```

---

## Task 1 — Migraciones DB: columnas F3, tabla `stories`, helpers de acceso

**Files:**
- `engine/db/schema.sql` (EDIT)
- `engine/db/models.py` (EDIT)
- `tests/test_f3_db.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/db/models.py
def set_fit(self, job_id: str, score: float, reasons: list[str], knockouts: list[str],
            *, warnings: list[dict] | None = None, breakdown: dict | None = None) -> None
def add_followup(self, job_id: str, *, channel: str, touch_number: int, due_at: str,
                 message_id: int | None = None, kind: str | None = None) -> int
def pending_followups(self) -> list[dict]          # join followups+jobs, state='pending'
def add_story(self, *, title: str, situation: str = "", task: str = "", action: str = "",
              result: str = "", reflection: str = "", skills: list[str] | None = None) -> int
def get_story(self, story_id: int) -> dict | None  # skills ya parseado a list[str]
def list_stories(self) -> list[dict]               # skills ya parseado a list[str]
def update_story(self, story_id: int, fields: dict) -> bool
def delete_story(self, story_id: int) -> bool
```

Columnas nuevas (migración aditiva): `jobs.knockout_warnings TEXT` (json list de warnings §6.4), `jobs.score_breakdown TEXT` (json dict §6.5 machine summary), `followups.kind TEXT` (NULL = touch legacy plan 006; `applied|responded|interview` = cadencia v2 §6.1).

**Steps:**

- [ ] RED — crear `tests/test_f3_db.py`:

```python
"""F3: migraciones aditivas (knockout_warnings, score_breakdown, followups.kind) + tabla stories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _seed(db: DB) -> str:
    db.upsert_job(Job(source="greenhouse", title="Data Scientist", company="Acme", location="Remote"))
    return db.list_jobs()[0]["id"]


def test_migration_adds_f3_columns(db: DB):
    cols_jobs = {r["name"] for r in db.conn.execute("PRAGMA table_info(jobs)")}
    cols_fu = {r["name"] for r in db.conn.execute("PRAGMA table_info(followups)")}
    assert {"knockout_warnings", "score_breakdown"} <= cols_jobs
    assert "kind" in cols_fu


def test_set_fit_persists_warnings_and_breakdown(db: DB):
    jid = _seed(db)
    db.set_fit(jid, 71.0, ["role matches title"], [],
               warnings=[{"code": "work_authorization", "label": "pide autorización US", "evidence": "authorized to work in the US"}],
               breakdown={"base": 50.0, "final": 71.0, "factors": [{"factor": "role", "delta": 25.0, "note": "role matches title"}]})
    row = db.get_job(jid)
    assert json.loads(row["knockout_warnings"])[0]["code"] == "work_authorization"
    assert json.loads(row["score_breakdown"])["final"] == 71.0


def test_set_fit_without_kwargs_keeps_previous_breakdown(db: DB):
    jid = _seed(db)
    db.set_fit(jid, 71.0, [], [], breakdown={"base": 50.0, "final": 71.0, "factors": []})
    db.set_fit(jid, 60.0, [], [])  # llamada legacy: no borra el breakdown previo
    assert json.loads(db.get_job(jid)["score_breakdown"])["final"] == 71.0


def test_add_followup_with_kind(db: DB):
    jid = _seed(db)
    fid = db.add_followup(jid, channel="email", touch_number=1, due_at="2026-07-11T00:00:00+00:00", kind="applied")
    rows = db.followups_for_job(jid)
    assert rows and rows[0]["id"] == fid and rows[0]["kind"] == "applied"


def test_pending_followups_joins_job_fields(db: DB):
    jid = _seed(db)
    db.add_followup(jid, channel="email", touch_number=1, due_at="2026-07-11T00:00:00+00:00", kind="applied")
    rows = db.pending_followups()
    assert rows[0]["company"] == "Acme" and rows[0]["title"] == "Data Scientist"
    assert rows[0]["job_id"] == jid and rows[0]["state"] == "pending"


def test_stories_crud_roundtrip(db: DB):
    sid = db.add_story(title="Pipeline caído en Black Friday", situation="ETL crítico caído",
                       task="Restaurar en <1h", action="Rollback + circuit breaker",
                       result="Recuperado en 40min", reflection="Alertas proactivas desde entonces",
                       skills=["python", "airflow"])
    s = db.get_story(sid)
    assert s["title"].startswith("Pipeline") and s["skills"] == ["python", "airflow"]
    assert db.update_story(sid, {"result": "Recuperado en 35min", "skills": ["python", "sql"]}) is True
    s2 = db.get_story(sid)
    assert s2["result"] == "Recuperado en 35min" and s2["skills"] == ["python", "sql"]
    assert s2["updated_at"] >= s["updated_at"]
    assert len(db.list_stories()) == 1
    assert db.delete_story(sid) is True
    assert db.list_stories() == [] and db.get_story(sid) is None


def test_update_story_rejects_unknown_field(db: DB):
    sid = db.add_story(title="X")
    with pytest.raises(ValueError):
        db.update_story(sid, {"evil": "x"})


def test_delete_story_unknown_id_returns_false(db: DB):
    assert db.delete_story(99999) is False
```

- [ ] Correr y ver el fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_db.py -x
```
Esperado: `AssertionError` en `test_migration_adds_f3_columns` (las columnas no existen).

- [ ] GREEN — `engine/db/schema.sql`: añadir al final (tras `peer_portfolios`):

```sql
-- Story bank STAR+R (F3 §6.3). Vive en la DB del perfil activo (una por perfil).
-- El matcher determinista (engine/stories.py) rankea por overlap de tokens/skills.
CREATE TABLE IF NOT EXISTS stories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    situation   TEXT DEFAULT '',
    task        TEXT DEFAULT '',
    action      TEXT DEFAULT '',
    result      TEXT DEFAULT '',
    reflection  TEXT DEFAULT '',
    skills      TEXT DEFAULT '[]',              -- json array de tags de skill
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

- [ ] GREEN — `engine/db/models.py`, en `_migrate()` (línea ~70), añadir tras las tres `_ensure_column` existentes:

```python
        # F3 (plan 2026-07-04): knock-out pre-scan + machine summary + cadencia v2.
        self._ensure_column("jobs", "knockout_warnings", "TEXT")
        self._ensure_column("jobs", "score_breakdown", "TEXT")
        self._ensure_column("followups", "kind", "TEXT")
```

- [ ] GREEN — reemplazar `set_fit` (models.py línea ~196) por:

```python
    def set_fit(
        self,
        job_id: str,
        score: float,
        reasons: list[str],
        knockouts: list[str],
        *,
        warnings: list[dict] | None = None,
        breakdown: dict | None = None,
    ) -> None:
        """Persist the fit result. `warnings` (§6.4) and `breakdown` (§6.5) are optional so
        legacy callers keep working; COALESCE preserves the previous value when omitted."""
        self.conn.execute(
            """UPDATE jobs SET fit_score=?, fit_reasons=?, knockout_flags=?,
                 knockout_warnings=COALESCE(?, knockout_warnings),
                 score_breakdown=COALESCE(?, score_breakdown)
               WHERE id=?""",
            (
                score,
                json.dumps(reasons),
                json.dumps(knockouts),
                json.dumps(warnings) if warnings is not None else None,
                json.dumps(breakdown) if breakdown is not None else None,
                job_id,
            ),
        )
        self.conn.commit()
```

- [ ] GREEN — reemplazar `add_followup` (models.py línea ~382) por:

```python
    def add_followup(
        self,
        job_id: str,
        *,
        channel: str,
        touch_number: int,
        due_at: str,
        message_id: int | None = None,
        kind: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO followups (job_id, message_id, channel, touch_number, due_at, kind, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (job_id, message_id, channel, touch_number, due_at, kind, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)
```

- [ ] GREEN — añadir tras `due_followups` (models.py línea ~414):

```python
    def pending_followups(self) -> list[dict]:
        """Every pending follow-up joined with its job (company/title/state) — feeds /followups."""
        rows = self.conn.execute(
            """SELECT f.*, j.title, j.company, j.state AS job_state, j.applied_at
               FROM followups f JOIN jobs j ON j.id = f.job_id
               WHERE f.state='pending' ORDER BY f.due_at"""
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] GREEN — añadir el bloque stories al final de la clase `DB` (antes de `def _b(...)`):

```python
    # ── story bank STAR+R (F3 §6.3) ───────────────────────────────────────────
    _STORY_TEXT_FIELDS = ("title", "situation", "task", "action", "result", "reflection")

    def add_story(
        self,
        *,
        title: str,
        situation: str = "",
        task: str = "",
        action: str = "",
        result: str = "",
        reflection: str = "",
        skills: list[str] | None = None,
    ) -> int:
        now = now_iso()
        cur = self.conn.execute(
            """INSERT INTO stories
               (title, situation, task, action, result, reflection, skills, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (title, situation, task, action, result, reflection, json.dumps(skills or []), now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _story_row(self, row) -> dict:
        d = dict(row)
        d["skills"] = _loads(d.get("skills"), [])
        return d

    def get_story(self, story_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
        return self._story_row(row) if row else None

    def list_stories(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM stories ORDER BY updated_at DESC").fetchall()
        return [self._story_row(r) for r in rows]

    def update_story(self, story_id: int, fields: dict) -> bool:
        """Partial update. Only STAR+R text fields and `skills` are writable."""
        allowed = set(self._STORY_TEXT_FIELDS) | {"skills"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown story fields: {sorted(unknown)}")
        if not fields:
            return False
        sets, params = [], []
        for k, v in fields.items():
            sets.append(f"{k}=?")
            params.append(json.dumps(v or []) if k == "skills" else str(v or ""))
        sets.append("updated_at=?")
        params.extend([now_iso(), story_id])
        cur = self.conn.execute(f"UPDATE stories SET {', '.join(sets)} WHERE id=?", params)
        self.conn.commit()
        return cur.rowcount > 0

    def delete_story(self, story_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM stories WHERE id=?", (story_id,))
        self.conn.commit()
        return cur.rowcount > 0
```

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_db.py tests/test_engine.py -x
```
Esperado: `8 passed` en test_f3_db.py y la suite de engine intacta (sin regresiones).

- [ ] Commit:

```bash
rtk git add engine/db/schema.sql engine/db/models.py tests/test_f3_db.py
rtk git commit -m "feat(f3): DB migrations — knockout_warnings, score_breakdown, followups.kind + stories table

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2 — Config: `followup_cadence` en Criteria + writers `update_criteria_fields` / `save_company` / `load_discovery_seeds`

**Files:**
- `engine/config.py` (EDIT)
- `tests/test_f3_config_writers.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/config.py
class Criteria(BaseModel):
    ...
    followup_cadence: dict[str, dict[str, int]]  # default: applied 7d/max2, responded 1d/max1, interview 1d/max1

CRITERIA_WRITABLE_FIELDS = frozenset({"shortlist_threshold", "company_blocklist", "followup_cadence"})

def update_criteria_fields(updates: dict[str, Any]) -> Criteria
def save_company(entry: dict) -> bool          # False si ya existe (dedupe por company o ats+token)
def load_discovery_seeds() -> list[str]        # candidatas de config/discovery_seeds.yaml (o su .example)
```

Nota de coordinación con F2: F2 añade `GET/PUT /api/criteria` (escritura completa del frontmatter). `update_criteria_fields` es el helper de PATCH parcial que necesita el apply-rec de F3; si al ejecutar este plan F2 ya dejó en `engine/config.py` un writer equivalente (verificar con `rtk grep -n "def.*criteria" engine/config.py`), reutilizarlo y adaptar solo la whitelist — el contrato de este task (firma + tests) se mantiene.

**Steps:**

- [ ] RED — crear `tests/test_f3_config_writers.py`:

```python
"""F3: cadencia configurable + writers de criteria/companies (escriben SOLO rutas del perfil)."""

from __future__ import annotations

import importlib

import pytest
import yaml


@pytest.fixture
def cfg_env(tmp_path, monkeypatch):
    """Config aislada en tmp_path: reapunta paths y recarga config."""
    import engine.config
    import engine.paths

    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "data"))
    importlib.reload(engine.paths)
    engine.paths._apply(None)
    monkeypatch.setattr(engine.paths, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(engine.paths, "CRITERIA_PATH", tmp_path / "config" / "criteria.md")
    monkeypatch.setattr(engine.paths, "COMPANIES_PATH", tmp_path / "config" / "companies.yaml")
    importlib.reload(engine.config)
    return engine.config


def test_followup_cadence_defaults(cfg_env):
    c = cfg_env.Criteria()
    assert c.followup_cadence["applied"] == {"days": 7, "max_touches": 2}
    assert c.followup_cadence["responded"] == {"days": 1, "max_touches": 1}
    assert c.followup_cadence["interview"] == {"days": 1, "max_touches": 1}


def test_update_criteria_fields_patches_frontmatter_preserving_prose(cfg_env):
    import engine.paths as paths

    paths.CRITERIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.CRITERIA_PATH.write_text("---\nroles: [data scientist]\nshortlist_threshold: 60\n---\n\nProsa para el brain.\n")
    merged = cfg_env.update_criteria_fields({"shortlist_threshold": 68.0})
    assert merged.shortlist_threshold == 68.0
    text = paths.CRITERIA_PATH.read_text()
    assert "shortlist_threshold: 68" in text
    assert "Prosa para el brain." in text          # la prosa sobrevive
    assert "data scientist" in text                 # los campos no tocados sobreviven
    assert cfg_env.load_criteria().shortlist_threshold == 68.0


def test_update_criteria_fields_rejects_non_writable(cfg_env):
    with pytest.raises(ValueError):
        cfg_env.update_criteria_fields({"roles": ["hacker"]})


def test_update_criteria_fields_validates_before_writing(cfg_env):
    import engine.paths as paths

    paths.CRITERIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.CRITERIA_PATH.write_text("---\nshortlist_threshold: 60\n---\n\nx\n")
    with pytest.raises(Exception):  # pydantic ValidationError
        cfg_env.update_criteria_fields({"shortlist_threshold": "not-a-number"})
    assert "60" in paths.CRITERIA_PATH.read_text()  # el archivo NO cambió


def test_save_company_appends_and_dedupes(cfg_env):
    import engine.paths as paths

    entry = {"company": "Acme Robotics", "ats": "greenhouse", "token": "acmerobotics"}
    assert cfg_env.save_company(entry) is True
    assert cfg_env.save_company(entry) is False  # dup exacto
    assert cfg_env.save_company({"company": "ACME ROBOTICS", "ats": "lever", "token": "x"}) is False  # dup por nombre
    data = yaml.safe_load(paths.COMPANIES_PATH.read_text())
    assert len(data["companies"]) == 1
    assert data["companies"][0]["token"] == "acmerobotics"
    loaded = cfg_env.load_companies()
    assert loaded and loaded[0].ats == "greenhouse"


def test_save_company_rejects_invalid_entry(cfg_env):
    with pytest.raises(Exception):  # pydantic: falta company/ats
        cfg_env.save_company({"token": "x"})


def test_load_discovery_seeds_empty_when_absent(cfg_env):
    assert cfg_env.load_discovery_seeds() == []
```

- [ ] Correr y ver el fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_config_writers.py -x
```
Esperado: `AttributeError: ... has no attribute 'followup_cadence'` (o `update_criteria_fields`).

- [ ] GREEN — `engine/config.py`: dentro de `class Criteria`, después de `max_highlights_per_role` y antes de `prose`:

```python
    # ── Follow-up cadence v2 (F3 §6.1) — días por estado + tope de toques ──
    # applied: primer follow-up a +7d, máx 2 toques → luego COLD; responded: nudge a +1d;
    # interview: thank-you a +1d. Editable por perfil desde criteria.md.
    followup_cadence: dict[str, dict[str, int]] = Field(
        default_factory=lambda: {
            "applied": {"days": 7, "max_touches": 2},
            "responded": {"days": 1, "max_touches": 1},
            "interview": {"days": 1, "max_touches": 1},
        }
    )
```

- [ ] GREEN — `engine/config.py`: añadir tras `load_criteria()`:

```python
CRITERIA_WRITABLE_FIELDS = frozenset({"shortlist_threshold", "company_blocklist", "followup_cadence"})


def update_criteria_fields(updates: dict[str, Any]) -> Criteria:
    """Patch de campos del frontmatter YAML de criteria.md, preservando la prosa.

    Valida el resultado con el modelo Criteria ANTES de escribir (si no valida, el archivo
    no se toca). Escribe SIEMPRE en paths.CRITERIA_PATH (perfil activo, gitignorado);
    si solo existe el .example commiteado, la copia parcheada nace en la ruta real —
    el example jamás se modifica.
    """
    unknown = set(updates) - CRITERIA_WRITABLE_FIELDS
    if unknown:
        raise ValueError(f"non-writable criteria fields: {sorted(unknown)}")
    src = example_fallback(paths.CRITERIA_PATH)
    text = src.read_text() if src.exists() else ""
    meta, prose = _split_frontmatter(text)
    meta.update(updates)
    merged = Criteria(**{**meta, "prose": prose})  # valida antes de escribir
    yaml_block = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    paths.CRITERIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.CRITERIA_PATH.write_text(f"---\n{yaml_block}\n---\n\n{prose}\n")
    return merged
```

- [ ] GREEN — `engine/config.py`: añadir tras `load_companies()`:

```python
def save_company(entry: dict) -> bool:
    """Append a companies.yaml del perfil activo. False si ya existe (mismo nombre, o mismo
    ats+token). Valida con CompanyTarget antes de escribir; nunca toca el .example."""
    target = CompanyTarget(**entry)
    src = example_fallback(paths.COMPANIES_PATH)
    data = (yaml.safe_load(src.read_text()) if src.exists() else {}) or {}
    rows: list[dict] = data.get("companies") or []
    name = target.company.strip().lower()
    for c in rows:
        if (c.get("company") or "").strip().lower() == name:
            return False
        if c.get("ats") == target.ats and (c.get("token") or "") == (target.token or ""):
            return False
    dumped = {k: v for k, v in target.model_dump().items() if v not in (None, "", False)}
    rows.append(dumped)
    data["companies"] = rows
    paths.COMPANIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.COMPANIES_PATH.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return True


def load_discovery_seeds() -> list[str]:
    """Empresas candidatas para el reverse ATS discovery (F3 §6.5), del perfil activo."""
    path = example_fallback(paths.CONFIG_DIR / "discovery_seeds.yaml")
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return [str(n).strip() for n in (data.get("candidates") or []) if str(n).strip()]
```

- [ ] Verificar + regresión de criteria existente:

```bash
rtk uv run --group dev pytest tests/test_f3_config_writers.py tests/test_criteria_fields.py tests/test_frontmatter.py -x
```
Esperado: `8 passed` nuevos + los existentes verdes.

- [ ] Commit:

```bash
rtk git add engine/config.py tests/test_f3_config_writers.py
rtk git commit -m "feat(f3): followup_cadence en Criteria + writers update_criteria_fields/save_company/load_discovery_seeds

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3 — Follow-ups v2 (engine): cadencia por estado, seed idempotente, buckets, cold, drafts deterministas

**Files:**
- `engine/outreach/followups.py` (EDIT — se EXTIENDE; `schedule()`/`followup_text()` del plan 006 se conservan intactos para el flujo de outreach por mensaje)
- `tests/test_f3_followups_v2.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/outreach/followups.py
CADENCE_STATES = ("applied", "responded", "interview")
URGENT_WINDOW_DAYS = 3

def cadence_for(state: str, criteria: Criteria) -> tuple[int, int] | None       # (days, max_touches)
def seed_for_state(db: DB, job_id: str, state: str, criteria: Criteria,
                   *, base_iso: str | None = None) -> int | None                 # id del followup o None
def register_sent(db: DB, followup_id: int, criteria: Criteria) -> dict         # {"ok": bool, "next_id": int|None}
def bucket_followups(followups: list[dict], now: datetime) -> dict[str, list[dict]]  # urgent/overdue/waiting
def cold_jobs(db: DB, criteria: Criteria) -> list[dict]                         # cadencia agotada sin respuesta
def draft_followup(job: dict, candidate_name: str, kind: str, touch_number: int,
                   language: str = "en", highlight: str = "") -> Draft
```

Semántica de buckets (determinista, función pura sobre `due_at` vs `now`): `waiting` = aún no vence; `URGENT` = vencido hace `< URGENT_WINDOW_DAYS` (3 días); `OVERDUE` = vencido hace ≥ 3 días; `COLD` = jobs en estado `applied` cuya cadencia `applied` está agotada (todos los toques `done`, ninguno `pending`, `touches_done >= max_touches`) y siguen sin respuesta.

Reglas de drafts (§6.1): prohibido "just checking in" (test lo verifica en cada plantilla), value-first (la primera frase aporta algo: contexto del rol + un activo concreto vía slot `highlight`), <150 palabras garantizado por construcción, EN/ES.

**Steps:**

- [ ] RED — crear `tests/test_f3_followups_v2.py`:

```python
"""F3 §6.1: cadencia por estado, seed idempotente, buckets URGENT/OVERDUE/waiting/COLD, drafts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.outreach import followups as fu


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


CRIT = Criteria(roles=["data scientist"])


def _seed_job(db: DB, state: str = "applied") -> str:
    db.upsert_job(Job(source="greenhouse", title="Data Scientist", company="Acme", location="Remote"))
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, state, {"via": "test"})
    return jid


def test_cadence_for_reads_criteria_defaults():
    assert fu.cadence_for("applied", CRIT) == (7, 2)
    assert fu.cadence_for("responded", CRIT) == (1, 1)
    assert fu.cadence_for("interview", CRIT) == (1, 1)
    assert fu.cadence_for("shortlisted", CRIT) is None


def test_seed_for_state_creates_first_touch_at_plus_days(db: DB):
    jid = _seed_job(db)
    base = "2026-07-04T12:00:00+00:00"
    fid = fu.seed_for_state(db, jid, "applied", CRIT, base_iso=base)
    assert fid is not None
    rows = db.followups_for_job(jid)
    assert len(rows) == 1
    assert rows[0]["kind"] == "applied" and rows[0]["touch_number"] == 1
    assert rows[0]["due_at"].startswith("2026-07-11")  # +7d


def test_seed_for_state_is_idempotent_while_pending(db: DB):
    jid = _seed_job(db)
    assert fu.seed_for_state(db, jid, "applied", CRIT) is not None
    assert fu.seed_for_state(db, jid, "applied", CRIT) is None  # re-run: no duplica
    assert len(db.followups_for_job(jid)) == 1


def test_register_sent_seeds_next_touch_until_cap(db: DB):
    jid = _seed_job(db)
    f1 = fu.seed_for_state(db, jid, "applied", CRIT)
    r1 = fu.register_sent(db, f1, CRIT)
    assert r1["ok"] is True and r1["next_id"] is not None  # touch 2 sembrado (max 2)
    r2 = fu.register_sent(db, r1["next_id"], CRIT)
    assert r2["ok"] is True and r2["next_id"] is None      # cap alcanzado → COLD después
    rows = db.followups_for_job(jid)
    assert sorted(f["touch_number"] for f in rows) == [1, 2]
    assert all(f["state"] == "done" for f in rows)


def test_register_sent_unknown_id(db: DB):
    assert fu.register_sent(db, 99999, CRIT) == {"ok": False, "next_id": None}


def test_bucket_followups_pure_classification():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    mk = lambda days: {"id": 1, "state": "pending", "due_at": (now + timedelta(days=days)).isoformat()}
    b = fu.bucket_followups([mk(2), mk(-1), mk(-5), {**mk(-1), "state": "done"}], now)
    assert [len(b["waiting"]), len(b["urgent"]), len(b["overdue"])] == [1, 1, 1]  # done se ignora
    assert b["urgent"][0]["days_overdue"] == 1.0
    assert b["overdue"][0]["days_overdue"] == 5.0


def test_cold_jobs_detects_exhausted_cadence(db: DB):
    jid = _seed_job(db)
    f1 = fu.seed_for_state(db, jid, "applied", CRIT, base_iso="2026-06-01T00:00:00+00:00")
    assert fu.cold_jobs(db, CRIT) == []                      # aún hay pending
    nxt = fu.register_sent(db, f1, CRIT)["next_id"]
    fu.register_sent(db, nxt, CRIT)
    cold = fu.cold_jobs(db, CRIT)
    assert len(cold) == 1 and cold[0]["job_id"] == jid and cold[0]["touches_done"] == 2


def test_drafts_obey_rules_all_kinds_and_languages():
    job = {"company": "Acme", "title": "Data Scientist"}
    for kind in ("applied", "responded", "interview"):
        for lang in ("en", "es"):
            d = fu.draft_followup(job, "Jane Doe", kind, 1, language=lang, highlight="churn models")
            assert "just checking in" not in d.body.lower()
            assert len(d.body.split()) < 150
            assert "Acme" in d.body and d.subject
            assert d.language == lang


def test_draft_second_touch_differs_from_first():
    job = {"company": "Acme", "title": "Data Scientist"}
    d1 = fu.draft_followup(job, "Jane", "applied", 1)
    d2 = fu.draft_followup(job, "Jane", "applied", 2)
    assert d1.body != d2.body and d2.variant == "applied-touch2"
```

- [ ] Correr y ver el fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_followups_v2.py -x
```
Esperado: `AttributeError: module 'engine.outreach.followups' has no attribute 'cadence_for'`.

- [ ] GREEN — `engine/outreach/followups.py`: añadir al final del archivo (imports: añadir `from engine.config import Criteria` arriba junto a los existentes):

```python
# ── Cadencia v2 por estado (F3 §6.1) ─────────────────────────────────────────
# Los toques v2 llevan `kind` = estado que los sembró y se confirman a mano en /followups
# (el brain NUNCA los auto-draftea — ver brain/run_brain.py). Los toques legacy del plan
# 006 (kind NULL, creados por schedule()) siguen intactos para el flujo por mensaje.
CADENCE_STATES = ("applied", "responded", "interview")
URGENT_WINDOW_DAYS = 3  # vencido < 3d → URGENT; ≥ 3d → OVERDUE


def cadence_for(state: str, criteria: Criteria) -> tuple[int, int] | None:
    """(days, max_touches) para un estado, o None si el estado no lleva cadencia."""
    cfg = (criteria.followup_cadence or {}).get(state)
    if not cfg:
        return None
    days, max_touches = int(cfg.get("days", 0)), int(cfg.get("max_touches", 0))
    if days <= 0 or max_touches <= 0:
        return None
    return days, max_touches


def seed_for_state(
    db: DB, job_id: str, state: str, criteria: Criteria, *, base_iso: str | None = None
) -> int | None:
    """Siembra el SIGUIENTE toque de la cadencia de `state`. Idempotente: nunca duplica un
    pending ni supera max_touches (cuenta done/cancelled también, como schedule())."""
    cad = cadence_for(state, criteria)
    if cad is None:
        return None
    days, max_touches = cad
    existing = [f for f in db.followups_for_job(job_id) if f.get("kind") == state]
    if any(f["state"] == "pending" for f in existing) or len(existing) >= max_touches:
        return None
    touch = (max((f["touch_number"] or 0) for f in existing) + 1) if existing else 1
    base = _parse(base_iso) if base_iso else datetime.now(UTC)
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    due = (base + timedelta(days=days)).isoformat()
    return db.add_followup(job_id, channel="email", touch_number=touch, due_at=due, kind=state)


def register_sent(db: DB, followup_id: int, criteria: Criteria) -> dict:
    """Confirmación humana de envío: marca done y siembra el siguiente toque si queda cupo."""
    row = db.conn.execute("SELECT * FROM followups WHERE id=?", (followup_id,)).fetchone()
    if row is None:
        return {"ok": False, "next_id": None}
    f = dict(row)
    db.mark_followup(followup_id, "done")
    next_id = seed_for_state(db, f["job_id"], f["kind"], criteria) if f.get("kind") else None
    return {"ok": True, "next_id": next_id}


def bucket_followups(followups: list[dict], now: datetime) -> dict[str, list[dict]]:
    """Clasificación PURA de follow-ups pending en urgencia. No toca la DB."""
    buckets: dict[str, list[dict]] = {"urgent": [], "overdue": [], "waiting": []}
    for f in followups:
        if f.get("state") != "pending":
            continue
        due = _parse(f.get("due_at") or "")
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        overdue_days = (now - due).total_seconds() / 86400
        item = {**f, "days_overdue": round(max(overdue_days, 0.0), 1)}
        if overdue_days < 0:
            buckets["waiting"].append(item)
        elif overdue_days < URGENT_WINDOW_DAYS:
            buckets["urgent"].append(item)
        else:
            buckets["overdue"].append(item)
    for rows in buckets.values():
        rows.sort(key=lambda r: r.get("due_at") or "")
    return buckets


def cold_jobs(db: DB, criteria: Criteria) -> list[dict]:
    """Jobs 'applied' con la cadencia agotada (todos los toques done, sin pending) → COLD."""
    cad = cadence_for("applied", criteria)
    if cad is None:
        return []
    _, max_touches = cad
    rows = db.conn.execute(
        """SELECT j.id AS job_id, j.title, j.company, j.applied_at,
                  SUM(CASE WHEN f.state='done' THEN 1 ELSE 0 END) AS touches_done,
                  SUM(CASE WHEN f.state='pending' THEN 1 ELSE 0 END) AS touches_pending
           FROM jobs j JOIN followups f ON f.job_id = j.id AND f.kind='applied'
           WHERE j.state='applied'
           GROUP BY j.id"""
    ).fetchall()
    return [
        dict(r) for r in rows if r["touches_pending"] == 0 and r["touches_done"] >= max_touches
    ]


# ── Drafts deterministas (§6.1): value-first, sin "just checking in", <150 palabras ──
def draft_followup(
    job: dict,
    candidate_name: str,
    kind: str,
    touch_number: int,
    language: str = "en",
    highlight: str = "",
) -> Draft:
    company, role, me = job.get("company", ""), job.get("title", ""), candidate_name
    hl_en = f" — for example, my work with {highlight} maps directly to what the role needs" if highlight else ""
    hl_es = f" — por ejemplo, mi experiencia con {highlight} encaja directo con lo que pide el rol" if highlight else ""
    if language == "es":
        bodies = {
            "applied": {
                1: (
                    f"Hola — apliqué al rol de {role} en {company} y quería sumar contexto útil: "
                    f"llego con resultados concretos en problemas como los que describe la vacante"
                    f"{hl_es}. Si les sirve, puedo compartir un ejemplo breve de un proyecto "
                    f"comparable. ¿Tiene sentido una conversación corta esta semana?\n\n{me}"
                ),
                2: (
                    f"Hola — segundo y último toque sobre el rol de {role} en {company}. Desde mi "
                    f"aplicación estuve pensando en su contexto{hl_es}; si el proceso sigue "
                    f"abierto, encantado de mostrar cómo abordaría los primeros 90 días. Si ya "
                    f"avanzaron con otra persona, también agradezco saberlo.\n\n{me}"
                ),
            },
            "responded": {
                1: (
                    f"Hola — gracias por responder sobre el rol de {role} en {company}. Para "
                    f"facilitar el siguiente paso: tengo disponibilidad esta semana y puedo "
                    f"adelantar material relevante{hl_es}. ¿Qué horario les acomoda?\n\n{me}"
                )
            },
            "interview": {
                1: (
                    f"Hola — gracias por la conversación de hoy sobre el rol de {role} en "
                    f"{company}. Me quedé pensando en los retos que mencionaron{hl_es}; quedo "
                    f"atento a los siguientes pasos y disponible para cualquier profundización."
                    f"\n\n{me}"
                )
            },
        }
        subject = f"Re: {role} en {company}"
    else:
        bodies = {
            "applied": {
                1: (
                    f"Hi — I applied for the {role} role at {company} and wanted to add useful "
                    f"context: I bring concrete results on the kind of problems the posting "
                    f"describes{hl_en}. Happy to share a short example of comparable work if "
                    f"helpful. Would a brief chat this week make sense?\n\n{me}"
                ),
                2: (
                    f"Hi — second and final note on the {role} role at {company}. Since applying "
                    f"I've been thinking about your context{hl_en}; if the process is still open, "
                    f"I'd love to show how I'd approach the first 90 days. If you've moved forward "
                    f"with someone else, I'd appreciate knowing that too.\n\n{me}"
                ),
            },
            "responded": {
                1: (
                    f"Hi — thanks for getting back about the {role} role at {company}. To make the "
                    f"next step easy: I'm available this week and can send relevant material ahead "
                    f"of time{hl_en}. What time works for you?\n\n{me}"
                )
            },
            "interview": {
                1: (
                    f"Hi — thank you for today's conversation about the {role} role at {company}. "
                    f"I kept thinking about the challenges you mentioned{hl_en}; looking forward "
                    f"to next steps, and happy to go deeper on anything.\n\n{me}"
                )
            },
        }
        subject = f"Re: {role} at {company}"
    per_kind = bodies.get(kind) or bodies["applied"]
    body = per_kind.get(touch_number) or per_kind[max(per_kind)]
    return Draft(
        "follow_up",
        "email",
        body,
        subject=subject,
        variant=f"{kind}-touch{touch_number}",
        language=language,
    )
```

- [ ] Verificar (v2 + legacy plan 006 intactos):

```bash
rtk uv run --group dev pytest tests/test_f3_followups_v2.py tests/test_engine.py -x
```
Esperado: `9 passed` nuevos, y los tests legacy de cadencia (plan 006) siguen verdes — `schedule()`/`followup_text()` no se tocaron.

- [ ] Commit:

```bash
rtk git add engine/outreach/followups.py tests/test_f3_followups_v2.py
rtk git commit -m "feat(f3): follow-ups v2 — cadencia por estado, seed idempotente, buckets y drafts value-first

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4 — Follow-ups v2 (API + wiring): auto-seed en Applied, GET /api/followups, POST /api/followups/{id}/sent, brain no auto-draftea v2

**Files:**
- `dashboard/backend/main.py` (EDIT)
- `brain/run_brain.py` (EDIT)
- `tests/test_f3_backend_api.py` (NEW — sección followups)
- `tests/test_backend_api.py` (EDIT — 1 test)

**Interfaces:**
```
GET  /api/followups                → {"buckets": {"urgent": [Item], "overdue": [Item], "waiting": [Item], "cold": [ColdJob]}}
     Item    = {id, job_id, title, company, kind, touch_number, due_at, days_overdue, draft: {subject, body}}
     ColdJob = {job_id, title, company, applied_at, touches_done, touches_pending}
POST /api/followups/{id}/sent      body {"confirm": true}   → {"ok": true, "next_id": int|null}
     (origin-guarded; 400 sin confirm=true; 404 id desconocido)
POST /api/jobs/{id}/applied        (EDIT) → siembra cadencia v2 (1 toque kind='applied' a +7d)
POST /api/jobs/{id}/state          (EDIT) → applied/responded/interview siembran su cadencia;
                                            responded además cancela pendientes (register_reply, como hoy)
```

Decisión (documentada): las transiciones del dashboard dejan de crear los 4 toques legacy (Day 3/7/14/21) y siembran la cadencia v2. `schedule()` queda para el flujo de outreach por mensaje (cuando un mensaje se marca sent). El brain deja de auto-draftar los toques v2: exigen confirmación humana en `/followups`.

**Steps:**

- [ ] RED — crear `tests/test_f3_backend_api.py` con la sección followups:

```python
"""F3: endpoints nuevos del dashboard (followups, analytics, stories, ops)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job(state: str | None = None) -> str:
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        db.upsert_job(
            Job(source="greenhouse", source_job_id="1", title="Data Scientist",
                company="Acme", url="https://x/1")
        )
        jid = db.list_jobs()[0]["id"]
        if state:
            db.set_state(jid, state, {"via": "test"})
    return jid


# ── §6.1 Follow-ups v2 ────────────────────────────────────────────────────────
def test_mark_applied_seeds_v2_cadence(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200  # idempotente
    with DB() as db:
        rows = db.followups_for_job(jid)
    assert len(rows) == 1 and rows[0]["kind"] == "applied" and rows[0]["touch_number"] == 1


def test_state_interview_seeds_thankyou(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        assert client.post(f"/api/jobs/{jid}/state", json={"state": "interview"}).status_code == 200
    with DB() as db:
        kinds = {f["kind"] for f in db.followups_for_job(jid)}
    assert "interview" in kinds


def test_get_followups_buckets_with_drafts(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        with DB() as db:
            db.add_followup(jid, channel="email", touch_number=1,
                            due_at="2020-01-01T00:00:00+00:00", kind="applied")  # muy vencido
        data = client.get("/api/followups").json()["buckets"]
    assert set(data) == {"urgent", "overdue", "waiting", "cold"}
    assert data["overdue"], "un toque vencido hace años debe caer en OVERDUE"
    item = data["overdue"][0]
    assert item["company"] == "Acme" and item["draft"]["body"]
    assert "just checking in" not in item["draft"]["body"].lower()


def test_followup_sent_requires_confirm_and_seeds_next(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        with DB() as db:
            fid = db.add_followup(jid, channel="email", touch_number=1,
                                  due_at="2026-07-11T00:00:00+00:00", kind="applied")
        assert client.post(f"/api/followups/{fid}/sent", json={"confirm": False}).status_code == 400
        r = client.post(f"/api/followups/{fid}/sent", json={"confirm": True})
        assert r.status_code == 200 and r.json()["ok"] is True and r.json()["next_id"]
        assert client.post("/api/followups/99999/sent", json={"confirm": True}).status_code == 404


def test_followup_sent_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/followups/1/sent", json={"confirm": True},
                        headers={"origin": "https://evil.example.com"})
    assert r.status_code == 403
```

- [ ] EDIT `tests/test_backend_api.py` — el test del comportamiento viejo (línea 57, `test_mark_applied_on_real_job_schedules_cadence`) pasa a caracterizar v2. Reemplazarlo por:

```python
def test_mark_applied_on_real_job_schedules_cadence(atlas_app):
    """F3 v2: /applied siembra el PRIMER follow-up de la cadencia applied (7d, kind='applied')."""
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/applied")
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    with DB() as db:
        rows = db.followups_for_job(jid)
        assert db.get_job(jid)["state"] == "applied"
    assert len(rows) == 1 and rows[0]["kind"] == "applied"
```

- [ ] Correr y ver el fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_backend_api.py tests/test_backend_api.py -x
```
Esperado: falla `test_mark_applied_seeds_v2_cadence` (hoy crea 4 toques legacy).

- [ ] GREEN — `dashboard/backend/main.py`: reemplazar los cuerpos de `api_set_state` (línea ~263) y `api_mark_applied` (línea ~280):

```python
@app.post("/api/jobs/{job_id}/state", dependencies=[Depends(require_trusted_origin)])
def api_set_state(job_id: str, body: StateBody, db: DB = Depends(get_db)):
    from engine.config import load_criteria
    from engine.outreach import followups

    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    if not db.get_job(job_id):
        raise HTTPException(404, "job not found")
    db.set_state(job_id, body.state, {"via": "dashboard"})
    # Cadencia v2 (F3 §6.1): applied/responded/interview siembran su follow-up; responded
    # además cancela los pendientes (nunca insistir tras una respuesta — regla plan 006).
    if body.state == "responded":
        followups.register_reply(db, job_id)
    if body.state in followups.CADENCE_STATES:
        followups.seed_for_state(db, job_id, body.state, load_criteria())
    return {"ok": True, "state": body.state}


@app.post("/api/jobs/{job_id}/applied", dependencies=[Depends(require_trusted_origin)])
def api_mark_applied(job_id: str, db: DB = Depends(get_db)):
    from engine.config import load_criteria
    from engine.outreach import followups

    db.set_state(job_id, "applied", {"via": "dashboard"})
    followups.seed_for_state(db, job_id, "applied", load_criteria())  # +7d, máx 2 → cold
    return {"ok": True}
```

- [ ] GREEN — `dashboard/backend/main.py`: añadir los endpoints (tras `api_mark_sent`, línea ~313):

```python
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
```

- [ ] GREEN — `brain/run_brain.py`: en el drain de follow-ups (línea ~72, `for f in db.due_followups(now_iso()):`), añadir como primera línea del loop:

```python
        if f.get("kind"):
            continue  # v2 (F3): los toques por estado se confirman a mano en /followups — nunca auto-draftar
```

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_backend_api.py tests/test_backend_api.py tests/test_engine.py -x
```
Esperado: todo verde (5 tests nuevos de followups + el editado).

- [ ] Commit:

```bash
rtk git add dashboard/backend/main.py brain/run_brain.py tests/test_f3_backend_api.py tests/test_backend_api.py
rtk git commit -m "feat(f3): API follow-ups v2 — auto-seed en applied, GET /api/followups, sent con confirmación

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5 — Analytics engine: funnel, score_floor, conversion_by, response_times (funciones puras sobre SQLite)

**Files:**
- `engine/analytics.py` (EDIT — el spec dice "módulo nuevo", pero `engine/analytics.py` YA existe con `overview/needs_action/job_detail`; las funciones nuevas viven ahí mismo, que es su sitio natural — crear un segundo módulo duplicaría el dominio)
- `tests/test_f3_analytics.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/analytics.py
POSITIVE_OUTCOME_STATES = ("responded", "interviewed", "offer")
_ATS_SOURCES = frozenset({"greenhouse", "lever", "ashby", "smartrecruiters", "workday"})

def funnel(db: DB) -> list[dict]                    # [{"stage","count","rate"}] rate = conversión vs etapa previa
def score_floor(db: DB) -> float | None             # min fit_score con outcome positivo; None sin datos
def conversion_by(db: DB, dim: str, criteria: Criteria | None = None) -> list[dict]
    # dim ∈ {"source","ats","remote_policy","role_term"};
    # [{"key","applied","responded","interviews","offers","response_rate"}] orden: applied desc
def response_times(db: DB) -> dict                  # {"n","avg_days","median_days","p90_days"}
```

Verificación de datos reales (hecha): la tabla `events` solo registra `discovered | stage_change | source_run | error | note | prepare` con el destino en `detail` JSON — NO es la fuente más fiable para el funnel. La fuente canónica de transiciones son las columnas timestamp por etapa de `jobs` (`discovered_at … offer_at`, constante `FUNNEL` ya existente en analytics.py:13) — el funnel se calcula de ahí, y los positivos se complementan con `application_outcomes.final_state` (que usa `interviewed`, no `interview`) y `response_days`.

**Steps:**

- [ ] RED — crear `tests/test_f3_analytics.py`:

```python
"""F3 §6.2: funnel con tasas, score floor empírico, conversión por dimensión, tiempos de respuesta."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine import analytics
from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _mk(db: DB, n: int, *, source="greenhouse", title="Data Scientist", wt="remote") -> str:
    db.upsert_job(Job(source=source, source_job_id=str(n), title=title,
                      company=f"Acme{n}", location="Remote", workplace_type=wt,
                      url=f"https://x/{n}"))
    return [j for j in db.list_jobs() if j["company"] == f"Acme{n}"][0]["id"]


def test_funnel_counts_and_rates(db: DB):
    a, b = _mk(db, 1), _mk(db, 2)
    for jid in (a, b):
        db.set_state(jid, "scored")
        db.set_state(jid, "shortlisted")
        db.set_state(jid, "applied")
    db.set_state(a, "responded")
    stages = {s["stage"]: s for s in analytics.funnel(db)}
    assert stages["discovered"]["count"] == 2 and stages["discovered"]["rate"] is None
    assert stages["applied"]["count"] == 2
    assert stages["responded"]["count"] == 1 and stages["responded"]["rate"] == 0.5


def test_score_floor_empirical(db: DB):
    a, b, c = _mk(db, 1), _mk(db, 2), _mk(db, 3)
    db.set_fit(a, 71.0, [], []); db.set_fit(b, 64.0, [], []); db.set_fit(c, 40.0, [], [])
    db.set_state(a, "applied"); db.set_state(a, "responded")
    db.record_outcome(b, "Acme2", final_state="interviewed")
    # c (score 40) no tiene outcome positivo → el floor es 64, no 40
    assert analytics.score_floor(db) == 64.0


def test_score_floor_none_without_positives(db: DB):
    _mk(db, 1)
    assert analytics.score_floor(db) is None


def test_conversion_by_source_and_role_term(db: DB):
    crit = Criteria(roles=["data scientist", "ml engineer"])
    a = _mk(db, 1, source="greenhouse", title="Data Scientist")
    b = _mk(db, 2, source="lever", title="ML Engineer")
    for jid in (a, b):
        db.set_state(jid, "applied")
    db.set_state(a, "responded")
    by_src = {r["key"]: r for r in analytics.conversion_by(db, "source")}
    assert by_src["greenhouse"]["applied"] == 1 and by_src["greenhouse"]["response_rate"] == 1.0
    assert by_src["lever"]["response_rate"] == 0.0
    by_term = {r["key"]: r for r in analytics.conversion_by(db, "role_term", crit)}
    assert by_term["data scientist"]["responded"] == 1
    assert by_term["ml engineer"]["responded"] == 0


def test_conversion_by_unknown_dim_raises(db: DB):
    with pytest.raises(ValueError):
        analytics.conversion_by(db, "astrology")


def test_response_times_from_timestamps_and_outcomes(db: DB):
    a = _mk(db, 1)
    db.set_state(a, "applied")
    db.conn.execute("UPDATE jobs SET applied_at='2026-06-01T00:00:00+00:00', "
                    "responded_at='2026-06-08T00:00:00+00:00' WHERE id=?", (a,))
    db.conn.commit()
    db.record_outcome(None, "Beta Corp", final_state="responded", response_days=3)
    rt = analytics.response_times(db)
    assert rt["n"] == 2 and rt["avg_days"] == 5.0 and rt["median_days"] == 5.0
```

- [ ] Correr y ver el fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_analytics.py -x
```
Esperado: `AttributeError: module 'engine.analytics' has no attribute 'funnel'`.

- [ ] GREEN — `engine/analytics.py`: añadir imports arriba (`from engine.config import Criteria` junto a los existentes; `statistics` stdlib) y este bloque tras `overview()`:

```python
# ── F3 §6.2: analytics puro sobre SQLite (funnel real, score floor, conversiones) ──
POSITIVE_OUTCOME_STATES = ("responded", "interviewed", "offer")
_ATS_SOURCES = frozenset({"greenhouse", "lever", "ashby", "smartrecruiters", "workday"})
_POSITIVE_JOBS_WHERE = (
    "(responded_at IS NOT NULL OR interview_at IS NOT NULL OR offer_at IS NOT NULL "
    "OR id IN (SELECT job_id FROM application_outcomes WHERE final_state IN "
    "('responded','interviewed','offer')))"
)


def funnel(db: DB) -> list[dict]:
    """Funnel por transiciones reales (columnas timestamp por etapa de jobs) + tasa vs etapa previa."""
    cols = [col for _, col in FUNNEL]
    select = ", ".join(f"COUNT({c}) AS {c}" for c in cols)
    row = db.conn.execute(f"SELECT {select} FROM jobs").fetchone()
    out: list[dict] = []
    prev: int | None = None
    for name, col in FUNNEL:
        count = row[col]
        rate = round(count / prev, 3) if prev else None
        out.append({"stage": name, "count": count, "rate": rate})
        prev = count
    return out


def score_floor(db: DB) -> float | None:
    """Score mínimo con outcome positivo — 'ningún positivo bajo X' (§6.2)."""
    row = db.conn.execute(
        f"SELECT MIN(fit_score) AS floor, COUNT(*) AS n FROM jobs "
        f"WHERE fit_score IS NOT NULL AND {_POSITIVE_JOBS_WHERE}"
    ).fetchone()
    return float(row["floor"]) if row and row["n"] else None


def conversion_by(db: DB, dim: str, criteria: Criteria | None = None) -> list[dict]:
    """Conversión de jobs APLICADOS agrupados por dimensión (§6.2)."""
    if dim not in ("source", "ats", "remote_policy", "role_term"):
        raise ValueError(f"unknown dim: {dim}")
    jobs = [j for j in db.list_jobs() if j.get("applied_at")]

    def key_of(j: dict) -> str:
        if dim == "source":
            return j.get("source") or "unknown"
        if dim == "ats":
            s = j.get("source") or "unknown"
            return s if s in _ATS_SOURCES else "non-ats"
        if dim == "remote_policy":
            return (j.get("workplace_type") or "unknown").lower()
        title = (j.get("title") or "").lower()
        for t in criteria.all_role_terms if criteria else []:
            if t in title:
                return t
        return "otro"

    groups: dict[str, dict] = {}
    for j in jobs:
        g = groups.setdefault(
            key_of(j), {"key": key_of(j), "applied": 0, "responded": 0, "interviews": 0, "offers": 0}
        )
        positive = bool(j.get("responded_at") or j.get("interview_at") or j.get("offer_at"))
        g["applied"] += 1
        g["responded"] += 1 if positive else 0
        g["interviews"] += 1 if (j.get("interview_at") or j.get("offer_at")) else 0
        g["offers"] += 1 if j.get("offer_at") else 0
    for g in groups.values():
        g["response_rate"] = round(g["responded"] / g["applied"], 3) if g["applied"] else None
    return sorted(groups.values(), key=lambda g: -g["applied"])


def response_times(db: DB) -> dict:
    """Días applied→responded (timestamps de jobs) + response_days confirmados (outcomes)."""
    import statistics

    days: list[float] = []
    for j in db.list_jobs():
        a, r = j.get("applied_at"), j.get("responded_at")
        if not (a and r):
            continue
        try:
            delta = (datetime.fromisoformat(r) - datetime.fromisoformat(a)).total_seconds() / 86400
        except (ValueError, TypeError):
            continue
        if delta >= 0:
            days.append(round(delta, 1))
    rows = db.conn.execute(
        "SELECT response_days FROM application_outcomes WHERE response_days IS NOT NULL"
    ).fetchall()
    days.extend(float(r["response_days"]) for r in rows)
    if not days:
        return {"n": 0, "avg_days": None, "median_days": None, "p90_days": None}
    days.sort()
    return {
        "n": len(days),
        "avg_days": round(statistics.fmean(days), 1),
        "median_days": round(statistics.median(days), 1),
        "p90_days": round(days[int(0.9 * (len(days) - 1))], 1),
    }
```

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_analytics.py tests/test_backend_api.py -x
```
Esperado: `6 passed` nuevos + API intacta.

- [ ] Commit:

```bash
rtk git add engine/analytics.py tests/test_f3_analytics.py
rtk git commit -m "feat(f3): analytics puro — funnel con tasas, score floor empírico, conversion_by, response_times

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6 — Recomendaciones deterministas + GET /api/analytics + POST /api/analytics/apply-rec

**Files:**
- `engine/analytics.py` (EDIT)
- `dashboard/backend/main.py` (EDIT)
- `tests/test_f3_analytics.py` (EDIT — añade tests)
- `tests/test_f3_backend_api.py` (EDIT — añade tests)

**Interfaces (firmas exactas):**
```python
# engine/analytics.py
def recommendations(db: DB, criteria: Criteria) -> list[dict]
    # Rec = {"id": str, "text": str, "action_type": "set_criteria"|"block_company"|"none", "payload": dict}
def analytics_payload(db: DB, criteria: Criteria) -> dict
    # {"funnel", "score_floor", "by_source", "by_ats", "by_remote_policy", "by_role_term",
    #  "response_times", "recommendations"}
```
```
GET  /api/analytics                 → analytics_payload(db, load_criteria())
POST /api/analytics/apply-rec       body Rec (id/action_type/payload) → {"ok": true, "applied": str}
     set_criteria  → update_criteria_fields({field: value}) con field ∈ {"shortlist_threshold"}
     block_company → append a criteria.company_blocklist (via update_criteria_fields)
     otro          → 400
```

Reglas deterministas (umbrales fijos, sin magia):
1. **Subir threshold**: si hay ≥3 positivos y `score_floor > shortlist_threshold + 2` → propone `shortlist_threshold = floor(score_floor)`.
2. **Bloquear empresa**: empresa con ≥3 aplicaciones y 0 positivos (y no ya bloqueada) → propone añadirla a `company_blocklist`.
3. **Término muerto** (informativa, `action_type: "none"`): role-term con ≥5 aplicaciones y 0 respuestas.

**Steps:**

- [ ] RED — añadir a `tests/test_f3_analytics.py`:

```python
def test_recommendations_threshold_and_block(db: DB):
    crit = Criteria(roles=["data scientist"], shortlist_threshold=60.0)
    # 3 positivos con floor 66 → recomienda subir threshold a 66
    for n, score in ((1, 66.0), (2, 70.0), (3, 80.0)):
        jid = _mk(db, n)
        db.set_fit(jid, score, [], [])
        db.set_state(jid, "applied"); db.set_state(jid, "responded")
    # Ghost Corp: 3 aplicaciones sin respuesta → recomienda bloquear
    for n in (4, 5, 6):
        db.upsert_job(Job(source="lever", source_job_id=str(n), title=f"DS {n}",
                          company="Ghost Corp", location="Remote", url=f"https://g/{n}"))
    for j in db.list_jobs():
        if j["company"] == "Ghost Corp":
            db.set_state(j["id"], "applied")
    recs = analytics.recommendations(db, crit)
    by_type = {r["action_type"]: r for r in recs}
    assert by_type["set_criteria"]["payload"] == {"field": "shortlist_threshold", "value": 66.0}
    assert by_type["block_company"]["payload"] == {"company": "Ghost Corp"}
    assert all({"id", "text", "action_type", "payload"} <= set(r) for r in recs)


def test_recommendations_skip_already_blocked(db: DB):
    crit = Criteria(roles=["data scientist"], company_blocklist=["Ghost Corp"])
    for n in (1, 2, 3):
        db.upsert_job(Job(source="lever", source_job_id=str(n), title=f"DS {n}",
                          company="Ghost Corp", location="Remote", url=f"https://g/{n}"))
    for j in db.list_jobs():
        db.set_state(j["id"], "applied")
    assert not [r for r in analytics.recommendations(db, crit) if r["action_type"] == "block_company"]


def test_analytics_payload_shape(db: DB):
    p = analytics.analytics_payload(db, Criteria())
    assert {"funnel", "score_floor", "by_source", "by_ats", "by_remote_policy",
            "by_role_term", "response_times", "recommendations"} <= set(p)
```

- [ ] RED — añadir a `tests/test_f3_backend_api.py`:

```python
# ── §6.2 Analytics + apply-rec ────────────────────────────────────────────────
def test_get_analytics_shape(atlas_app):
    with TestClient(atlas_app) as client:
        _seed_job("applied")
        p = client.get("/api/analytics").json()
    assert {"funnel", "score_floor", "recommendations", "response_times"} <= set(p)
    assert p["funnel"][0]["stage"] == "discovered"


def test_apply_rec_set_criteria_writes_frontmatter(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "criteria.md")
    with TestClient(atlas_app) as client:
        r = client.post("/api/analytics/apply-rec", json={
            "id": "threshold-66", "action_type": "set_criteria",
            "payload": {"field": "shortlist_threshold", "value": 66.0}})
        assert r.status_code == 200 and r.json()["ok"] is True
    assert "shortlist_threshold: 66" in (tmp_path / "criteria.md").read_text()


def test_apply_rec_block_company(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "criteria.md")
    with TestClient(atlas_app) as client:
        r = client.post("/api/analytics/apply-rec", json={
            "id": "block-ghost", "action_type": "block_company",
            "payload": {"company": "Ghost Corp"}})
        assert r.status_code == 200
    assert "Ghost Corp" in (tmp_path / "criteria.md").read_text()


def test_apply_rec_rejects_unknown_action_and_field(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/analytics/apply-rec", json={
            "id": "x", "action_type": "rm-rf", "payload": {}}).status_code == 400
        assert client.post("/api/analytics/apply-rec", json={
            "id": "x", "action_type": "set_criteria",
            "payload": {"field": "roles", "value": ["hacker"]}}).status_code == 400
```

- [ ] Correr y ver fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_analytics.py tests/test_f3_backend_api.py -x
```
Esperado: `AttributeError ... 'recommendations'`, luego 404 de `/api/analytics`.

- [ ] GREEN — `engine/analytics.py`: añadir tras `response_times()` (import `norm_company` ya que `engine.normalize` está importado — ampliar la línea de import a `from engine.normalize import STAGE_TIMESTAMP_COLS, norm_company` si no está; revisar imports actuales del módulo):

```python
def recommendations(db: DB, criteria: Criteria) -> list[dict]:
    """Recomendaciones deterministas accionables (§6.2). Umbrales fijos y explicables."""
    recs: list[dict] = []
    # 1. Score floor empírico → subir shortlist_threshold.
    floor = score_floor(db)
    positives = db.conn.execute(
        f"SELECT COUNT(*) AS n FROM jobs WHERE fit_score IS NOT NULL AND {_POSITIVE_JOBS_WHERE}"
    ).fetchone()["n"]
    if floor is not None and positives >= 3 and floor > criteria.shortlist_threshold + 2:
        value = float(int(floor))
        recs.append(
            {
                "id": f"threshold-{int(value)}",
                "text": (
                    f"Ningún resultado positivo bajo score {floor:.0f} ({positives} positivos): "
                    f"sube shortlist_threshold de {criteria.shortlist_threshold:.0f} a {value:.0f}."
                ),
                "action_type": "set_criteria",
                "payload": {"field": "shortlist_threshold", "value": value},
            }
        )
    # 2. Empresas que nunca responden → blocklist.
    blocked = {norm_company(c) for c in criteria.company_blocklist}
    rows = db.conn.execute(
        """SELECT company, COUNT(*) AS n FROM jobs
           WHERE applied_at IS NOT NULL AND responded_at IS NULL
             AND interview_at IS NULL AND offer_at IS NULL
           GROUP BY company HAVING n >= 3"""
    ).fetchall()
    for r in rows:
        if norm_company(r["company"]) in blocked:
            continue
        recs.append(
            {
                "id": f"block-{norm_company(r['company'])}",
                "text": f"{r['n']} aplicaciones a {r['company']} sin ninguna respuesta: bloquéala.",
                "action_type": "block_company",
                "payload": {"company": r["company"]},
            }
        )
    # 3. Role-terms que no convierten (informativa — quitar un término es decisión del usuario).
    for row in conversion_by(db, "role_term", criteria):
        if row["key"] != "otro" and row["applied"] >= 5 and row["responded"] == 0:
            recs.append(
                {
                    "id": f"term-{row['key'].replace(' ', '-')}",
                    "text": (
                        f"El término '{row['key']}' lleva {row['applied']} aplicaciones sin "
                        f"respuesta — considera quitarlo de roles en Ajustes."
                    ),
                    "action_type": "none",
                    "payload": {"term": row["key"]},
                }
            )
    return recs


def analytics_payload(db: DB, criteria: Criteria) -> dict:
    """Composición completa para GET /api/analytics (§6.2)."""
    return {
        "funnel": funnel(db),
        "score_floor": score_floor(db),
        "by_source": conversion_by(db, "source"),
        "by_ats": conversion_by(db, "ats"),
        "by_remote_policy": conversion_by(db, "remote_policy"),
        "by_role_term": conversion_by(db, "role_term", criteria),
        "response_times": response_times(db),
        "recommendations": recommendations(db, criteria),
    }
```

- [ ] GREEN — `dashboard/backend/main.py`: añadir tras el bloque de followups:

```python
# ── Analytics + loop de aprendizaje (F3 §6.2) ─────────────────────────────────
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
        field, value = body.payload.get("field"), body.payload.get("value")
        if field not in APPLY_REC_CRITERIA_FIELDS:
            raise HTTPException(400, f"campo no aplicable por rec: {field}")
        update_criteria_fields({field: value})
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
```

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_analytics.py tests/test_f3_backend_api.py -x
```
Esperado: todo verde (9 + 9 tests).

- [ ] Commit:

```bash
rtk git add engine/analytics.py dashboard/backend/main.py tests/test_f3_analytics.py tests/test_f3_backend_api.py
rtk git commit -m "feat(f3): recomendaciones deterministas + GET /api/analytics + apply-rec

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7 — Story bank engine: `engine/stories.py` (matcher por overlap con ontología + formateo)

**Files:**
- `engine/stories.py` (NEW)
- `tests/test_f3_stories.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/stories.py
SKILL_WEIGHT = 3.0

def match_stories(stories: list[dict], query_text: str,
                  ontology: dict[str, list[str]]) -> list[tuple[dict, float]]
def format_story(story: dict, max_words: int = 400) -> str
```

Port determinista del `match-star.mjs` de career-ops: tokeniza query e historias, canonicaliza vía la ontología existente (`load_ontology()`: canonical → aliases), y puntúa `SKILL_WEIGHT × |skills ∩ query| + |tokens ∩ query|`. `format_story` produce el bloque STAR+R listo para pegar (título + Situación/Tarea/Acción/Resultado/Reflexión), truncado a `max_words` (§6.3 pide 250–500; default 400).

**Steps:**

- [ ] RED — crear `tests/test_f3_stories.py`:

```python
"""F3 §6.3: matcher determinista de historias STAR+R + formateo para pegar."""

from __future__ import annotations

from engine.stories import format_story, match_stories

ONTOLOGY = {"python": ["py"], "airflow": ["apache airflow"], "sql": []}

S1 = {"id": 1, "title": "Pipeline caído en Black Friday", "situation": "ETL crítico caído en pico",
      "task": "Restaurar en menos de 1h", "action": "Rollback y circuit breaker en Airflow",
      "result": "Recuperado en 40 minutos", "reflection": "Añadí alertas proactivas",
      "skills": ["python", "airflow"]}
S2 = {"id": 2, "title": "Negociación con stakeholder", "situation": "Roadmap en conflicto",
      "task": "Alinear prioridades", "action": "Workshop de trade-offs", "result": "Acuerdo en 2 semanas",
      "reflection": "Escuchar primero", "skills": ["communication"]}


def test_match_ranks_by_skill_and_token_overlap():
    ranked = match_stories([S1, S2], "Tell me about debugging a python airflow incident", ONTOLOGY)
    assert ranked and ranked[0][0]["id"] == 1
    assert ranked[0][1] > 0
    ids = [s["id"] for s, _ in ranked]
    assert ids.index(1) < ids.index(2) if 2 in ids else True


def test_match_canonicalizes_aliases():
    # "apache airflow" en la query debe matchear la skill canónica "airflow"
    ranked = match_stories([S1], "experience with apache airflow", ONTOLOGY)
    assert ranked and ranked[0][0]["id"] == 1


def test_match_empty_query_returns_empty():
    assert match_stories([S1, S2], "", ONTOLOGY) == []


def test_no_match_returns_empty():
    assert match_stories([S2], "kubernetes cluster autoscaling", ONTOLOGY) == []


def test_format_story_structure_and_truncation():
    text = format_story(S1)
    for label in ("Situación:", "Tarea:", "Acción:", "Resultado:", "Reflexión:"):
        assert label in text
    assert text.startswith("**Pipeline caído en Black Friday**")
    short = format_story(S1, max_words=10)
    assert len(short.split()) <= 11 and short.endswith("…")
```

- [ ] Correr y ver fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_stories.py -x
```
Esperado: `ModuleNotFoundError: No module named 'engine.stories'`.

- [ ] GREEN — crear `engine/stories.py`:

```python
"""Story bank STAR+R (F3 §6.3) — matcher determinista + formateo.

Port del scoring por overlap de career-ops `match-star.mjs`: sin LLM. Ante una pregunta
de entrevista o un JD, rankea las historias del banco por solape de skills (peso 3x) y
de tokens de texto, canonicalizando ambos lados con la ontología del perfil
(engine.config.load_ontology: canonical → aliases).
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-zA-Z0-9áéíóúñüÁÉÍÓÚÑÜ+#.]{2,}")
_STOPWORDS = frozenset(
    "the a an and or of to in for with on at is are was were be been how what when tell me about"
    " your you my i we they it this that de la el los las un una unas unos y o u en que con para"
    " como sobre del al su sus mi mis fue eran ser estar cuando cómo qué cuéntame".split()
)
SKILL_WEIGHT = 3.0
_STORY_TEXT_KEYS = ("title", "situation", "task", "action", "result", "reflection")


def _tokens(text: str) -> set[str]:
    return {t.lower().rstrip(".") for t in _WORD.findall(text or "")} - _STOPWORDS


def _alias_map(ontology: dict[str, list[str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for canonical, aliases in (ontology or {}).items():
        can = canonical.lower()
        out[can] = can
        for a in aliases or []:
            out[a.lower()] = can
    return out


def _canonicalize(tokens: set[str], amap: dict[str, str]) -> set[str]:
    return {amap.get(t, t) for t in tokens}


def match_stories(
    stories: list[dict], query_text: str, ontology: dict[str, list[str]]
) -> list[tuple[dict, float]]:
    """Historias rankeadas por relevancia a la query. Solo devuelve score > 0."""
    amap = _alias_map(ontology)
    # Los alias multi-palabra ("apache airflow") no sobreviven la tokenización por palabra:
    # detectarlos como frase en la query cruda y añadir su canónico.
    query_low = (query_text or "").lower()
    phrase_hits = {can for alias, can in amap.items() if " " in alias and alias in query_low}
    q = _canonicalize(_tokens(query_text), amap) | phrase_hits
    if not q:
        return []
    out: list[tuple[dict, float]] = []
    for s in stories:
        skills = _canonicalize({str(x).lower() for x in (s.get("skills") or [])}, amap)
        body = " ".join(str(s.get(k) or "") for k in _STORY_TEXT_KEYS)
        toks = _canonicalize(_tokens(body), amap)
        score = SKILL_WEIGHT * len(q & skills) + len(q & toks)
        if score > 0:
            out.append((s, round(score, 1)))
    return sorted(out, key=lambda p: -p[1])


def format_story(story: dict, max_words: int = 400) -> str:
    """Bloque STAR+R listo para pegar; truncado limpio a max_words con elipsis."""
    parts = [f"**{story.get('title', '')}**"]
    for label, key in (
        ("Situación", "situation"),
        ("Tarea", "task"),
        ("Acción", "action"),
        ("Resultado", "result"),
        ("Reflexión", "reflection"),
    ):
        if story.get(key):
            parts.append(f"{label}: {story[key]}")
    text = "\n\n".join(parts)
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"
```

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_stories.py -x
```
Esperado: `5 passed`.

- [ ] Commit:

```bash
rtk git add engine/stories.py tests/test_f3_stories.py
rtk git commit -m "feat(f3): story bank — matcher determinista por overlap con ontología + format_story

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 8 — Story bank API: CRUD + matcher endpoint

**Files:**
- `dashboard/backend/main.py` (EDIT)
- `tests/test_f3_backend_api.py` (EDIT — añade tests)

**Interfaces:**
```
GET    /api/stories                  → {"stories": [Story]}          Story.skills ya parseado
POST   /api/stories                  body StoryBody → {"ok": true, "id": int}       (origin-guarded)
PUT    /api/stories/{id}             body StoryBody (parcial) → {"ok": true}         (origin-guarded; 404)
DELETE /api/stories/{id}             → {"ok": true}                                  (origin-guarded; 404)
GET    /api/stories/match?q=...      → {"matches": [{"story", "score", "formatted"}]} (top 5)
```

**Steps:**

- [ ] RED — añadir a `tests/test_f3_backend_api.py`:

```python
# ── §6.3 Story bank ───────────────────────────────────────────────────────────
def test_stories_crud_and_match(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/stories", json={
            "title": "Pipeline caído en Black Friday", "situation": "ETL caído",
            "task": "Restaurar", "action": "Rollback en Airflow", "result": "40min",
            "reflection": "Alertas", "skills": ["python", "airflow"]})
        assert r.status_code == 200
        sid = r.json()["id"]
        stories = client.get("/api/stories").json()["stories"]
        assert stories[0]["skills"] == ["python", "airflow"]
        assert client.put(f"/api/stories/{sid}", json={"result": "35min"}).status_code == 200
        assert client.get("/api/stories").json()["stories"][0]["result"] == "35min"
        m = client.get("/api/stories/match", params={"q": "python incident on airflow"}).json()
        assert m["matches"] and m["matches"][0]["story"]["id"] == sid
        assert "Situación:" in m["matches"][0]["formatted"]
        assert client.delete(f"/api/stories/{sid}").status_code == 200
        assert client.get("/api/stories").json()["stories"] == []


def test_stories_put_delete_unknown_404(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.put("/api/stories/999", json={"title": "x"}).status_code == 404
        assert client.delete("/api/stories/999").status_code == 404


def test_stories_post_requires_title(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/stories", json={"situation": "x"}).status_code == 422


def test_stories_mutations_reject_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        hdr = {"origin": "https://evil.example.com"}
        assert client.post("/api/stories", json={"title": "x"}, headers=hdr).status_code == 403
        assert client.delete("/api/stories/1", headers=hdr).status_code == 403
```

- [ ] Correr y ver fallo (`404` en `/api/stories`), luego GREEN — `dashboard/backend/main.py`: añadir tras el bloque analytics:

```python
# ── Story bank STAR+R (F3 §6.3) ───────────────────────────────────────────────
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
    return {"stories": db.list_stories()}


@app.post("/api/stories", dependencies=[Depends(require_trusted_origin)])
def api_add_story(body: StoryBody, db: DB = Depends(get_db)):
    sid = db.add_story(**body.model_dump())
    return {"ok": True, "id": sid}


@app.put("/api/stories/{story_id}", dependencies=[Depends(require_trusted_origin)])
def api_update_story(story_id: int, body: StoryPatchBody, db: DB = Depends(get_db)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not db.get_story(story_id):
        raise HTTPException(404, "story not found")
    db.update_story(story_id, fields)
    return {"ok": True}


@app.delete("/api/stories/{story_id}", dependencies=[Depends(require_trusted_origin)])
def api_delete_story(story_id: int, db: DB = Depends(get_db)):
    if not db.delete_story(story_id):
        raise HTTPException(404, "story not found")
    return {"ok": True}


@app.get("/api/stories/match")
def api_match_stories(q: str = "", db: DB = Depends(get_db)):
    from engine.config import load_ontology
    from engine.stories import format_story, match_stories

    ranked = match_stories(db.list_stories(), q, load_ontology())[:5]
    return {
        "matches": [
            {"story": s, "score": score, "formatted": format_story(s)} for s, score in ranked
        ]
    }
```

> Nota de orden de rutas: registrar `GET /api/stories/match` FUNCIONA aunque exista `PUT/DELETE /api/stories/{story_id}` porque los métodos difieren; con `GET /api/stories/{id}` (que NO añadimos) habría que declarar `match` antes.

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_backend_api.py -x
```
Esperado: todo verde (13 tests acumulados en el archivo).

- [ ] Commit:

```bash
rtk git add dashboard/backend/main.py tests/test_f3_backend_api.py
rtk git commit -m "feat(f3): story bank API — CRUD /api/stories + GET /api/stories/match

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 9 — Knock-out pre-scan: `engine/knockouts.py` + persistencia al scorear

**Files:**
- `engine/knockouts.py` (NEW)
- `engine/scoring/run.py` (EDIT)
- `engine/analytics.py` (EDIT — `job_detail` parsea la columna)
- `tests/test_f3_knockouts.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/knockouts.py
def prescan(job: dict, criteria: Criteria, master_cv: dict) -> list[dict]
    # Warning = {"code": "work_authorization"|"years_gap"|"degree"|"language",
    #            "label": str (es, para chips UI), "evidence": str (cita del JD)}
```

**Decisión (persistir vs on-read):** se computa en `score_jobs()` y se PERSISTE en `jobs.knockout_warnings` (columna del Task 1). Justificación: (a) el spec §6.5 exige que analytics y el brain consuman esto determinísticamente — una columna JSON es consultable con SQL, un cómputo on-read no; (b) `score_jobs(rescore=True)` ya re-corre con cada "Buscar" y con cada cambio de criteria, así que la columna se refresca por el mismo ciclo de vida que `fit_reasons`; (c) evita recomputar regex sobre descripciones de ~10KB en cada GET del detalle. No penaliza el score (§6.4: es visibilidad pre-aplicación, los knockouts del scorer ya existen).

Detecciones (todas con evidencia citada, case-insensitive):
1. **Visa/work authorization**: "authorized to work in", "work permit/authorization", "visa sponsorship not available"/"no visa sponsorship"/"without sponsorship", "US citizen(ship)", "security clearance", "must be located/reside/live in".
2. **Años mínimos**: `req > candidate_years + 2` (reutiliza `_required_years` de `engine/scoring/fit.py` — import intra-paquete deliberado; si molesta el guion bajo, renombrarlo a público es un follow-up, no parte de este plan).
3. **Grado requerido**: "bachelor's/master's/PhD … required" y el nivel pedido NO está evidenciado en `master_cv["education"]`.
4. **Idioma requerido**: "fluent/fluency/proficiency/native (in) X" con X ∉ `criteria.languages`.

**Steps:**

- [ ] RED — crear `tests/test_f3_knockouts.py`:

```python
"""F3 §6.4: pre-scan determinista de knock-outs (visa, años, grado, idioma) con evidencia."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.config import Criteria
from engine.knockouts import prescan

CRIT = Criteria(roles=["data scientist"], candidate_years=5, languages=["en", "es"])
CV = {"basics": {"name": "Jane Doe"}, "education": [{"degree": "BSc Computer Science", "school": "UTPL"}]}


def _job(desc: str, title: str = "Data Scientist") -> dict:
    return {"title": title, "description": desc}


def test_detects_work_authorization():
    w = prescan(_job("Applicants must be authorized to work in the United States."), CRIT, CV)
    assert any(x["code"] == "work_authorization" for x in w)
    assert "authorized to work" in [x for x in w if x["code"] == "work_authorization"][0]["evidence"]


def test_detects_no_sponsorship_and_clearance_once():
    w = prescan(_job("Visa sponsorship is not available. Active security clearance preferred."), CRIT, CV)
    codes = [x["code"] for x in w]
    assert codes.count("work_authorization") == 1  # un solo warning de visa, no spam


def test_detects_years_gap_beyond_plus2():
    assert any(x["code"] == "years_gap" for x in prescan(_job("Requires 8+ years of experience."), CRIT, CV))
    assert not any(x["code"] == "years_gap" for x in prescan(_job("Requires 6+ years of experience."), CRIT, CV))


def test_detects_missing_degree_level():
    w = prescan(_job("A Master's degree in CS is required."), CRIT, CV)  # CV solo tiene BSc
    assert any(x["code"] == "degree" for x in w)
    # bachelor pedido + bachelor en CV → sin warning
    assert not any(x["code"] == "degree" for x in prescan(_job("Bachelor's degree required."), CRIT, CV))


def test_detects_required_language_outside_profile():
    w = prescan(_job("Fluency in German is a must."), CRIT, CV)
    assert any(x["code"] == "language" for x in w)
    assert not prescan(_job("Fluent in English required."), CRIT, CV)  # en ∈ languages


def test_clean_jd_yields_no_warnings():
    assert prescan(_job("Great remote role building dashboards with Python and SQL."), CRIT, CV) == []


def test_prescan_persisted_by_score_jobs(tmp_path: Path, monkeypatch):
    import json

    from engine.db.models import DB
    from engine.normalize import Job
    from engine.scoring.run import score_jobs

    monkeypatch.setattr("engine.scoring.run.load_master_cv", lambda: CV)
    monkeypatch.setattr("engine.scoring.run.load_ontology", lambda: {"python": []})
    db = DB(tmp_path / "t.db")
    db.upsert_job(Job(source="greenhouse", title="Data Scientist", company="Acme",
                      location="Remote", is_remote=True,
                      description="Must be authorized to work in the US. Python required."))
    score_jobs(db, CRIT)
    row = db.list_jobs()[0]
    warnings = json.loads(row["knockout_warnings"])
    assert warnings and warnings[0]["code"] == "work_authorization"
```

- [ ] Correr y ver fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_knockouts.py -x
```
Esperado: `ModuleNotFoundError: No module named 'engine.knockouts'`.

- [ ] GREEN — crear `engine/knockouts.py`:

```python
"""Knock-out pre-scan (F3 §6.4) — visibilidad pre-aplicación, sin tocar el score.

Escaneo determinista del JD contra el perfil: requisitos que suelen descalificar a un
candidato remoto internacional (work authorization, clearance, años muy por encima,
grado no evidenciado en el CV, idioma fuera del perfil). Cada warning cita la evidencia.
"""

from __future__ import annotations

import re

from engine.config import Criteria
from engine.scoring.fit import _required_years

_VISA_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bauthori[sz]ed to work in\b", re.I), "pide autorización de trabajo"),
    (re.compile(r"\bwork (?:permit|authori[sz]ation)\b", re.I), "pide permiso de trabajo"),
    (
        re.compile(
            r"\bvisa sponsorship (?:is )?not available\b|\bno visa sponsorship\b"
            r"|\bwithout (?:visa )?sponsorship\b|\b(?:cannot|unable to) (?:offer|provide) (?:visa )?sponsorship\b",
            re.I,
        ),
        "sin patrocinio de visa",
    ),
    (re.compile(r"\bu\.?s\.? citizen(?:ship)?\b", re.I), "pide ciudadanía US"),
    (re.compile(r"\bsecurity clearance\b", re.I), "pide security clearance"),
    (re.compile(r"\bmust (?:be located|reside|live) in\b", re.I), "exige residencia específica"),
]

_DEGREE_RE = re.compile(
    r"\b(bachelor'?s?|master'?s?|ph\.?d|licenciatura|maestr[ií]a|doctorado)\b"
    r"[^.\n]{0,80}\b(?:required|is required|requerid[oa])\b",
    re.I,
)
_DEGREE_LEVEL = {
    "bachelor": 1, "licenciatura": 1, "bsc": 1, "b.s": 1, "ingenier": 1,
    "master": 2, "maestr": 2, "msc": 2, "m.s": 2,
    "phd": 3, "ph.d": 3, "doctorado": 3, "doctor": 3,
}
_LANG_RE = re.compile(
    r"\b(?:fluent|fluency|proficien\w+|native)\s+(?:in\s+)?"
    r"(english|spanish|german|french|portuguese|dutch|italian|ingl[eé]s|alem[aá]n|franc[eé]s|portugu[eé]s|italiano)\b",
    re.I,
)
_LANG_CODE = {
    "english": "en", "inglés": "en", "ingles": "en",
    "spanish": "es",
    "german": "de", "alemán": "de", "aleman": "de",
    "french": "fr", "francés": "fr", "frances": "fr",
    "portuguese": "pt", "portugués": "pt", "portugues": "pt",
    "dutch": "nl", "italian": "it", "italiano": "it",
}


def _evidence(text: str, m: re.Match, pad: int = 60) -> str:
    start, end = max(m.start() - pad, 0), min(m.end() + pad, len(text))
    return " ".join(text[start:end].split())


def _level_in(text: str) -> int:
    low = text.lower()
    return max((lv for term, lv in _DEGREE_LEVEL.items() if term in low), default=0)


def _cv_degree_level(master_cv: dict) -> int:
    hay = " ".join(str(e) for e in (master_cv.get("education") or []))
    return _level_in(hay)


def prescan(job: dict, criteria: Criteria, master_cv: dict) -> list[dict]:
    """Warnings deterministas {code, label, evidence}. Lista vacía = nada detectado."""
    text = f"{job.get('title') or ''}\n{job.get('description') or ''}"
    warnings: list[dict] = []
    # 1. Visa / work authorization / clearance / residencia — un solo warning (el primero).
    for rx, label in _VISA_PATTERNS:
        m = rx.search(text)
        if m:
            warnings.append(
                {"code": "work_authorization", "label": label, "evidence": _evidence(text, m)}
            )
            break
    # 2. Años muy por encima del candidato (gap > 2 — más laxo que el scorer, es un aviso).
    req = _required_years(job.get("description") or "")
    if req and criteria.candidate_years and req > criteria.candidate_years + 2:
        warnings.append(
            {
                "code": "years_gap",
                "label": f"pide {req}+ años (tienes ~{criteria.candidate_years})",
                "evidence": f"{req}+ years required",
            }
        )
    # 3. Grado requerido no evidenciado en el master CV.
    m = _DEGREE_RE.search(text)
    if m:
        asked = _level_in(m.group(1))
        if asked > _cv_degree_level(master_cv):
            warnings.append(
                {
                    "code": "degree",
                    "label": f"exige {m.group(1).lower()} (no evidenciado en tu CV)",
                    "evidence": _evidence(text, m),
                }
            )
    # 4. Idioma requerido fuera del perfil.
    m = _LANG_RE.search(text)
    if m:
        code = _LANG_CODE.get(m.group(1).lower())
        if code and code not in criteria.languages:
            warnings.append(
                {
                    "code": "language",
                    "label": f"exige {m.group(1)} fluido",
                    "evidence": _evidence(text, m),
                }
            )
    return warnings
```

- [ ] GREEN — `engine/scoring/run.py`: dentro del loop de `score_jobs()`, reemplazar la línea `db.set_fit(j["id"], res.score, res.reasons, res.knockouts)` por:

```python
        warnings = prescan(j, criteria, master)
        db.set_fit(j["id"], res.score, res.reasons, res.knockouts, warnings=warnings)
```
y añadir el import arriba: `from engine.knockouts import prescan`.

- [ ] GREEN — `engine/analytics.py`, en `job_detail()` (línea ~160), tras el parse de `knockout_flags`:

```python
    job["knockout_warnings"] = json.loads(job.get("knockout_warnings") or "[]")
```

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_knockouts.py tests/test_engine.py tests/test_quality_gates.py -x
```
Esperado: `8 passed` nuevos + scoring existente intacto.

- [ ] Commit:

```bash
rtk git add engine/knockouts.py engine/scoring/run.py engine/analytics.py tests/test_f3_knockouts.py
rtk git commit -m "feat(f3): knock-out pre-scan — visa/años/grado/idioma con evidencia, persistido al scorear

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 10 — Machine summary: deltas por factor en `score_job` + `score_breakdown` persistido y expuesto

**Files:**
- `engine/scoring/fit.py` (EDIT)
- `engine/scoring/run.py` (EDIT)
- `engine/analytics.py` (EDIT — `job_detail` parsea)
- `tests/test_f3_score_breakdown.py` (NEW)

**Interfaces (firmas exactas):**
```python
# engine/scoring/fit.py
@dataclass
class ScoreResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    knockouts: list[str] = field(default_factory=list)
    disqualified: bool = False
    factors: list[dict] = field(default_factory=list)   # NEW: [{"factor","delta","note"}]

    def breakdown(self) -> dict:
        # {"base": 50.0, "final": score, "disqualified": bool, "factors": [...],
        #  "reasons": [...], "knockouts": [...]}
```

Implementación: `score_job` gana un helper interno `_apply(delta, factor, note)` que reemplaza cada par `score += X; reasons.append(y)`. Los ajustes de la función son mecánicos (misma aritmética, mismos strings de `reasons` — los tests existentes de scoring NO deben cambiar). Factores canónicos: `blocklist, role, remote, onsite_gate, seniority, salary, must_haves, deal_breaker, knockout_terms, language, freshness, years, learning`. F2 añade el factor `geo` con el mismo mecanismo.

**Steps:**

- [ ] RED — crear `tests/test_f3_score_breakdown.py`:

```python
"""F3 §6.5: machine summary — deltas por factor en el score, persistidos por corrida."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config import Criteria
from engine.scoring.fit import score_job

CRIT = Criteria(roles=["data scientist"], remote_required=True, must_haves=["python"],
                salary_floor_usd=70000)

JOB = {"title": "Senior Data Scientist", "company": "Acme", "is_remote": 1,
       "workplace_type": "remote", "salary_min": 90000, "salary_max": 120000,
       "salary_interval": "yearly", "description": "We use python and sql daily."}


def test_score_job_records_factor_deltas():
    res = score_job(JOB, CRIT)
    factors = {f["factor"]: f for f in res.factors}
    assert factors["role"]["delta"] == 25
    assert factors["remote"]["delta"] == 15
    assert factors["salary"]["delta"] == 10
    assert all({"factor", "delta", "note"} <= set(f) for f in res.factors)


def test_deltas_sum_to_final_score_when_unclamped():
    res = score_job(JOB, CRIT)
    assert res.score == 50.0 + sum(f["delta"] for f in res.factors)


def test_breakdown_shape():
    b = score_job(JOB, CRIT).breakdown()
    assert b["base"] == 50.0 and b["final"] == score_job(JOB, CRIT).score
    assert b["disqualified"] is False and isinstance(b["factors"], list)
    assert b["reasons"] and b["knockouts"] == []


def test_negative_factor_recorded():
    res = score_job({**JOB, "title": "Senior Underwater Basket Weaver",
                     "description": "no relevant terms"}, CRIT)
    factors = {f["factor"]: f for f in res.factors}
    assert factors["role"]["delta"] == -35


def test_breakdown_persisted_and_exposed(tmp_path: Path, monkeypatch):
    from engine import analytics
    from engine.db.models import DB
    from engine.normalize import Job
    from engine.scoring.run import score_jobs

    monkeypatch.setattr("engine.scoring.run.load_master_cv", lambda: {})
    monkeypatch.setattr("engine.scoring.run.load_ontology", lambda: {})
    db = DB(tmp_path / "t.db")
    db.upsert_job(Job(source="greenhouse", title="Senior Data Scientist", company="Acme",
                      location="Remote", is_remote=True, description="python everywhere"))
    score_jobs(db, CRIT)
    row = db.list_jobs()[0]
    stored = json.loads(row["score_breakdown"])
    assert stored["final"] == row["fit_score"] and stored["factors"]
    detail = analytics.job_detail(db, row["id"])
    assert detail["job"]["score_breakdown"]["base"] == 50.0
```

- [ ] Correr y ver fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_score_breakdown.py -x
```
Esperado: `AttributeError: 'ScoreResult' object has no attribute 'factors'`.

- [ ] GREEN — `engine/scoring/fit.py`: ampliar `ScoreResult` (línea ~39):

```python
@dataclass
class ScoreResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    knockouts: list[str] = field(default_factory=list)
    disqualified: bool = False
    factors: list[dict] = field(default_factory=list)  # machine summary (F3 §6.5)

    def breakdown(self) -> dict:
        """Desglose completo por corrida — persistido en jobs.score_breakdown."""
        return {
            "base": 50.0,
            "final": self.score,
            "disqualified": self.disqualified,
            "factors": self.factors,
            "reasons": self.reasons,
            "knockouts": self.knockouts,
        }
```

- [ ] GREEN — `engine/scoring/fit.py`, dentro de `score_job` (línea ~73): declarar tras `disq = False`:

```python
    factors: list[dict] = []

    def _apply(delta: float, factor: str, note: str) -> None:
        """Ajusta el score y registra el delta con su razón — misma aritmética de siempre."""
        nonlocal score
        score += delta
        reasons.append(note)
        factors.append({"factor": factor, "delta": delta, "note": note})
```

y convertir mecánicamente CADA par `score ± X` + `reasons.append(...)` a `_apply(...)`, manteniendo strings idénticos. Conversión exhaustiva (número de línea actual → llamada):

```python
# 0. blocklist (línea 94) — short-circuit; añadir factors al return:
        return ScoreResult(0.0, ["company in blocklist"], ["company in blocklist"], True,
                           [{"factor": "blocklist", "delta": -50.0, "note": "company in blocklist"}])
# 1. role (98-106):
        _apply(25, "role", "role matches title")
        _apply(8, "role", "role matches description only")
        _apply(-35, "role", "no role keyword match")
# 2. remote (112-119): _apply(15, "remote", "remote")
#    (la rama disq "not remote" no cambia score → dejar reasons.append como está)
# 2b. onsite gate (126-131): sin delta (disq) → dejar como está
# 3. seniority (150-166):
        _apply(-12, "seniority", f"{term} title — typically wants ~{criteria.stretch_min_years}+ yrs (you have ~{cy})")
        _apply(6, "seniority", f"{term} seniority")
        _apply(10, "seniority", "seniority matches")
# 4. salary (177-184):
        _apply(10, "salary", "salary meets floor")
        _apply(-10, "salary", "salary below floor")
# 5. must-haves (188-190): _apply(min(len(hits) * 4, 12), "must_haves", f"must-haves: {', '.join(hits)}")
# 7. knockout terms (201-203): _apply(-min(len(ko) * 5, 10), "knockout_terms", f"knockout flags: {', '.join(ko)}")
# 8. language (211-212): _apply(-25, "language", f"likely {lang}-language posting (off-target)")
# 9. freshness (220-222): _apply(-15, "freshness", f"posted ~{age:.0f}d ago (stale, >{criteria.max_age_days}d)")
# 10. years (236-247):
        _apply(-18, "years", f"requires {req}+ yrs — far above your ~{cy}")
        _apply(-9, "years", f"requires {req}+ yrs (above your ~{cy})")
        _apply(-8, "years", f"requires {req}+ years (> your {criteria.max_years_required})")
# 11. learnings (256-257): _apply(4, "learning", f"learning: {obs}")
```

OJO: en las ramas donde hoy `knockouts.append(...)` acompaña al ajuste (stretch, years), el `knockouts.append` se conserva tal cual junto al `_apply` (el helper solo cubre score+reason). El return final pasa a:

```python
    return ScoreResult(round(score, 1), reasons, knockouts, disq, factors)
```

- [ ] GREEN — `engine/scoring/run.py`: la línea del Task 9 pasa a persistir también el breakdown:

```python
        warnings = prescan(j, criteria, master)
        db.set_fit(
            j["id"], res.score, res.reasons, res.knockouts,
            warnings=warnings, breakdown=res.breakdown(),
        )
```

- [ ] GREEN — `engine/analytics.py`, en `job_detail()` junto al parse del Task 9:

```python
    job["score_breakdown"] = json.loads(job["score_breakdown"]) if job.get("score_breakdown") else None
```

- [ ] Verificar (CRÍTICO: los tests de scoring existentes no deben cambiar — misma aritmética):

```bash
rtk uv run --group dev pytest tests/test_f3_score_breakdown.py tests/test_engine.py tests/test_fit_domain.py tests/test_quality_gates.py tests/test_learning.py -x
```
Esperado: `5 passed` nuevos + cero regresiones.

- [ ] Commit:

```bash
rtk git add engine/scoring/fit.py engine/scoring/run.py engine/analytics.py tests/test_f3_score_breakdown.py
rtk git commit -m "feat(f3): machine summary — deltas por factor en score_job, breakdown persistido y en el detalle

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 11 — Reverse ATS discovery: `engine/discovery/reverse.py` + seeds por dominio

**Files:**
- `engine/discovery/reverse.py` (NEW)
- `config/seeds/default/discovery_seeds.yaml`, `config/seeds/data/discovery_seeds.yaml`, `config/seeds/architecture/discovery_seeds.yaml` (NEW)
- `engine/profiles.py` (EDIT — `_SEED_FILES`)
- `tests/test_f3_reverse_discovery.py` (NEW)

**Honestidad técnica (investigado en el código y en las APIs):** ni Greenhouse (`boards-api.greenhouse.io`), ni Lever (`api.lever.co/v0/postings`), ni Ashby (`api.ashbyhq.com/posting-api/job-board`) exponen un directorio global consultable por keyword ("dame las empresas con jobs de X") — solo exponen el board de UNA empresa si conoces su token (exactamente lo que ya consumen `engine/discovery/ats/{greenhouse,lever,ashby}.py`). El `scan-ats-full` de career-ops funciona igual: itera una lista curada de slugs. Por tanto el modelo honesto es: **tomar empresas candidatas** (semillas del dominio del perfil en `discovery_seeds.yaml` + nombres que el usuario escriba en la UI), **derivar tokens plausibles** del nombre, **probar cada ATS** con los mismos endpoints keyless que ya usa discovery, y **sugerir solo las que tengan posiciones que matcheen `criteria.all_role_terms`**. La confirmación del usuario las añade a `companies.yaml` (vía `save_company` del Task 2).

**Interfaces (firmas exactas):**
```python
# engine/discovery/reverse.py
GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"

def slug_candidates(name: str) -> list[str]                       # "Acme Corp" → ["acmecorp","acme-corp","acme"]
def probe_company(name: str, client: httpx.Client) -> dict | None # {"company","ats","token","jobs_count","titles"}
def suggest_companies(names: list[str], criteria: Criteria, *,
                      client: httpx.Client | None = None, max_names: int = 15) -> list[dict]
    # [{"company","ats","token","jobs_count","matching_titles"}] — solo con ≥1 título que matchee
```

**Steps:**

- [ ] RED — crear `tests/test_f3_reverse_discovery.py` (cero red: se stubea `get_json`):

```python
"""F3 §6.5: reverse ATS discovery — probing honesto de candidatas contra boards públicos."""

from __future__ import annotations

import httpx
import pytest

from engine.config import Criteria
from engine.discovery import reverse

CRIT = Criteria(roles=["data scientist"])


def test_slug_candidates():
    assert reverse.slug_candidates("Acme Corp") == ["acmecorp", "acme-corp", "acme"]
    assert reverse.slug_candidates("Acme") == ["acme"]


def _fake_get_json(payloads: dict[str, object]):
    """URL → payload; cualquier otra URL simula 404."""

    def fake(client, url, params=None, retries=2):
        if url in payloads:
            return payloads[url]
        raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url),
                                    response=httpx.Response(404))

    return fake


def test_probe_company_finds_greenhouse_board(monkeypatch):
    gh_url = reverse.GREENHOUSE_URL.format(token="acmecorp")
    monkeypatch.setattr(reverse, "get_json", _fake_get_json({
        gh_url: {"jobs": [{"title": "Senior Data Scientist"}, {"title": "Chef"}]}}))
    hit = reverse.probe_company("Acme Corp", client=None)
    assert hit == {"company": "Acme Corp", "ats": "greenhouse", "token": "acmecorp",
                   "jobs_count": 2, "titles": ["Senior Data Scientist", "Chef"]}


def test_probe_company_falls_through_to_lever(monkeypatch):
    lever_url = reverse.LEVER_URL.format(token="acme")
    monkeypatch.setattr(reverse, "get_json", _fake_get_json({
        lever_url: [{"text": "Data Scientist"}]}))
    hit = reverse.probe_company("Acme", client=None)
    assert hit and hit["ats"] == "lever" and hit["titles"] == ["Data Scientist"]


def test_probe_company_none_when_no_board(monkeypatch):
    monkeypatch.setattr(reverse, "get_json", _fake_get_json({}))
    assert reverse.probe_company("Ghost Startup", client=None) is None


def test_suggest_companies_filters_by_role_terms_and_known(monkeypatch):
    gh_acme = reverse.GREENHOUSE_URL.format(token="acmecorp")
    gh_beta = reverse.GREENHOUSE_URL.format(token="betabakery")
    monkeypatch.setattr(reverse, "get_json", _fake_get_json({
        gh_acme: {"jobs": [{"title": "Staff Data Scientist"}]},
        gh_beta: {"jobs": [{"title": "Pastry Chef"}]},          # sin match de rol → fuera
    }))
    monkeypatch.setattr(reverse, "load_companies", lambda: [])
    out = reverse.suggest_companies(["Acme Corp", "Beta Bakery", "  "], CRIT, client=None)
    assert len(out) == 1
    assert out[0]["company"] == "Acme Corp"
    assert out[0]["matching_titles"] == ["Staff Data Scientist"]


def test_suggest_companies_skips_already_configured(monkeypatch):
    from engine.config import CompanyTarget

    monkeypatch.setattr(reverse, "load_companies",
                        lambda: [CompanyTarget(company="Acme Corp", ats="greenhouse", token="x")])
    called = []
    monkeypatch.setattr(reverse, "probe_company", lambda n, c: called.append(n))
    assert reverse.suggest_companies(["Acme Corp"], CRIT, client=None) == []
    assert called == []  # ni siquiera se probó


def test_discovery_seeds_files_exist():
    from pathlib import Path

    for pack in ("default", "data", "architecture"):
        assert (Path("config/seeds") / pack / "discovery_seeds.yaml").exists()
```

- [ ] Correr y ver fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_reverse_discovery.py -x
```
Esperado: `ModuleNotFoundError: No module named 'engine.discovery.reverse'`.

- [ ] GREEN — crear `engine/discovery/reverse.py`:

```python
"""Reverse ATS discovery (F3 §6.5) — probing de empresas candidatas contra boards públicos.

HONESTIDAD: ningún ATS publica un directorio global por keyword. Lo público y keyless es
el board de CADA empresa si conoces su token (los mismos endpoints que consume
engine/discovery/ats/*). Modelo: lista de candidatas (seeds del dominio + input del
usuario) → tokens plausibles → probar Greenhouse/Lever/Ashby → sugerir solo las que
tengan posiciones que matcheen los role_terms del perfil. El usuario confirma en la UI
y save_company() las añade a companies.yaml.
"""

from __future__ import annotations

import re

import httpx

from engine.config import Criteria, load_companies
from engine.discovery.http import get_json, make_client
from engine.normalize import norm_company

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def slug_candidates(name: str) -> list[str]:
    """Tokens plausibles a partir del nombre: 'Acme Corp' → acmecorp, acme-corp, acme."""
    base = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    if not base:
        return []
    out: list[str] = []
    for cand in (base.replace(" ", ""), base.replace(" ", "-"), base.split(" ")[0]):
        if cand and cand not in out:
            out.append(cand)
    return out


def _titles(ats: str, data: object) -> list[str]:
    if ats == "greenhouse":
        return [j.get("title", "") for j in (data or {}).get("jobs", [])]  # type: ignore[union-attr]
    if ats == "lever":
        return [p.get("text", "") for p in (data if isinstance(data, list) else [])]
    return [j.get("title", "") for j in ((data or {}).get("jobs") or [])]  # type: ignore[union-attr]


def probe_company(name: str, client: httpx.Client | None) -> dict | None:
    """Prueba cada ATS con los tokens plausibles; primer board con jobs gana."""
    probes: list[tuple[str, str, dict | None]] = []
    for token in slug_candidates(name):
        probes.append(("greenhouse", GREENHOUSE_URL.format(token=token), None))
        probes.append(("lever", LEVER_URL.format(token=token), {"mode": "json", "limit": 100}))
    compact = re.sub(r"[^A-Za-z0-9]", "", name)
    for token in dict.fromkeys([compact, compact.lower()]):  # Ashby es case-sensitive
        if token:
            probes.append(("ashby", ASHBY_URL.format(token=token), None))
    for ats, url, params in probes:
        try:
            data = get_json(client, url, params=params, retries=0)
        except httpx.HTTPError:
            continue
        titles = [t for t in _titles(ats, data) if t]
        if titles:
            token = url.rstrip("/").split("/")[-1] if ats != "greenhouse" else url.split("/boards/")[1].split("/")[0]
            return {"company": name, "ats": ats, "token": token,
                    "jobs_count": len(titles), "titles": titles}
    return None


def suggest_companies(
    names: list[str],
    criteria: Criteria,
    *,
    client: httpx.Client | None = None,
    max_names: int = 15,
) -> list[dict]:
    """Sugerencias {company, ats, token, jobs_count, matching_titles} para companies.yaml."""
    known = {norm_company(c.company) for c in load_companies()}
    clean = [n.strip() for n in names if n and n.strip()]
    candidates = [n for n in dict.fromkeys(clean) if norm_company(n) not in known][:max_names]
    owns = client is None and bool(candidates)
    if owns:
        client = make_client(timeout=10)
    terms = criteria.all_role_terms
    out: list[dict] = []
    try:
        for name in candidates:
            hit = probe_company(name, client)
            if not hit:
                continue
            matching = [t for t in hit["titles"] if any(term in t.lower() for term in terms)]
            if not matching:
                continue
            out.append(
                {
                    "company": name,
                    "ats": hit["ats"],
                    "token": hit["token"],
                    "jobs_count": hit["jobs_count"],
                    "matching_titles": matching[:5],
                }
            )
    finally:
        if owns and client is not None:
            client.close()
    return out
```

> Nota sobre el token de greenhouse en `probe_company`: la URL termina en `/jobs`, por eso el token se extrae del segmento tras `/boards/` y no del último segmento. El test `test_probe_company_finds_greenhouse_board` lo verifica (`token == "acmecorp"`).

- [ ] GREEN — crear los seeds (ejemplos FICTICIOS — repo público; el usuario los edita en su perfil):

`config/seeds/default/discovery_seeds.yaml`:
```yaml
# Empresas candidatas para el reverse ATS discovery (F3). Atlas probará cada nombre
# contra los boards públicos de Greenhouse/Lever/Ashby y te sugerirá las que tengan
# posiciones que matcheen tus role_terms. Edita esta lista con empresas de tu industria.
# (Los nombres de ejemplo son ficticios — reemplázalos.)
candidates: []
# candidates:
#   - Acme Analytics
#   - Umbrella Robotics
```

`config/seeds/data/discovery_seeds.yaml`:
```yaml
# Candidatas para reverse ATS discovery (dominio: data). Nombres de EJEMPLO ficticios —
# reemplaza con empresas data-first reales de tu radar antes de usarlo.
candidates:
  - Acme Analytics
  - Umbrella Data Labs
  - Initech ML
```

`config/seeds/architecture/discovery_seeds.yaml`:
```yaml
# Candidatas para reverse ATS discovery (dominio: architecture). Nombres de EJEMPLO
# ficticios — reemplaza con estudios/proptech reales de tu radar antes de usarlo.
candidates:
  - Acme Studio
  - Umbrella BIM Works
```

- [ ] GREEN — `engine/profiles.py`: añadir a `_SEED_FILES` (línea ~31), tras la fila de `interview_topics.yaml`:

```python
    ("config/discovery_seeds.yaml", "discovery_seeds.yaml"),
```
(El copiado es "domain pack primero, default después" — mecanismo existente `_seed_source`; packs sin el archivo caen al default vacío.)

- [ ] Verificar:

```bash
rtk uv run --group dev pytest tests/test_f3_reverse_discovery.py tests/test_profiles.py -x
```
Esperado: `7 passed` nuevos + perfiles intactos.

- [ ] Commit:

```bash
rtk git add engine/discovery/reverse.py engine/profiles.py config/seeds/default/discovery_seeds.yaml config/seeds/data/discovery_seeds.yaml config/seeds/architecture/discovery_seeds.yaml tests/test_f3_reverse_discovery.py
rtk git commit -m "feat(f3): reverse ATS discovery — probing honesto de candidatas + seeds por dominio

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 12 — Exponer en la web lo que hoy es CLI-only (§6.5): resolve/add company, import connections, salud del sistema

**Files:**
- `pyproject.toml` (EDIT — `python-multipart` para el upload multipart)
- `dashboard/backend/main.py` (EDIT — endpoints `companies/resolve`, `companies/add`, `discovery/suggest`, `connections/import`, `system/health`)
- `dashboard/frontend/src/api.ts` (EDIT — tipos + funciones F3 + `postForm`)
- `dashboard/frontend/src/components/SettingsOps.tsx` (NEW — panel embebido en Ajustes)
- `dashboard/frontend/src/components/SettingsModal.tsx` (EDIT — montar `<SettingsOps/>`)
- `tests/test_f3_backend_api.py` (EDIT — sección ops)
- `dashboard/frontend/src/components/SettingsOps.test.tsx` (NEW — Vitest)

**Interfaces:**
```
POST /api/companies/resolve   body {"url": str}
     → {"resolved": bool, "company": str|null, "ats": str|null, "token": str|null,
        "preview_jobs_count": int, "already_configured": bool}
     (origin-guarded; 400 si falta url; resolved=false si no hay ATS conocido — nunca 500)
POST /api/companies/add       body {"company": str, "ats": str, "token": str, "eu"?: bool,
                                    "instance"?: str, "careers_url"?: str}
     → {"ok": bool, "added": bool}   (added=false si ya existía — dedupe de save_company)
     (origin-guarded; 400 si la entrada no valida CompanyTarget)
POST /api/discovery/suggest   body {"names"?: [str]}   (vacío → usa load_discovery_seeds())
     → {"suggestions": [{company, ats, token, jobs_count, matching_titles}]}
     (origin-guarded — hace red saliente; reusa reverse.suggest_companies)
POST /api/connections/import  multipart form-data, campo `file` = Connections.csv
     → {"ok": bool, "imported": int}
     (origin-guarded; 400 si no hay archivo o CSV ilegible)
GET  /api/system/health
     → {"profile": str, "db": {"path": str, "ok": bool, "jobs": int},
        "counts": {state: int}, "last_run": str|null, "last_success": str|null,
        "sources": [{source, ok: bool, count: int, run_at: str|null, error: str|null}],
        "safeguards": {"api_key_unset": bool, "base_url_default": bool}}
```

Nota de coordinación con F2: F2 añade `GET/PUT /api/criteria` y puede haber creado ya un helper de subida de archivos. `POST /api/connections/import` es independiente (usa `import_connections_csv`, no criteria). Si F2 dejó un patrón de `UploadFile` en `main.py`, reutilizar su import de `UploadFile, File` — el contrato de este task se mantiene. `/api/system/health` consolida lo que el CLI hace en `doctor()` (safeguards $0) + `status()` (counts, source health, last_run) sin duplicar lógica: reusa `db.counts_by_state()`, `db.latest_source_health()`, `db.meta_get()` y lee las mismas env vars que `doctor`.

**Steps:**

- [ ] GREEN (dep primero, sin RED — es una dependencia de runtime del upload) — `pyproject.toml`: añadir a `dependencies` (tras `pdfplumber>=0.11`):

```toml
    "python-multipart>=0.0.9",   # form-data upload de Connections.csv (F3 §6.5)
```
y sincronizar:
```bash
rtk uv sync
```
Esperado: `python-multipart` instalado (Starlette lo exige para `UploadFile`/`Form`).

- [ ] RED — añadir a `tests/test_f3_backend_api.py` (la sección ops; el helper `_seed_job` ya existe del Task 4):

```python
# ── §6.5 Ops: resolve/add company, import connections, system health ──────────
def test_resolve_company_returns_ats_contract(atlas_app, monkeypatch):
    import dashboard.backend.main as backend_main

    monkeypatch.setattr(
        backend_main, "resolve_ats",
        lambda url, client=None: {"ats": "greenhouse", "token": "acmerobotics", "eu": False},
    )
    monkeypatch.setattr(backend_main, "_probe_company_jobs", lambda ats, token: (3, "Acme Robotics"))
    with TestClient(atlas_app) as client:
        r = client.post("/api/companies/resolve", json={"url": "https://boards.greenhouse.io/acmerobotics"})
    body = r.json()
    assert r.status_code == 200 and body["resolved"] is True
    assert body["ats"] == "greenhouse" and body["token"] == "acmerobotics"
    assert body["preview_jobs_count"] == 3 and body["already_configured"] is False


def test_resolve_company_unknown_ats_is_not_error(atlas_app, monkeypatch):
    import dashboard.backend.main as backend_main

    monkeypatch.setattr(backend_main, "resolve_ats", lambda url, client=None: None)
    with TestClient(atlas_app) as client:
        r = client.post("/api/companies/resolve", json={"url": "https://example.com/careers"})
    assert r.status_code == 200 and r.json()["resolved"] is False


def test_resolve_company_requires_url(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/companies/resolve", json={}).status_code == 422


def test_add_company_appends_and_dedupes(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "COMPANIES_PATH", tmp_path / "companies.yaml")
    entry = {"company": "Acme Robotics", "ats": "greenhouse", "token": "acmerobotics"}
    with TestClient(atlas_app) as client:
        r1 = client.post("/api/companies/add", json=entry)
        r2 = client.post("/api/companies/add", json=entry)
    assert r1.status_code == 200 and r1.json() == {"ok": True, "added": True}
    assert r2.status_code == 200 and r2.json() == {"ok": True, "added": False}
    import yaml

    data = yaml.safe_load((tmp_path / "companies.yaml").read_text())
    assert len(data["companies"]) == 1 and data["companies"][0]["token"] == "acmerobotics"


def test_add_company_rejects_invalid(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/companies/add", json={"token": "x"}).status_code == 400


def test_suggest_companies_uses_reverse(atlas_app, monkeypatch):
    import dashboard.backend.main as backend_main

    monkeypatch.setattr(
        backend_main.reverse, "suggest_companies",
        lambda names, criteria, client=None: [
            {"company": "Acme Corp", "ats": "greenhouse", "token": "acmecorp",
             "jobs_count": 2, "matching_titles": ["Staff Data Scientist"]}
        ],
    )
    with TestClient(atlas_app) as client:
        r = client.post("/api/discovery/suggest", json={"names": ["Acme Corp"]})
    body = r.json()
    assert r.status_code == 200 and body["suggestions"][0]["company"] == "Acme Corp"


def test_import_connections_multipart(atlas_app):
    csv = (
        "First Name,Last Name,Company,Position,URL,Email Address\n"
        "Jane,Doe,Acme,Data Lead,https://x/jane,jane@x.com\n"
        "John,Roe,Beta,ML Eng,https://x/john,john@x.com\n"
    )
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/connections/import",
            files={"file": ("Connections.csv", csv, "text/csv")},
        )
    assert r.status_code == 200 and r.json() == {"ok": True, "imported": 2}


def test_import_connections_rejects_empty(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/connections/import", files={"file": ("empty.csv", "", "text/csv")})
    assert r.status_code == 200 and r.json()["imported"] == 0


def test_system_health_consolidates_status_and_doctor(atlas_app, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    with TestClient(atlas_app) as client:
        _seed_job("applied")
        h = client.get("/api/system/health").json()
    assert h["db"]["ok"] is True and h["db"]["jobs"] >= 1
    assert "applied" in h["counts"]
    assert isinstance(h["sources"], list)
    assert h["safeguards"]["api_key_unset"] is True
    assert set(h) >= {"profile", "db", "counts", "last_run", "sources", "safeguards"}


def test_ops_posts_reject_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        hdr = {"origin": "https://evil.example.com"}
        assert client.post("/api/companies/resolve", json={"url": "x"}, headers=hdr).status_code == 403
        assert client.post("/api/companies/add", json={}, headers=hdr).status_code == 403
        assert client.post("/api/discovery/suggest", json={}, headers=hdr).status_code == 403
        assert client.post("/api/connections/import", files={"file": ("c.csv", "", "text/csv")},
                           headers=hdr).status_code == 403
```

- [ ] Correr y ver el fallo:

```bash
rtk uv run --group dev pytest tests/test_f3_backend_api.py -x -k "resolve or add_company or suggest or connections or system_health or ops_posts"
```
Esperado: `404` en `/api/companies/resolve` (el endpoint no existe todavía).

- [ ] GREEN — `dashboard/backend/main.py`: ampliar los imports del top del módulo. La línea `from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request` pasa a incluir `File, Form, UploadFile`:

```python
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
```
y junto a `from engine import analytics, profiles` añadir el import del resolver y el reverse (module-level para que los tests puedan `monkeypatch.setattr(backend_main, "resolve_ats", ...)`):

```python
from engine.discovery import reverse
from engine.discovery.registry import resolve_ats
```

- [ ] GREEN — `dashboard/backend/main.py`: reemplazar el endpoint `/api/health` (línea ~463) por su versión ampliada, conservando el `/api/health` legacy trivial y añadiendo el consolidado `/api/system/health`:

```python
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
    except Exception:
        return 0, None
    finally:
        client.close()


# ── Exponer CLI-only en la web (F3 §6.5): resolve/add company, suggest, connections, health ──
class ResolveBody(BaseModel):
    url: str


class CompanyEntryBody(BaseModel):
    company: str
    ats: str
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
        return {"resolved": False, "company": None, "ats": None, "token": None,
                "preview_jobs_count": 0, "already_configured": False}
    token = contract.get("token") or ""
    count, company_name = _probe_company_jobs(contract["ats"], token)
    # Nombre sugerido: el que reporte el board, o derivado del host de la URL.
    from urllib.parse import urlsplit

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
    except Exception as e:  # pydantic ValidationError de CompanyTarget
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
async def api_import_connections(file: UploadFile = File(...), db: DB = Depends(get_db)):
    """Upload de LinkedIn Connections.csv → import_connections_csv (referral detection)."""
    import tempfile
    from pathlib import Path

    from engine.referrals.connections import import_connections_csv

    raw = await file.read()
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)
    try:
        imported = import_connections_csv(db, tmp_path)
    except Exception as e:
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
        "last_success": db.meta_get("last_success"),
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
```

- [ ] Verificar backend:

```bash
rtk uv run --group dev pytest tests/test_f3_backend_api.py -x
```
Esperado: toda la suite del archivo verde, incluidos los 9 tests ops nuevos.

- [ ] GREEN — `dashboard/frontend/src/api.ts`: añadir el tipo y el helper `postForm` (tras `post<T>()`, línea ~188):

```typescript
export type SystemHealth = {
  profile: string;
  db: { path: string; ok: boolean; jobs: number };
  counts: Record<string, number>;
  last_run: string | null;
  last_success: string | null;
  sources: { source: string; ok: boolean; count: number; run_at: string | null; error: string | null }[];
  safeguards: { api_key_unset: boolean; base_url_default: boolean };
};

export type ResolvedCompany = {
  resolved: boolean;
  company: string | null;
  ats: string | null;
  token: string | null;
  preview_jobs_count: number;
  already_configured: boolean;
};

export type CompanySuggestion = {
  company: string;
  ats: string;
  token: string;
  jobs_count: number;
  matching_titles: string[];
};

async function postForm<T>(url: string, form: FormData): Promise<T> {
  // NO fijar Content-Type: el navegador añade el boundary del multipart automáticamente.
  const r = await fetch(url, { method: "POST", body: form });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}
```

- [ ] GREEN — `dashboard/frontend/src/api.ts`: añadir las funciones F3 al objeto `api` (antes del cierre `};`, junto a `exportUrl`):

```typescript
  systemHealth: () => get<SystemHealth>("/api/system/health"),
  resolveCompany: (url: string) => post<ResolvedCompany>("/api/companies/resolve", { url }),
  addCompany: (entry: { company: string; ats: string; token?: string | null }) =>
    post<{ ok: boolean; added: boolean }>("/api/companies/add", entry),
  suggestCompanies: (names?: string[]) =>
    post<{ suggestions: CompanySuggestion[] }>("/api/discovery/suggest", { names: names ?? [] }),
  importConnections: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<{ ok: boolean; imported: number }>("/api/connections/import", form);
  },
```

- [ ] GREEN — crear `dashboard/frontend/src/components/SettingsOps.tsx`:

```tsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type CompanySuggestion, type ResolvedCompany, type SystemHealth } from "../api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Separator } from "./ui/separator";

/** Salud del sistema + añadir empresa por URL + importar conexiones (F3 §6.5). */
export function SettingsOps() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [url, setUrl] = useState("");
  const [resolved, setResolved] = useState<ResolvedCompany | null>(null);
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<CompanySuggestion[]>([]);

  function refreshHealth() {
    api.systemHealth().then(setHealth).catch(() => setHealth(null));
  }
  useEffect(refreshHealth, []);

  async function resolveUrl() {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const r = await api.resolveCompany(url.trim());
      setResolved(r);
      if (!r.resolved) toast.error("No detecté un ATS conocido en esa URL");
    } catch {
      toast.error("No se pudo resolver la URL");
    } finally {
      setBusy(false);
    }
  }

  async function addResolved() {
    if (!resolved?.resolved || !resolved.ats) return;
    try {
      const r = await api.addCompany({
        company: resolved.company ?? "",
        ats: resolved.ats,
        token: resolved.token,
      });
      toast.success(r.added ? `Añadida ${resolved.company}` : "Ya estaba en tu lista");
      setResolved(null);
      setUrl("");
    } catch {
      toast.error("No se pudo añadir la empresa");
    }
  }

  async function runSuggest() {
    setBusy(true);
    try {
      const r = await api.suggestCompanies();
      setSuggestions(r.suggestions);
      if (!r.suggestions.length) toast.info("Sin sugerencias nuevas para tus semillas");
    } catch {
      toast.error("No se pudo buscar sugerencias");
    } finally {
      setBusy(false);
    }
  }

  async function addSuggestion(s: CompanySuggestion) {
    try {
      const r = await api.addCompany({ company: s.company, ats: s.ats, token: s.token });
      toast.success(r.added ? `Añadida ${s.company}` : "Ya estaba en tu lista");
      setSuggestions((prev) => prev.filter((x) => x.company !== s.company));
    } catch {
      toast.error("No se pudo añadir");
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const r = await api.importConnections(file);
      toast.success(`Importadas ${r.imported} conexiones`);
    } catch {
      toast.error("No se pudo importar el CSV");
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div>
      <section>
        <div className="mb-1 text-sm font-semibold">Salud del sistema</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Fuentes, base de datos y garantías de coste $0 (equivale a{" "}
          <code className="font-mono">atlas status</code> + <code className="font-mono">doctor</code>).
        </div>
        {health ? (
          <div className="space-y-2 text-xs">
            <div className="flex flex-wrap gap-2">
              <Badge variant={health.db.ok ? "secondary" : "destructive"}>
                DB {health.db.ok ? "ok" : "error"} · {health.db.jobs} jobs
              </Badge>
              <Badge variant={health.safeguards.api_key_unset ? "secondary" : "destructive"}>
                API key {health.safeguards.api_key_unset ? "sin fijar ✓" : "FIJADA ✗"}
              </Badge>
              <Badge variant="outline">perfil: {health.profile}</Badge>
              <Badge variant="outline">último run: {health.last_run?.slice(0, 19) ?? "nunca"}</Badge>
            </div>
            <ul className="space-y-0.5">
              {health.sources.map((s) => (
                <li key={s.source} className="flex items-center gap-2">
                  <span className={s.ok ? "text-emerald-600" : "text-destructive"}>
                    {s.ok ? "✓" : "✗"}
                  </span>
                  <span className="font-mono">{s.source}</span>
                  <span className="text-muted-foreground">
                    {s.count} · {(s.run_at ?? "").slice(0, 19)}
                    {s.error ? ` · ${s.error.slice(0, 40)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
            <Button variant="ghost" size="sm" onClick={refreshHealth}>
              Refrescar
            </Button>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">Cargando…</div>
        )}
      </section>

      <Separator className="my-2" />

      <section>
        <div className="mb-1 text-sm font-semibold">Añadir empresa por URL</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Pega la URL de carreras; Atlas detecta el ATS (Greenhouse/Lever/Ashby/…) y la añade a{" "}
          <code className="font-mono">companies.yaml</code>.
        </div>
        <div className="flex gap-2">
          <Input
            className="flex-1 font-mono text-xs"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://boards.greenhouse.io/acme"
          />
          <Button variant="secondary" disabled={busy} onClick={resolveUrl}>
            Detectar
          </Button>
        </div>
        {resolved?.resolved ? (
          <div className="mt-2 flex items-center justify-between rounded-md border p-2 text-xs">
            <div>
              <span className="font-semibold">{resolved.company}</span>{" "}
              <Badge variant="outline">{resolved.ats}</Badge>{" "}
              <span className="text-muted-foreground">
                {resolved.preview_jobs_count} posiciones
              </span>
            </div>
            <Button
              size="sm"
              disabled={resolved.already_configured}
              onClick={addResolved}
            >
              {resolved.already_configured ? "Ya está" : "Añadir"}
            </Button>
          </div>
        ) : null}
        <div className="mt-2">
          <Button variant="ghost" size="sm" disabled={busy} onClick={runSuggest}>
            Sugerir empresas de mis semillas
          </Button>
          {suggestions.map((s) => (
            <div
              key={s.company}
              className="mt-1 flex items-center justify-between rounded-md border p-2 text-xs"
            >
              <div>
                <span className="font-semibold">{s.company}</span>{" "}
                <Badge variant="outline">{s.ats}</Badge>{" "}
                <span className="text-muted-foreground">
                  {s.matching_titles.slice(0, 2).join(", ")}
                </span>
              </div>
              <Button size="sm" onClick={() => addSuggestion(s)}>
                Añadir
              </Button>
            </div>
          ))}
        </div>
      </section>

      <Separator className="my-2" />

      <section>
        <div className="mb-1 text-sm font-semibold">Importar conexiones de LinkedIn</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Sube tu <code className="font-mono">Connections.csv</code> (Ajustes → Privacidad de datos
          → Obtén una copia) para detectar referidos en tus empresas objetivo.
        </div>
        <Input type="file" accept=".csv" onChange={onFile} />
      </section>
    </div>
  );
}
```

- [ ] GREEN — `dashboard/frontend/src/components/SettingsModal.tsx`: montar el panel. Localizar el punto de inserción:

```bash
rtk grep -n "saveColumns\|</Dialog>" dashboard/frontend/src/components/SettingsModal.tsx
```
Añadir el import junto a los demás (línea ~4, tras `import { api, type CsvColumn } from "../api";`):

```tsx
import { SettingsOps } from "./SettingsOps";
```
E insertar, justo ANTES del cierre `</DialogContent>` (tras la última `</section>` de columnas), un separador y el panel:

```tsx
        <Separator className="my-2" />

        <SettingsOps />
```

- [ ] GREEN — crear `dashboard/frontend/src/components/SettingsOps.test.tsx` (Vitest, patrón `vi.mock("../api")` como los tests existentes):

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const { toast, api } = vi.hoisted(() => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  api: {
    systemHealth: vi.fn(() =>
      Promise.resolve({
        profile: "owner",
        db: { path: "/tmp/atlas.db", ok: true, jobs: 42 },
        counts: { applied: 3 },
        last_run: "2026-07-04T10:00:00+00:00",
        last_success: "2026-07-04T10:00:00+00:00",
        sources: [{ source: "greenhouse", ok: true, count: 12, run_at: "2026-07-04T10:00:00+00:00", error: null }],
        safeguards: { api_key_unset: true, base_url_default: true },
      }),
    ),
    resolveCompany: vi.fn(() =>
      Promise.resolve({
        resolved: true, company: "Acme Robotics", ats: "greenhouse", token: "acmerobotics",
        preview_jobs_count: 3, already_configured: false,
      }),
    ),
    addCompany: vi.fn(() => Promise.resolve({ ok: true, added: true })),
    suggestCompanies: vi.fn(() => Promise.resolve({ suggestions: [] })),
    importConnections: vi.fn(() => Promise.resolve({ ok: true, imported: 2 })),
  },
}));
vi.mock("sonner", () => ({ toast }));
vi.mock("../api", () => ({ api }));

import { SettingsOps } from "./SettingsOps";

describe("SettingsOps", () => {
  it("renders system health from /api/system/health", async () => {
    render(<SettingsOps />);
    expect(await screen.findByText(/42 jobs/)).toBeInTheDocument();
    expect(screen.getByText(/greenhouse/)).toBeInTheDocument();
    expect(screen.getByText(/sin fijar/)).toBeInTheDocument();
  });

  it("resolves a careers URL and adds the company", async () => {
    const user = userEvent.setup();
    render(<SettingsOps />);
    await user.type(
      screen.getByPlaceholderText(/boards.greenhouse.io/),
      "https://boards.greenhouse.io/acmerobotics",
    );
    await user.click(screen.getByRole("button", { name: "Detectar" }));
    expect(await screen.findByText("Acme Robotics")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Añadir" }));
    await waitFor(() => expect(api.addCompany).toHaveBeenCalledWith({
      company: "Acme Robotics", ats: "greenhouse", token: "acmerobotics",
    }));
    expect(toast.success).toHaveBeenCalled();
  });

  it("uploads a Connections.csv via importConnections", async () => {
    const user = userEvent.setup();
    render(<SettingsOps />);
    const file = new File(["First Name,Last Name,Company\nJane,Doe,Acme\n"], "Connections.csv", {
      type: "text/csv",
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);
    await waitFor(() => expect(api.importConnections).toHaveBeenCalledWith(file));
    expect(toast.success).toHaveBeenCalledWith("Importadas 2 conexiones");
  });
});
```

- [ ] Verificar frontend (test + typecheck + build):

```bash
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend run build
```
Esperado: los 3 tests de `SettingsOps.test.tsx` verdes, sin errores de tipos, build OK.

- [ ] Commit:

```bash
rtk git add pyproject.toml dashboard/backend/main.py dashboard/frontend/src/api.ts dashboard/frontend/src/components/SettingsOps.tsx dashboard/frontend/src/components/SettingsModal.tsx dashboard/frontend/src/components/SettingsOps.test.tsx tests/test_f3_backend_api.py
rtk git commit -m "feat(f3): exponer CLI-only en la web — resolve/add company, import connections, salud del sistema

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 13 — Gate final F3: suite completa, build, check.sh, verificación de features y cierre de rama

**Files:** (ninguno nuevo — verificación + cierre)

Este task NO escribe código de features. Es la puerta `verification-before-completion` de la fase: correr todo verde, verificar manualmente que las features F3 funcionan en la app real (preview tools), confirmar que ningún dato personal quedó commiteado (repo público), y cerrar con `finishing-a-development-branch` (PR, sin auto-merge).

**Steps:**

- [ ] Suite backend completa (todos los tests, no solo F3):

```bash
rtk uv run --group dev pytest
```
Esperado: todo verde. Referencia: 117 tests previos + los ~70 nuevos de F3 (Tasks 1-12). Cero fallos, cero errores. Si algo falla, `superpowers:systematic-debugging` antes de continuar — NUNCA declarar la fase completa con rojos.

- [ ] Frontend: tests + typecheck + build:

```bash
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend run build
```
Esperado: toda la suite Vitest verde (incluidos los nuevos: `SettingsOps.test.tsx` y los que F3 añadió a views/componentes), `tsc --noEmit` sin errores, `vite build` sin warnings de import roto.

- [ ] Gate consolidado de ambos stacks:

```bash
./scripts/check.sh
```
Esperado: termina con `✓ All checks passed.` (uv sync + ruff check + ruff format --check + pytest + frontend lint/format/typecheck/test). Este es el gate oficial de la fase (spec §8).

- [ ] QA manual con preview tools (verification-before-completion, spec §8). Levantar la app y comprobar cada feature F3 de punta a punta:

```bash
rtk uv run uvicorn dashboard.backend.main:app --port 8787 &
npm --prefix dashboard/frontend run dev
```
Checklist funcional (marcar solo tras VERLO funcionar en el navegador, no por inferencia):
  - [ ] `/followups`: al marcar un job Applied aparece 1 toque en waiting; un toque vencido cae en URGENT/OVERDUE con draft sin "just checking in"; "marcar enviado" (con confirmación) siembra el siguiente toque; la cadencia agotada muestra el job en COLD.
  - [ ] `/analytics`: funnel real con conversiones, score floor, conversión por fuente/ATS/remote/role-term, tiempos de respuesta; el panel de recomendaciones aplica una rec de un click (sube threshold / bloquea empresa) y persiste en criteria.md.
  - [ ] `/stories`: CRUD de historias STAR+R; el matcher rankea y formatea ante una pregunta/JD.
  - [ ] Card + detalle: chips de knock-out (visa/años/idioma/grado/clearance) visibles; el detalle muestra el desglose del score (deltas por factor).
  - [ ] `/settings` (SettingsOps): salud del sistema (fuentes, DB, safeguards $0); resolver una URL de carreras real y añadir la empresa; subir un `Connections.csv` de prueba (datos ficticios) y ver el conteo importado.

- [ ] Confirmar que NINGÚN dato personal quedó commiteado (repo PÚBLICO — constraint global 5). Revisar el diff de la rama y el estado:

```bash
rtk git status
rtk git log --oneline origin/master..HEAD
rtk grep -rn "aimm1999\|Anthony\|Manotoa" config/ tests/ engine/ dashboard/ || echo "sin datos personales en el código"
```
Esperado: los archivos tocados son solo los de Tasks 1-12 (código + tests + seeds ficticios); los writers de perfil (`criteria.md`, `companies.yaml`, `discovery_seeds.yaml`, `atlas.db`, `Connections.csv`) NO aparecen (están gitignorados). Fixtures y ejemplos usan "Acme"/"Jane Doe"/"Ghost Corp". Si aparece cualquier ruta de perfil o dato real, PARAR y sacarla del commit antes de cerrar.

- [ ] Verificar que los ejemplos commiteados (`.example`, seeds) siguen siendo ficticios y que los `.gitignore` cubren las rutas de perfil:

```bash
rtk git check-ignore config/companies.yaml config/criteria.md config/discovery_seeds.yaml data/atlas.db || echo "revisar .gitignore"
```
Esperado: cada ruta de perfil listada como ignorada (o inexistente en el árbol commiteado).

- [ ] Cierre de rama con el skill de Superpowers (NO auto-merge — la decisión de merge es del dueño; repo personal con master protegido → PR por fase, spec §8 y CLAUDE.md):

Invocar `superpowers:finishing-a-development-branch`. Verifica tests (ya verdes arriba), presenta el menú merge/PR/keep/descartar y, para esta fase, **crear PR** (master protegido con PR + 1 review). El cuerpo del PR resume las features F3 (follow-ups v2, analytics + loop de aprendizaje, story bank STAR+R, knock-out pre-scan, machine summary, reverse ATS discovery, exposición web de CLI-only) y enlaza el spec §6 y este plan. Terminar el body del PR con:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] Tras abrir el PR, verificar el estado de CI (sin merge):

```bash
rtk gh pr checks
```
Esperado: los checks del PR en verde. El merge queda a decisión del dueño — NO mergear por iniciativa propia.
