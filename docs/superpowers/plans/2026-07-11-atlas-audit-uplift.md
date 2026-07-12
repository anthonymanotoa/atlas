# Atlas Audit Uplift — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sanear datos/estado del perfil real, cerrar los gaps de confiabilidad y features vs los repos líderes (career-ops, ai-job-search, ApplyPilot), y cerrar con una validación end-to-end real aplicando a vacantes con el perfil `owner`.

**Architecture:** Regla invariante del repo: lo determinista vive en `engine/` (Python puro, sin IA); lo que requiere criterio va como **intent** de la cola `engine/intents.py` que drena el brain de Cowork (patrón $0). El dashboard (FastAPI + React/Meridian) solo lee de la API. Spec: `docs/superpowers/specs/2026-07-11-atlas-audit-uplift-design.md`.

**Tech Stack:** Python 3.12 (uv), typer + rich (CLI), SQLite (`engine/db/schema.sql` + `DB` en `engine/db/models.py`), FastAPI (`dashboard/backend/main.py`), React+Vite+Tailwind (`dashboard/frontend/`), pytest.

## Global Constraints

- **$0 garantizado:** nada de `claude -p` / Agent SDK / `ANTHROPIC_API_KEY`. IA solo vía intents + brain Cowork.
- **Atlas nunca envía nada.** Drafts y pre-fill solamente.
- **Anti-fabricación:** ningún generador inventa hechos; todo claim sale de `master_cv.yaml`.
- **Repo público:** cero datos personales en código, tests, fixtures o seeds. Lo personal vive solo en `profiles/` (gitignored).
- **Tests SIEMPRE via RTK:** `rtk uv run --group dev pytest` (nunca `pytest` a secas). Suite actual: 514 verdes — debe seguir verde en cada commit.
- **UI:** cualquier cambio visual usa la skill `atlas-design-system` (tokens v2, primitivas compartidas). Copy de UI en español.
- **Git:** nunca `git add .` — añadir archivos por nombre. Commits frecuentes, uno por task como mínimo.
- **Worktree:** ejecutar en un worktree aislado (este plan nació en `local-project-setup-303f5f`). Para comandos con el perfil real: `export ATLAS_PROFILES_DIR="/Users/anthonymanotoa/dev/personal/atlas/profiles"`.
- **Arquitectura:** ante dudas de "quién llama a qué", correr `cd /Users/anthonymanotoa/dev/personal/atlas && graphify query "<pregunta>"`.

---

## Fase F0 — Saneamiento de datos y estado

### Task 1: Detector determinista de CV plantilla (`engine/cv/placeholder.py`)

**Files:**
- Create: `engine/cv/placeholder.py`
- Test: `tests/test_cv_placeholder.py`

**Interfaces:**
- Produces: `find_placeholders(cv: dict) -> list[str]` (lista de hallazgos legibles, vacía = CV real) y `is_template_cv(cv: dict) -> bool`. Los consumen Tasks 2, 3, 4 y 12.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cv_placeholder.py
from engine.cv.placeholder import find_placeholders, is_template_cv


def test_template_cv_is_flagged():
    cv = {
        "basics": {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "linkedin": "linkedin.com/in/example",
        }
    }
    findings = find_placeholders(cv)
    assert any("Ada Lovelace" in f for f in findings)
    assert any("example.com" in f for f in findings)
    assert is_template_cv(cv) is True


def test_real_cv_passes():
    cv = {
        "basics": {
            "name": "Jane Roe",
            "email": "jane@gmail.com",
            "linkedin": "linkedin.com/in/janeroe",
        }
    }
    assert find_placeholders(cv) == []
    assert is_template_cv(cv) is False


def test_empty_or_missing_basics_is_flagged():
    assert is_template_cv({}) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_cv_placeholder.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.cv.placeholder`

- [ ] **Step 3: Write the implementation**

```python
# engine/cv/placeholder.py
"""Deterministic template-identity detector for master_cv.yaml.

The seed master CV ships with the "Ada Lovelace" placeholder identity. Anything
generated from it (tailored CVs, outreach, portfolio) is unusable. This module is
the single source of truth for "is this CV still the template?".
"""

from __future__ import annotations

PLACEHOLDER_NAMES = {"ada lovelace"}
PLACEHOLDER_DOMAINS = ("example.com", "example.org")
PLACEHOLDER_URL_FRAGMENTS = ("linkedin.com/in/example", "github.com/example")


def find_placeholders(cv: dict) -> list[str]:
    findings: list[str] = []
    basics = cv.get("basics") or {}
    name = (basics.get("name") or "").strip()
    if not name:
        findings.append("basics.name vacío")
    elif name.lower() in PLACEHOLDER_NAMES:
        findings.append(f"basics.name es la plantilla: {name!r} (Ada Lovelace)")
    email = (basics.get("email") or "").lower()
    if any(d in email for d in PLACEHOLDER_DOMAINS):
        findings.append(f"basics.email usa dominio de ejemplo: {email!r} (example.com)")
    for key in ("linkedin", "github", "website"):
        val = (basics.get(key) or "").lower()
        if any(frag in val for frag in PLACEHOLDER_URL_FRAGMENTS) or any(
            d in val for d in PLACEHOLDER_DOMAINS
        ):
            findings.append(f"basics.{key} es URL de ejemplo: {val!r}")
    return findings


def is_template_cv(cv: dict) -> bool:
    return bool(find_placeholders(cv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_cv_placeholder.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
rtk git add engine/cv/placeholder.py tests/test_cv_placeholder.py
rtk git commit -m "feat(cv): deterministic template-identity detector"
```

### Task 2: Señalización de CV plantilla en `doctor`, `tailor`, `prep` y `portfolio generate`

**Files:**
- Modify: `engine/cli.py` (comandos `doctor`, `tailor`, `prep`, y `portfolio generate` en `portfolio_app`)
- Test: `tests/test_cv_placeholder_cli.py`

**Interfaces:**
- Consumes: `engine.cv.placeholder.find_placeholders`.
- Produces: helper `_warn_if_template_cv(console) -> bool` en `engine/cli.py` reutilizado por los 4 comandos (carga el master CV activo con el mismo loader que ya usa `tailor` — buscar `load_master_cv`/equivalente en `engine/cv/tailor.py` y reutilizarlo).

- [ ] **Step 1: Write the failing test** (usar el runner de typer que ya usan otros tests de CLI; ver patrón en `tests/test_engine.py`)

```python
# tests/test_cv_placeholder_cli.py
from typer.testing import CliRunner

from engine.cli import app

runner = CliRunner()


def test_doctor_flags_template_cv(tmp_profile):
    # tmp_profile: fixture existente en tests/conftest.py que arma un perfil
    # aislado con el master CV plantilla (verificar nombre exacto en conftest;
    # si no existe, crear una fixture equivalente con monkeypatch de
    # engine.paths hacia un tmp_path con el master_cv.yaml.example copiado).
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "plantilla" in result.output.lower() or "Ada Lovelace" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --group dev pytest tests/test_cv_placeholder_cli.py -v`
Expected: FAIL — doctor no menciona la plantilla

- [ ] **Step 3: Implement.** En `engine/cli.py`:

```python
def _warn_if_template_cv(console: Console) -> bool:
    """Imprime advertencia prominente si el master CV activo es la plantilla."""
    from engine.cv.placeholder import find_placeholders
    from engine.cv.tailor import load_master_cv  # reutilizar el loader real

    try:
        cv = load_master_cv()
    except Exception:
        return False
    findings = find_placeholders(cv)
    if findings:
        console.print(
            "[bold red]⚠ Tu master CV sigue siendo la PLANTILLA[/bold red] — "
            "nada de lo generado es enviable. Corre [bold]atlas cv promote[/bold] "
            "tras completar profile/master_cv.draft.yaml."
        )
        for f in findings:
            console.print(f"  [red]•[/red] {f}")
        return True
    return False
```

En `doctor()`: llamar `_warn_if_template_cv(console)` y sumar una línea roja al reporte. En `tailor`, `prep` y `portfolio generate`: llamarlo al inicio (solo advierte; NO bloquea).

- [ ] **Step 4: Run tests**

Run: `rtk uv run --group dev pytest tests/test_cv_placeholder_cli.py tests/test_engine.py -v`
Expected: PASS (y la suite previa intacta)

- [ ] **Step 5: Commit**

```bash
rtk git add engine/cli.py tests/test_cv_placeholder_cli.py
rtk git commit -m "feat(cli): warn loudly when master CV is still the template"
```

### Task 3: Banner de CV plantilla en el dashboard

**Files:**
- Modify: `dashboard/backend/main.py` (endpoint de status/perfil que consume el frontend — localizar el que alimenta el AppShell, p. ej. `/api/status` o `/api/profile`)
- Modify: `dashboard/frontend/src/components/AppShell.tsx` (o el componente de banners existente — el heartbeat ya pinta "estuve caído N días"; colocar este banner con el mismo patrón)
- Test: `tests/test_backend_api.py` (añadir caso) + test frontend si `tests/frontend` lo cubre (seguir patrón de `plans/016-frontend-tests.md`)

**Interfaces:**
- Consumes: `find_placeholders`.
- Produces: campo JSON `cv_template_findings: list[str]` en el endpoint de status; el frontend muestra banner rojo persistente cuando `length > 0`.

- [ ] **Step 1: Test backend que falla** (añadir a `tests/test_backend_api.py`, patrón TestClient existente): el endpoint de status incluye `cv_template_findings` y es lista no vacía con el perfil plantilla.
- [ ] **Step 2: Run** `rtk uv run --group dev pytest tests/test_backend_api.py -k template -v` → FAIL.
- [ ] **Step 3: Backend:** en el handler de status, añadir:

```python
from engine.cv.placeholder import find_placeholders
from engine.cv.tailor import load_master_cv

try:
    payload["cv_template_findings"] = find_placeholders(load_master_cv())
except Exception:
    payload["cv_template_findings"] = []
```

- [ ] **Step 4: Frontend:** banner en AppShell (mismo slot que el banner de heartbeat): fondo `--destructive`, texto: "Tu CV master es la plantilla — nada de lo generado es enviable. Completa tu CV real y corre `atlas cv promote`." Aplicar skill `atlas-design-system` antes de tocar el TSX.
- [ ] **Step 5: Run** suite backend + build frontend (`npm --prefix dashboard/frontend run build`) → verde.
- [ ] **Step 6: Commit** `feat(dashboard): persistent banner when master CV is the template`.

### Task 4: `atlas cv promote` (draft → master con validación y backup)

**Files:**
- Create: `engine/cv/promote.py`
- Modify: `engine/cli.py` (sub-app `cv` existente — ahí vive `cv dump`)
- Test: `tests/test_cv_promote.py`

**Interfaces:**
- Consumes: `find_placeholders`.
- Produces: `promote_draft(profile_dir: Path) -> Path` — valida `profile/master_cv.draft.yaml`, hace backup `profile/master_cv.backup-<UTCts>.yaml` del master actual, escribe el draft validado como `profile/master_cv.yaml` y devuelve la ruta final. Lanza `PromoteError(str)` con mensaje accionable si falla la validación.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cv_promote.py
from pathlib import Path

import pytest
import yaml

from engine.cv.promote import PromoteError, promote_draft

REAL = {
    "basics": {"name": "Jane Roe", "email": "jane@gmail.com", "linkedin": "linkedin.com/in/janeroe"},
    "experience": [{"company": "Acme", "title": "Data Analyst", "start": "2022-01"}],
}


def _profile(tmp_path: Path, draft: dict | None) -> Path:
    prof = tmp_path / "profile"
    prof.mkdir()
    (prof / "master_cv.yaml").write_text(
        yaml.safe_dump({"basics": {"name": "Ada Lovelace", "email": "ada@example.com"}})
    )
    if draft is not None:
        (prof / "master_cv.draft.yaml").write_text(yaml.safe_dump(draft))
    return tmp_path


def test_promote_happy_path(tmp_path):
    root = _profile(tmp_path, REAL)
    out = promote_draft(root)
    promoted = yaml.safe_load(out.read_text())
    assert promoted["basics"]["name"] == "Jane Roe"
    backups = list((root / "profile").glob("master_cv.backup-*.yaml"))
    assert len(backups) == 1


def test_promote_rejects_placeholder_draft(tmp_path):
    root = _profile(tmp_path, {"basics": {"name": "Ada Lovelace", "email": "a@example.com"}})
    with pytest.raises(PromoteError, match="plantilla"):
        promote_draft(root)


def test_promote_rejects_source_text_residue(tmp_path):
    draft = dict(REAL) | {"_source_text": "raw pdf text"}
    root = _profile(tmp_path, draft)
    with pytest.raises(PromoteError, match="_source_text"):
        promote_draft(root)


def test_promote_requires_draft(tmp_path):
    root = _profile(tmp_path, None)
    with pytest.raises(PromoteError, match="draft"):
        promote_draft(root)
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implement**

```python
# engine/cv/promote.py
"""Promote profile/master_cv.draft.yaml → profile/master_cv.yaml (validated, with backup)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from engine.cv.placeholder import find_placeholders


class PromoteError(RuntimeError):
    pass


REQUIRED_BASICS = ("name", "email")


def promote_draft(profile_root: Path) -> Path:
    prof = profile_root / "profile"
    draft_path = prof / "master_cv.draft.yaml"
    master_path = prof / "master_cv.yaml"
    if not draft_path.exists():
        raise PromoteError(f"No existe el draft: {draft_path}")
    draft = yaml.safe_load(draft_path.read_text()) or {}
    if "_source_text" in draft:
        raise PromoteError(
            "El draft aún contiene _source_text (texto crudo del PDF sin mapear). "
            "Mapea los campos y borra _source_text antes de promover."
        )
    basics = draft.get("basics") or {}
    missing = [k for k in REQUIRED_BASICS if not (basics.get(k) or "").strip()]
    if missing:
        raise PromoteError(f"Faltan campos obligatorios en basics: {', '.join(missing)}")
    if not draft.get("experience"):
        raise PromoteError("El draft no tiene experiencia (experience) — mapéala primero.")
    findings = find_placeholders(draft)
    if findings:
        raise PromoteError("El draft sigue con identidad de plantilla: " + "; ".join(findings))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if master_path.exists():
        master_path.rename(prof / f"master_cv.backup-{ts}.yaml")
    master_path.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True))
    return master_path
```

- [ ] **Step 4: CLI:** en `engine/cli.py`, sub-app `cv`:

```python
@cv_app.command("promote")
def cv_promote() -> None:
    """Valida el draft y lo promueve a master (con backup)."""
    from engine.cv.promote import PromoteError, promote_draft
    from engine.paths import active_profile_root  # usar el helper real de paths; si no
    # existe con ese nombre, usar el que resuelve el dir del perfil activo (ver _apply()).

    try:
        out = promote_draft(active_profile_root())
    except PromoteError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓ Master CV promovido:[/green] {out}")
```

- [ ] **Step 5: Run** `rtk uv run --group dev pytest tests/test_cv_promote.py -v` → PASS; suite completa verde.
- [ ] **Step 6: Commit** `feat(cv): atlas cv promote — validated draft→master promotion with backup`.

### Task 5: `atlas brain --dry-run`

**Files:**
- Modify: `brain/run_brain.py` + `engine/cli.py` (comando `brain`)
- Test: `tests/test_brain_dry_run.py`

**Interfaces:**
- Produces: flag `--dry-run` que recorre el pipeline completo (discover→score→shortlist→prep candidates→intents) **sin escrituras** (ni DB ni outbox) y reporta un resumen JSON de qué haría (`{"would_discover": bool, "would_score": N, "would_prep": [...], "pending_intents": N}`).

- [ ] **Step 1: Test que falla:** invocar el runner con `dry_run=True` sobre una DB temporal sembrada con 2 jobs `scored`; afirmar que devuelve el resumen y que la DB no cambió (mismos counts, sin eventos nuevos).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement:** threading del parámetro `dry_run: bool = False` por `run_brain.py` (cada etapa consulta y reporta en vez de ejecutar; reutilizar los mismos selectores de candidatos que usa la corrida real). En CLI: `--dry-run` → imprime el resumen con rich y sale 0.
- [ ] **Step 4: Run** tests → PASS.
- [ ] **Step 5: Commit** `feat(brain): --dry-run pipeline preview without writes`.

### Task 6: Intents atascados — edad visible + `requeue`

**Files:**
- Modify: `engine/intents.py`, `engine/cli.py` (sub-app `intents`), `dashboard/backend/main.py` (endpoint que lista intents para BrainTasksPanel)
- Test: `tests/test_brain_intents.py` (extender)

**Interfaces:**
- Produces: `stale_intents(db: DB, max_age_hours: float = 48.0) -> list[dict]` en `engine/intents.py`; comando `atlas intents requeue <id>` (error→pending, running colgado→pending con nota); campo `is_stale: bool` + `age_hours: float` en los dicts de `list_intents`.

- [ ] **Step 1: Tests que fallan** (extender `tests/test_brain_intents.py`): (a) un intent pending con `created_at` hace 3 días aparece en `stale_intents` y trae `is_stale=True` en `list_intents`; (b) `requeue` sobre un intent `error` lo deja `pending` y limpia `error`; (c) `requeue` sobre `done` lanza error.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement:** en `_row_to_dict`, calcular `age_hours` desde `created_at` (usar el parser aware-UTC compartido de plan 029 — `engine/utils` o donde viva `parse_utc`) y `is_stale = status == "pending" and age_hours > 48`. `stale_intents` filtra eso. `requeue(db, intent_id)` valida estados permitidos `("error", "running")` con `_require` y hace UPDATE a pending. CLI: comando `requeue` + columna EDAD en `intents list` (rojo si stale). Backend: pasar los campos nuevos tal cual (el panel ya lista intents).
- [ ] **Step 4: Run** → PASS. `atlas status` debe además avisar "N intents atascados" — añadirlo al comando `status` leyendo `stale_intents`.
- [ ] **Step 5: Commit** `feat(intents): stale detection + requeue command`.

### Task 7: Fuentes demo etiquetadas y excluidas del perfil real

**Files:**
- Modify: `config/sources.yaml`, `config/companies.yaml` (y sus equivalentes en `config/seeds/*/` si duplican), `engine/discovery/runner.py`
- Test: `tests/test_demo_sources.py`

**Interfaces:**
- Produces: entradas demo marcadas `demo: true`; `runner.discover` las salta salvo `include_demo: true` en la config del perfil, registrando en el summary `{"skipped_demo": [names]}`.

- [ ] **Step 1: Test que falla:** config con una company `{name: DemoCo, demo: true}` → `discover` no la consulta y el summary lista `skipped_demo == ["DemoCo"]`; con `include_demo: true` sí la incluye.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement:** en el loader/iterador de companies y boards del runner, filtrar `entry.get("demo")` cuando `cfg.get("include_demo") is not True`. Marcar en los YAML del repo: el Lever demo board y las seed companies (Airbnb, GitLab, Ashby, Ramp) con `demo: true` y un comentario de por qué.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(discovery): demo-tagged sources excluded from real profiles`.

---

## Fase F1 — Confiabilidad del pipeline

### Task 8: Salud de fuentes honesta (ok / ok-vacío / sin-configurar / error)

**Files:**
- Create: `engine/discovery/health.py`
- Modify: `engine/cli.py` (comando `status`), `dashboard/backend/main.py` (endpoint de salud de fuentes), fuente Adzuna (`engine/discovery/apis/adzuna.py`) para reportar "unconfigured" si faltan credenciales
- Test: `tests/test_source_health_states.py`

**Interfaces:**
- Consumes: tabla `source_health` (cols: `source, run_at, ok, count, error`).
- Produces: `classify_sources(db: DB, empty_streak: int = 3) -> list[dict]` con `{"source", "state", "hint", "last_run", "last_count"}`, estados: `"ok" | "ok_empty" | "unconfigured" | "error"`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_source_health_states.py
from engine.db.models import DB
from engine.discovery.health import classify_sources


def _seed(db, source, runs):  # runs: list[(ok, count, error)]
    for i, (ok, count, error) in enumerate(runs):
        db.conn.execute(
            "INSERT INTO source_health (source, run_at, ok, count, error) VALUES (?,?,?,?,?)",
            (source, f"2026-07-{8 + i:02d}T08:00:00Z", ok, count, error),
        )
    db.conn.commit()


def test_ok_empty_streak_is_flagged():
    db = DB(":memory:"); db.init_schema()
    _seed(db, "adzuna", [(1, 0, None)] * 3)
    (row,) = [r for r in classify_sources(db) if r["source"] == "adzuna"]
    assert row["state"] == "ok_empty"
    assert "credencial" in row["hint"].lower() or "0 resultados" in row["hint"]


def test_unconfigured_error_marker():
    db = DB(":memory:"); db.init_schema()
    _seed(db, "adzuna", [(0, 0, "unconfigured: missing ADZUNA_APP_ID")])
    (row,) = [r for r in classify_sources(db) if r["source"] == "adzuna"]
    assert row["state"] == "unconfigured"


def test_ok_with_data():
    db = DB(":memory:"); db.init_schema()
    _seed(db, "greenhouse", [(1, 12, None)] * 3)
    (row,) = [r for r in classify_sources(db) if r["source"] == "greenhouse"]
    assert row["state"] == "ok"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement:** `classify_sources` agrupa las últimas `empty_streak` corridas por fuente: error reciente con prefijo `unconfigured:` → `unconfigured`; todas ok con `count==0` → `ok_empty` con hint; algún error → `error`; resto → `ok`. En Adzuna: si faltan `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`, registrar `ok=0, error="unconfigured: missing ADZUNA_APP_ID"` **sin** intentar la llamada. `status` pinta estado + hint por fuente (amarillo `ok_empty`, gris `unconfigured`); backend expone lo mismo.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(discovery): honest source-health states (ok/ok_empty/unconfigured/error)`.

### Task 9: Dedup de variantes en la shortlist

**Files:**
- Create: `engine/scoring/dedupe.py`
- Modify: `engine/cli.py` (comando `top`), `dashboard/backend/main.py` (listado de jobs shortlisted)
- Test: `tests/test_shortlist_dedupe.py`

**Interfaces:**
- Produces: `collapse_variants(jobs: list[dict]) -> list[dict]` — agrupa por `(company normalizada, título core)` (reutilizar la normalización de `engine/reposts.py`, que ya computa "same company+core-title"); el canónico (mejor fit, más reciente) gana y lleva `variant_count: int` y `variant_ids: list[str]`.

- [ ] **Step 1: Tests que fallan:** 5 jobs de "CVS Health" con títulos casi idénticos y fits 88-92 → `collapse_variants` devuelve 1 con `variant_count == 5`; dos empresas distintas no se colapsan; el canónico es el de mayor fit.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** usando la misma clave de agrupación que `engine/reposts.py` (importar su helper de título core; si es privado, moverlo a función pública `core_title(title) -> str` con test propio).
- [ ] **Step 4: Integrar:** `top` colapsa por defecto y muestra "×N variantes" (flag `--all` para verlas); el endpoint de shortlist devuelve `variant_count`/`variant_ids` y el Board/NeedsAction muestran la píldora "×N" (skill `atlas-design-system`).
- [ ] **Step 5: Run** suite → PASS. **Commit** `feat(scoring): collapse near-identical shortlist variants`.

### Task 10: Legibilidad fit vs CV-match + prioridad blended

**Files:**
- Modify: `engine/scoring/fit.py` (o módulo nuevo `engine/scoring/priority.py`), `engine/cli.py` (`top`), dashboard job list/detail
- Test: `tests/test_priority.py`

**Interfaces:**
- Produces: `priority(fit_score: float | None, match_score: int | None) -> float` — `fit*0.7 + match*0.3` si hay match, si no `fit`; redondeado a 1 decimal. `top` ordena por priority y muestra tres columnas etiquetadas: `PRIORIDAD`, `FIT (criterios)`, `CV MATCH (keywords)`.

- [ ] **Step 1: Tests que fallan:** `priority(100, 20) == 76.0`; `priority(80, None) == 80.0`; orden de `top` usa priority.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (función pura + wiring en `top` y en el endpoint del dashboard; leyenda de una línea bajo la tabla de `top`: "fit = encaje con tus criterios; CV match = cobertura de keywords de la vacante en tu CV").
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat(scoring): blended priority + labeled fit/match display`.

### Task 11: Liveness activado y visible

**Files:**
- Modify: `config/sources.yaml` (bloque `liveness`), `engine/cli.py` (`status`)
- Test: `tests/test_liveness_status.py`

**Interfaces:**
- Consumes: `engine/discovery/liveness.py::sweep_liveness` (ya existe, gated por `liveness.enabled`).
- Produces: `liveness.enabled: true` por defecto en la config del repo (y seeds); `status` muestra "Liveness: último sweep <fecha>, N expirados activos".

- [ ] **Step 1: Test que falla:** con un job `expired` en DB, `status` menciona el conteo de expirados y la fecha del último sweep (sembrar `liveness_checked_at`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (query de conteo + max(liveness_checked_at) en `status`; flip del default en YAML con comentario).
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat(discovery): liveness on by default + visible in status`.

---

## Fase F2 — Calidad de output (drafter-reviewer)

### Task 12: Reporte de revisión determinista por CV generado (`review.md`)

**Files:**
- Create: `engine/cv/review_report.py`
- Modify: `engine/cli.py` (`tailor` y `prep` lo invocan tras generar DOCX/PDF)
- Test: `tests/test_review_report.py`

**Interfaces:**
- Consumes: `engine/cv/parse_check.py::extract_text/check`, `find_placeholders`, keyword coverage existente de `engine/cv/keywords.py`, master CV.
- Produces: `build_review(docx_path: Path, pdf_path: Path, master_cv: dict, job: dict, coverage: dict) -> ReviewResult` con `ReviewResult(passed: bool, checks: list[Check], markdown: str)`; `Check(name, ok, detail)`. `tailor`/`prep` escriben `review.md` junto al package y muestran ✅/⚠ por check.

Checks (todos deterministas): (1) texto extraíble del PDF ≥ 400 chars; (2) bloque de contacto presente (email del master en el texto extraído); (3) sin placeholders (reusar Task 1 sobre el texto); (4) claims-vs-master: toda empresa y título que aparezca en el CV adaptado existe en `master_cv.experience` (lock anti-fabricación verificable); (5) cobertura de keywords (del coverage report existente, con lista de faltantes); (6) páginas dentro del límite (reutilizar el conteo del render si existe; si no, páginas del PDF vía pypdf que ya es dependencia de parse_check — verificar y reutilizar).

- [ ] **Step 1: Tests que fallan:** construir un master mínimo + docx/pdf de fixture (generarlos en el test vía `engine/cv/render.py` con un CV sintético) y validar: pasa el happy path; una empresa inventada en el adaptado dispara el check 4 con `ok=False`; el markdown contiene una línea por check.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `build_review` + integración en `tailor`/`prep` (escribir `review.md` al package dir del job, mismo dir del DOCX/PDF).
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat(cv): deterministic review report (review.md) per tailored CV`.

### Task 13: Revisión con criterio visible (intent `cv_review` existente → UI)

**Files:**
- Modify: `dashboard/backend/main.py` (si el job detail aún no expone `cv_reviews_for`), `dashboard/frontend/src/pages/JobDetailPage.tsx`
- Test: `tests/test_backend_api.py` (extender)

**Interfaces:**
- Consumes: `DB.cv_reviews_for(job_id)` y el intent `cv_review` ya implementado en `engine/intents.py`.
- Produces: sección "Revisión del CV" en el job detail: resultado del `review.md` (Task 12) + la última `cv_review` del brain si existe, con botón "Pedir revisión al brain" que encola el intent (endpoint POST existente de intents; verificar en `main.py` cómo encola BrainTasksPanel y reutilizar).

- [ ] **Step 1: Test backend que falla:** GET del job detail incluye `cv_reviews` (lista) y `review_report` (contenido de review.md si existe).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** backend + UI (skill `atlas-design-system`).
- [ ] **Step 4: Run** + `npm --prefix dashboard/frontend run build` → verde. **Step 5: Commit** `feat(dashboard): surface deterministic + brain CV reviews in job detail`.

---

## Fase F3 — Features nuevas

> Patrón común de las Tasks 14-16 (intents nuevos): añadir el tipo a `INTENT_TYPES`, implementar `_ctx_<type>` y `_write_<type>` en `engine/intents.py`, registrarlos en los dispatchers de `context_for`/`apply_result`, y actualizar `brain/SKILL.md` + `brain/run_brain.py` para que el brain los drene. `plans/028-intents-registry-hygiene.md` define la higiene del registry — sus tests deben seguir verdes (ejecutan que todo tipo tenga ctx+write).

### Task 14: Intent `company_research`

**Files:**
- Modify: `engine/db/schema.sql` (+ migración `_ensure_column`/CREATE en `DB._migrate`), `engine/db/models.py`, `engine/intents.py`, `engine/cli.py` (`prep` adjunta el brief si existe), `dashboard/backend/main.py` + `JobDetailPage.tsx`
- Test: `tests/test_intent_company_research.py`

**Interfaces:**
- Produces: tabla `company_research (id, company_norm TEXT NOT NULL, job_id TEXT, summary TEXT, signals_json TEXT, sources_json TEXT, researched_at TEXT)`; `DB.add_company_research(...) -> int` y `DB.company_research_for(company_norm) -> dict | None`; intent type `company_research` cuyo `_ctx` entrega `{company, job_brief, existing_research}` y cuyo `_write` persiste `{summary: str, signals: list[str], sources: list[str]}` validando tipos.

- [ ] **Step 1: Tests que fallan** (patrón de `tests/test_brain_intents.py`): enqueue → `context_for` trae el brief del job; `apply_result` con un payload válido crea la fila y marca done; payload sin `summary` → error y el intent queda `error`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (schema + models + handlers + registro en dispatchers).
- [ ] **Step 4:** `prep` incluye el brief en `package.md` (sección "Sobre la empresa") si hay research; job detail lo muestra.
- [ ] **Step 5: Run** suite (incluye tests de registry hygiene) → PASS. **Commit** `feat(intents): company_research intent + storage + surfacing`.

### Task 15: Intent `contact_discovery`

**Files:**
- Modify: `engine/intents.py`, `engine/cli.py`, `dashboard/backend/main.py` + `JobDetailPage.tsx`
- Test: `tests/test_intent_contact_discovery.py`

**Interfaces:**
- Consumes: `DB.add_contact(...)` y `DB.contacts_for_company(company_norm)` (existen); tabla `messages` via `DB.add_message` para el draft.
- Produces: intent type `contact_discovery`: `_ctx` entrega `{company, role_title, job_brief, existing_contacts}`; `_write` acepta `{contacts: [{name, role, profile_url, confidence: "high|medium|low", reasoning}], draft_message: str|None}`, persiste contactos con `source="brain_research"` y el draft como message kind `"referral_or_intro"`. **Nunca envía nada.** Confianza SIEMPRE visible — son candidatos, no verdades.

- [ ] **Step 1: Tests que fallan:** apply_result válido crea N contactos con confidence y un message draft; contacto sin `confidence` → error; `context_for` incluye contactos previos para no duplicar.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4:** job detail muestra "Contactos sugeridos (confianza)" + botón copiar draft; `prep` lista contactos en `package.md`.
- [ ] **Step 5: Run** → PASS. **Commit** `feat(intents): contact_discovery intent (candidates + draft, never sends)`.

### Task 16: Intent `portfolio_research` (búsqueda viva de portfolios de referencia)

**Files:**
- Modify: `engine/intents.py`, `engine/db/models.py` (helpers de `peer_portfolios` si faltan: `add_peer_portfolio`, `peer_portfolios_all`), `engine/cli.py` (sub-app `portfolio`: comando `research`)
- Test: `tests/test_intent_portfolio_research.py`

**Interfaces:**
- Consumes: tabla `peer_portfolios` (existe: `role_match, peer_name, peer_profile_url, peer_portfolio_url, key_strengths_json, how_to_emulate_json, source_url, notes, reviewed_at`).
- Produces: intent type `portfolio_research`: `_ctx` entrega `{domain, target_role, current_references (seeds + peer_portfolios existentes), patterns}`; `_write` acepta `{portfolios: [{peer_name, peer_portfolio_url, role_match, key_strengths: list, how_to_emulate: list, source_url}]}` y upserta por `peer_portfolio_url` (no duplicar). CLI `atlas portfolio research [--enqueue]`: muestra la tabla actual con fecha `reviewed_at`; `--enqueue` encola el intent.

- [ ] **Step 1: Tests que fallan:** apply_result inserta filas con `reviewed_at` presente; re-aplicar con la misma URL actualiza en vez de duplicar; `context_for` incluye los seeds del dominio activo.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(portfolio): portfolio_research intent — living peer references`.

### Task 17: Seeds de portfolio enriquecidos + PortfolioViewer rico

**Files:**
- Modify: `config/seeds/data/portfolio_references.yaml` (y `default`/`architecture` en la misma pasada), `engine/portfolio/peer_examples.py` (pasar `name`/`why` si existen), `dashboard/backend/main.py` (`GET /api/portfolio/research` — main.py:1292-1319 — añade `peer_portfolios` + `last_reviewed_at`), `dashboard/frontend/src/components/PortfolioViewer.tsx`
- Test: `tests/test_portfolio_examples.py` (extender o crear)

**Interfaces:**
- Produces: cada referencia curada es `{url, name, why}` (los 9 de `data` con nombre real del autor del portfolio y una línea de por qué es buen ejemplo — contenido genérico del dominio, NO datos del usuario); `peer_examples_for` los devuelve completos; el endpoint suma los descubiertos por el intent; la UI muestra tarjetas (nombre, why, strengths) y la fecha del último research con CTA "Refrescar (encolar al brain)".

- [ ] **Step 1: Test que falla:** `peer_examples_for("data")` devuelve dicts con `name` y `why` no vacíos.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (YAML enriquecido a mano — investigar cada URL lo suficiente para un `why` honesto de una línea; loader tolerante con seeds viejos solo-URL).
- [ ] **Step 4:** endpoint + UI (skill `atlas-design-system`); build frontend verde.
- [ ] **Step 5: Run** → PASS. **Commit** `feat(portfolio): enriched curated references + rich viewer with live refresh CTA`.

### Task 18: Brain al día (SKILL.md + run_brain + morning brief)

**Files:**
- Modify: `brain/SKILL.md`, `brain/run_brain.py`
- Test: `tests/test_brain_intents.py` (extender: los tipos nuevos aparecen en la cola que el brain drena)

**Interfaces:**
- Produces: el pipeline del brain encola/drena `company_research` (para el top-N de la shortlist), `contact_discovery` (para jobs en `ready`), `portfolio_research` (semanal — si `reviewed_at` más reciente > 7 días), y el `MORNING_BRIEF.md` gana secciones: intents atascados (Task 6), fuentes en `ok_empty`/`unconfigured` (Task 8), y resumen de research nuevo.

- [ ] **Step 1: Test que falla:** con DB sembrada (job ready sin contactos; peer_portfolios viejo), el planner del brain (la parte determinista de `run_brain.py` que decide qué encolar) encola los intents esperados y es idempotente (segunda corrida no duplica pending).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** + actualizar `brain/SKILL.md` (instrucciones del task de Cowork: cómo drenar cada tipo nuevo, con la regla de untrusted input de `plans/027`).
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat(brain): enqueue new research intents + richer morning brief`.

### Task 19: Outcome calibration visible (Analytics)

**Files:**
- Modify: `engine/` (verificar qué existe en `tests/test_f3_analytics.py` / el módulo de analytics que alimenta AnalyticsStrip; extenderlo), `dashboard/backend/main.py`, `dashboard/frontend/src/components/AnalyticsStrip.tsx`
- Test: `tests/test_f3_analytics.py` (extender)

**Interfaces:**
- Consumes: `application_outcomes`, `applications`, `cv_versions`, `messages`.
- Produces: métricas `response_rate_by_channel` y `response_rate_by_cv_version` (si no existen ya — VERIFICAR primero leyendo `tests/test_f3_analytics.py`; si existen, esta task es solo exponerlas/pintarlas) + tarjeta en Analytics con n mínimo (no mostrar % con n<5; mostrar "n=3, aún sin señal").

- [ ] **Step 1:** leer `tests/test_f3_analytics.py` y el módulo real; escribir el test de la métrica faltante (que falle).
- [ ] **Step 2-4:** implementar → verde → UI.
- [ ] **Step 5: Commit** `feat(analytics): outcome calibration (response rates by channel and CV version)`.

---

## Fase F4 — Validación end-to-end con el perfil real (con el usuario)

> Estas tasks NO son TDD: son operación + verificación real. Requieren al usuario presente y `export ATLAS_PROFILES_DIR="/Users/anthonymanotoa/dev/personal/atlas/profiles"`.

### Task 20: Datos reales y brain operativo

- [ ] **Step 1:** Mapear el CV real: abrir `profiles/owner/profile/master_cv.draft.yaml`, estructurar `_source_text` en los campos del YAML (con el usuario validando cada sección), borrar `_source_text`.
- [ ] **Step 2:** `uv run atlas cv promote` → verde. `uv run atlas doctor` sin hallazgos de plantilla.
- [ ] **Step 3:** Limpiar el perfil: verificar que discover ya no trae fuentes demo (Task 7); configurar o desactivar explícitamente Adzuna (estado `unconfigured` visible si se deja sin credenciales).
- [ ] **Step 4:** Brain: revisar con el usuario la tarea Cowork `atlas-job-brain` (existe, apunta al repo correcto, corre 08:10); si está rota, recrearla siguiendo `brain/SKILL.md`. Drenar los intents pendientes (los 2 atascados + los nuevos) en una corrida supervisada. Verificar `MORNING_BRIEF.md` generado y heartbeat fresco (`downtime_hours() is None`).
- [ ] **Step 5:** Commit de lo que sea repo (configs); los datos del perfil NO se commitean.

### Task 21: Validación funcional completa + aplicaciones reales

- [ ] **Step 1:** Suite completa verde: `rtk uv run --group dev pytest` (≥514 + los nuevos).
- [ ] **Step 2:** `./scripts/run.sh` + walkthrough del dashboard en el navegador (todas las vistas: NeedsAction, Board, JobDetail, Analytics, Portfolio, Brain Tasks, selector de perfil, Cmd+K, claro/oscuro). Verificar los features nuevos: banner CV (ausente ahora), estados de fuentes, ×N variantes, prioridad, reviews, contactos, portfolio rico.
- [ ] **Step 3:** Elegir 3-5 vacantes reales del top → `uv run atlas prep <job_id>` cada una → revisar DOCX+PDF (identidad real, `review.md` todo ✅) y los 5 mensajes.
- [ ] **Step 4:** `uv run atlas portfolio generate` con datos reales + `portfolio research` fresco.
- [ ] **Step 5:** `uv run atlas interview prep` (o `interview add` + `prep`) para al menos 1 vacante.
- [ ] **Step 6:** **Aplicar de verdad a ≥3 vacantes** — el usuario envía (Claude en Chrome puede pre-rellenar formularios con el usuario mirando; Atlas jamás envía). Registrar estado (applied) y verificar followups programados (0/3/7/14) y `outcome` al recibir respuesta.
- [ ] **Step 7:** Criterio de éxito del plan (del spec §F4): ≥3 aplicaciones reales enviadas con materiales sin placeholders, brain con heartbeat fresco, suite verde, dashboard sin regresiones.
- [ ] **Step 8:** Cierre de rama: `superpowers:verification-before-completion` → `superpowers:requesting-code-review` → `superpowers:finishing-a-development-branch` (repo personal: merge local permitido si tests + review pasaron).

---

## Orden y dependencias

```
F0: 1 → 2 → 3 → 4        (CV plantilla: detector → CLI → UI → promote)
    5, 6, 7               (independientes entre sí)
F1: 8, 9, 10, 11          (independientes; 9 y 10 tocan ambos `top` — hacerlos en ese orden)
F2: 12 → 13
F3: 14, 15, 16 (paralelos) → 17 → 18 → 19
F4: 20 → 21               (siempre al final; requieren al usuario)
```

## Self-review del plan (hecho)

- Cobertura del spec: F0.1→T1-4, F0.2→T5-6+T20, F0.3→T7, F1.1→T8, F1.2→T9, F1.3→T10, F1.4→T11, F2.1→T12, F2.2→T13, F3.1→T15, F3.2→T14, F3.3→T16-17, F3.4→T18-19, F4→T20-21. Backlog (Workday, negotiation) fuera, como dice el spec §6.
- Verificado contra el código real: `INTENT_TYPES`/handlers en `engine/intents.py`, `source_health` y `peer_portfolios` en `schema.sql`, `liveness.py` existente (T11 solo activa/surfacea), `DB.add_contact`/`cv_reviews_for` existentes, sub-apps typer (`portfolio_app`, `intents_app`, `cv`).
- Donde el nombre exacto de un helper no está verificado (loader del master CV, helper del perfil activo en `paths.py`, fixture de perfil en conftest), la task lo dice explícitamente y ordena verificar/reusar el real en vez de inventar.
