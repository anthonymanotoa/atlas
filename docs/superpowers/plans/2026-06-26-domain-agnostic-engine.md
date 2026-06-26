# Domain-Agnostic Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Atlas work for any industry (first new domain: architecture) by introducing a per-profile `domain` concept, per-domain seed packs, and making every generator/UI read config instead of hardcoded "data/AI" literals.

**Architecture:** The deterministic engine is already config-driven. We add (1) a `domain` field on the profile registry, (2) per-domain seed packs under `config/seeds/<domain>/` that populate the already-per-profile config files, and (3) edits so generators/UI read that config. Runtime source of truth = the profile's own config files.

**Tech Stack:** Python 3.12 + Pydantic + Typer (engine), FastAPI (dashboard backend), React + TS + shadcn (frontend), YAML config, pytest.

## Global Constraints

- Tests run via `uv run rtk pytest` (117 green today — must stay green). Use `uv sync --group dev` if deps missing.
- The `data`/owner profile MUST produce identical output after the change (golden test).
- Profiles without a `domain` field default to `"data"` (back-compat).
- Never hardcode "data/AI/ML" in any path a non-data profile sees.
- Code edits happen in the worktree; Lucy's profile DATA lives in the MAIN checkout (`/Users/anthonymanotoa/dev/personal/atlas/profiles/lucy`).
- Commit per task. Add files by name (never `git add -A`). End commits with the Co-Authored-By trailer.
- Any frontend copy/markup touched follows the `atlas-design-system` (Warm Editorial) skill.

## File Structure

- `engine/profiles.py` — add `domain` to registry + `create_profile` + `domain_of`; `_seeds_for(domain)`.
- `engine/cli.py` — `--domain` on `profiles create`; show domain in `profiles list`.
- `engine/config.py` — new `Criteria` fields; new loaders `load_cv_layout()`, `load_interview_topics()`.
- `engine/paths.py` — `CV_LAYOUT_PATH`, `INTERVIEW_TOPICS_PATH` globals.
- `engine/scoring/fit.py` — read title-ladder + stretch from `Criteria`.
- `engine/advisor.py` — drop hardcoded lists; read ontology + `criteria.core_keywords`; gate repositioning.
- `engine/outreach/templates.py` — `basics.pitch` interpolation; ontology-derived acronyms/skills-phrase.
- `engine/portfolio/{builder,prompt,peer_research}.py` — pluggable proof-source; parameterized prompt.
- `engine/cv/{render,parse_check,build,import_cv}.py` — layout-driven sections; `ALLOWED_LANGUAGES` from criteria.
- `engine/interview/interview_prep.py` — read banks from `interview_topics.yaml`.
- `engine/discovery/jobspy_source.py` — drop hardcoded `'USA'`.
- `dashboard/backend/main.py` — expose `domain`/target label + source list.
- `dashboard/frontend/src/{OnboardingGate,HelpGuide,CvAuditDialog,PortfolioViewer,App,InterviewPanel,Board,DetailDrawer}.tsx`.
- `config/seeds/{data,architecture,default}/...` — the packs.
- `README.md` — generic advisor description.

---

### Task 1: `domain` concept on profiles

**Files:**
- Modify: `engine/profiles.py` (`_register`, `create_profile`, add `domain_of`, `init_owner`)
- Modify: `engine/cli.py` (`profiles create` → `--domain`; `profiles list` shows domain)
- Test: `tests/test_profiles_domain.py`

**Interfaces:**
- Produces: `profiles.create_profile(profile_id, label=None, domain="data") -> dict`; `profiles.domain_of(profile_id) -> str` (default `"data"`); registry entry gains `"domain"`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_profiles_domain.py
from engine import profiles, paths

def test_create_profile_persists_domain(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_DIR", tmp_path)
    monkeypatch.setattr(paths, "REGISTRY_PATH", tmp_path / "registry.json")
    profiles.create_profile("lucy", "Lucy", domain="architecture")
    assert profiles.domain_of("lucy") == "architecture"

def test_domain_defaults_to_data_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_DIR", tmp_path)
    monkeypatch.setattr(paths, "REGISTRY_PATH", tmp_path / "registry.json")
    profiles.create_profile("bob", "Bob")  # no domain arg
    assert profiles.domain_of("bob") == "data"
    assert profiles.domain_of("nonexistent") == "data"
```

- [ ] **Step 2: Run, expect FAIL** (`domain_of` undefined / signature mismatch). `uv run rtk pytest tests/test_profiles_domain.py -v`
- [ ] **Step 3: Implement** — `create_profile(profile_id, label=None, domain="data")` passes `domain` to `_register`, which stores it on the entry; add `domain_of()`; `init_owner()` registers `domain="data"`.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Implement CLI** — `--domain` option (default `"data"`, validated against `config/seeds/` dirs with a clear error listing available packs); `profiles list` prints domain.
- [ ] **Step 6: Commit** `feat(profiles): add per-profile domain concept`

---

### Task 2: Per-domain seed packs + `data` & `default` packs (back-compat)

**Files:**
- Create: `config/seeds/data/{criteria.example.md,ontology.yaml,sources.yaml,companies.example.yaml,master_cv.example.yaml}` (moved/copied from current content — byte-identical content)
- Create: `config/seeds/default/{...}` (neutral placeholders, empty ontology)
- Modify: `engine/profiles.py` (`_SEEDS` → `_seeds_for(domain)`, fallback to `default`, STOP seeding ontology/sources from live files)
- Test: `tests/test_seed_packs.py`

**Interfaces:**
- Consumes: `profiles.domain_of` (Task 1).
- Produces: `profiles._seeds_for(domain) -> list[tuple[str,str]]`; `create_profile` seeds from `config/seeds/<domain>/` with `default` fallback.

- [ ] **Step 1: Write failing test**

```python
# tests/test_seed_packs.py
import yaml
from engine import profiles, paths

def _mk(tmp_path, monkeypatch, domain):
    monkeypatch.setattr(paths, "PROFILES_DIR", tmp_path)
    monkeypatch.setattr(paths, "REGISTRY_PATH", tmp_path / "registry.json")
    profiles.create_profile("p", "P", domain=domain)
    return tmp_path / "p"

def test_data_profile_seeds_ds_ontology(tmp_path, monkeypatch):
    root = _mk(tmp_path, monkeypatch, "data")
    ont = yaml.safe_load((root / "config/ontology.yaml").read_text())["skills"]
    assert "Python" in ont  # data pack keeps the DS gazetteer

def test_architecture_profile_seeds_aec_ontology(tmp_path, monkeypatch):
    root = _mk(tmp_path, monkeypatch, "architecture")
    ont = yaml.safe_load((root / "config/ontology.yaml").read_text())["skills"]
    assert "Revit" in ont and "Python" not in ont
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** `_seeds_for(domain)`; create `config/seeds/data/` (current content), `config/seeds/default/`. (Architecture pack lands in Task 3 — its test is xfail-marked until then, or Task 3 ordered before re-running this test.)
- [ ] **Step 4: Run data test, expect PASS**
- [ ] **Step 5: Commit** `feat(profiles): per-domain seed packs (data + default)`

---

### Task 3: Author the `architecture` seed pack (content)

**Files:**
- Create: `config/seeds/architecture/{criteria.example.md,ontology.yaml,sources.yaml,companies.example.yaml,master_cv.example.yaml,cv_layout.yaml,interview_topics.yaml}`
- Test: `tests/test_seed_packs.py::test_architecture_profile_seeds_aec_ontology` (from Task 2)

**Interfaces:**
- Produces: the architecture pack content (AEC ontology, criteria with `exclude_exec: false`, `stretch_terms: []`, `repositioning_target: ""`, es/en languages, architecture roles; cv_layout with projects-first + licensure; interview_topics).

- [ ] **Step 1:** Author `ontology.yaml` (AEC gazetteer from `docs/research/architecture-cv-recommendations.md` §3: Revit, AutoCAD, ArchiCAD, SketchUp, Rhino, Grasshopper, Dynamo, Lumion, Enscape, Twinmotion, D5 Render, V-Ray, Navisworks, BIM, LEED, Adobe PS/AI/InDesign, construction documents, heritage rehabilitation, residential design — with aliases).
- [ ] **Step 2:** Author `criteria.example.md` (roles, must_haves revit/autocad, `exclude_exec: false`, `stretch_terms: []`, building-vs-software-architect deal_breakers, languages es/en, locations).
- [ ] **Step 3:** Author `sources.yaml` (architecture search terms; on-site allowed), `companies.example.yaml` (empty/AEC), `cv_layout.yaml` (projects-first, licensure section, `proof_source: visual_gallery`), `interview_topics.yaml`, `master_cv.example.yaml` (architect scaffold with `basics.pitch`, `licensure`).
- [ ] **Step 4: Run** `tests/test_seed_packs.py -v`, expect PASS
- [ ] **Step 5: Commit** `feat(seeds): architecture domain pack`

---

### Task 4: New `Criteria` fields

**Files:**
- Modify: `engine/config.py` (`Criteria`)
- Test: `tests/test_criteria_fields.py`

**Interfaces:**
- Produces: `Criteria.stretch_terms: list[str]` (default `["staff","principal","distinguished","fellow"]`), `stretch_min_years: int` (default 8), `senior_terms`/`exec_terms`/`junior_terms` (defaults = current `fit.py` tuples as lists), `core_keywords: list[str]` (default `[]`), `repositioning_target: str` (default `""`), `top_jd_keywords: int` (25), `max_skills: int` (18), `max_highlights_per_role: int` (4).

- [ ] **Step 1: Write failing test**

```python
# tests/test_criteria_fields.py
from engine.config import Criteria

def test_new_fields_have_backcompat_defaults():
    c = Criteria()
    assert c.stretch_terms == ["staff", "principal", "distinguished", "fellow"]
    assert c.stretch_min_years == 8
    assert c.repositioning_target == ""
    assert c.core_keywords == []
    assert c.top_jd_keywords == 25

def test_architecture_can_disable_stretch():
    c = Criteria(stretch_terms=[], exclude_exec=False)
    assert c.stretch_terms == [] and c.exclude_exec is False
```

- [ ] **Step 2: Run, expect FAIL** · **Step 3: Add fields** · **Step 4: Run, expect PASS** · **Step 5: Commit** `feat(config): per-profile fields for scoring/tuning/positioning`

---

### Task 5: Scoring reads ladder + stretch from `Criteria`

**Files:**
- Modify: `engine/scoring/fit.py` (`score_job`: use `criteria.junior_terms/exec_terms/stretch_terms/stretch_min_years/senior_terms`)
- Test: `tests/test_fit_domain.py` (+ existing `tests/` scoring tests must stay green)

**Interfaces:** Consumes Task 4 fields.

- [ ] **Step 1: Write failing test**

```python
# tests/test_fit_domain.py
from engine.config import Criteria
from engine.scoring.fit import score_job

ARCH = Criteria(roles=["architect"], remote_required=False, exclude_exec=False, stretch_terms=[], candidate_years=1)

def test_principal_architect_not_penalized_when_stretch_disabled():
    r = score_job({"title": "Principal Architect", "description": "Revit AutoCAD"}, ARCH)
    assert r.disqualified is False
    assert not any("staff/principal" in k.lower() for k in r.knockouts)

def test_director_of_design_not_dq_when_exec_allowed():
    r = score_job({"title": "Director of Design", "description": "architecture studio"}, ARCH)
    assert r.disqualified is False

def test_data_profile_still_penalizes_stretch():
    data = Criteria(roles=["data scientist"], candidate_years=5)  # defaults keep stretch on
    r = score_job({"title": "Principal Data Scientist", "description": "ml"}, data)
    assert any("staff/principal" in k.lower() for k in r.knockouts)
```

- [ ] **Step 2: Run, expect FAIL** · **Step 3:** Replace module constants `JUNIOR_TERMS/EXEC_TERMS/SENIOR_TERMS/_STRETCH_RE/STRETCH_MIN_YEARS` usage in `score_job` with `criteria.*` (build the stretch regex from `criteria.stretch_terms`; skip stretch logic when empty). Keep module constants as the defaults feeding `Criteria`. · **Step 4: Run new + full scoring suite, expect PASS** · **Step 5: Commit** `feat(scoring): drive title-ladder + stretch from criteria`

---

### Task 6: De-bias the advisor

**Files:**
- Modify: `engine/advisor.py` (drop `AI_TERMS` + inline `core`; read `criteria.core_keywords` + ontology; gate repositioning findings on `criteria.repositioning_target`; neutralize summary suggestion copy)
- Modify: `engine/cli.py:382-392` (`advise` footer copy)
- Test: `tests/test_advisor_domain.py` (+ existing advisor tests green)

**Interfaces:** `audit_cv(master, criteria=None)` — optional criteria; when `None`, `load_criteria()`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_advisor_domain.py
from engine.advisor import audit_cv
from engine.config import Criteria

ARCH_CV = {"basics": {"email": "a@b.c", "linkedin": "x", "summary": "Arquitecta con experiencia en Revit y rehabilitación patrimonial, 40 palabras..."},
           "skills": ["Revit", "AutoCAD", "Lumion"], "experience": [{"title": "Dibujante", "company": "P&P", "highlights": ["Produje 12 planos", "Coordiné documentación"]}]}

def test_no_ai_repositioning_when_target_empty():
    findings = audit_cv(ARCH_CV, Criteria(repositioning_target="", core_keywords=["revit", "autocad", "bim"]))
    assert not any("IA" in f.message or "IA/ML" in f.suggestion for f in findings)
    assert not any("posicionamiento IA" in f.area for f in findings)

def test_core_keywords_come_from_criteria():
    findings = audit_cv({"basics": {"email": "a@b.c"}, "skills": [], "experience": []},
                        Criteria(core_keywords=["revit", "bim"]))
    msgs = " ".join(f.message for f in findings)
    assert "python" not in msgs.lower()
```

- [ ] **Step 2: Run, expect FAIL** · **Step 3:** Refactor `audit_cv` to take `criteria`; replace `_has_ai`/`AI_TERMS` with a check against `criteria.repositioning_target` terms (skip when empty); replace `core` list with `criteria.core_keywords`; neutralize the "enfoque en IA" summary copy to "tu propuesta de valor". Keep all domain-neutral checks (placeholders, contact, quantified bullets). · **Step 4: Run, expect PASS** · **Step 5: Commit** `feat(advisor): domain-driven audit, gate repositioning on criteria`

---

### Task 7: Outreach identity from `basics.pitch`

**Files:**
- Modify: `engine/outreach/templates.py` (interpolate `basics.pitch`; ontology-derived `_ACRONYMS`; neutral `_skills_phrase` fallback)
- Test: `tests/test_outreach_domain.py` (+ existing outreach tests green)

**Interfaces:** templates read `master["basics"]["pitch"] = {identity_line, impact_domain, role_noun, value_verb}`; absent → neutral fallback derived from `basics.label`.

- [ ] **Step 1: Write failing test** (assert an architect pitch yields a body containing her role_noun and NOT "data scientist").
- [ ] **Step 2: Run, expect FAIL** · **Step 3: Implement** · **Step 4: Run, expect PASS** · **Step 5: Commit** `feat(outreach): identity from basics.pitch, not hardcoded DS`

---

### Task 8: Portfolio proof-source + prompt

**Files:**
- Modify: `engine/portfolio/builder.py` (proof-source: `github | visual_gallery | none` from `cv_layout.yaml`/config), `engine/portfolio/prompt.py` (label/themes/buckets from criteria + `basics.label/pitch`), `engine/portfolio/peer_research.py:43-49` (host filter by domain)
- Test: `tests/test_portfolio_domain.py`

- [ ] **Step 1: Write failing test** (architecture profile → prompt has no "Senior Data Scientist"/"GitHub"; peer query uses behance/issuu).
- [ ] **Step 2: Run, expect FAIL** · **Step 3: Implement** · **Step 4: Run, expect PASS** · **Step 5: Commit** `feat(portfolio): pluggable proof-source + domain-parameterized prompt`

---

### Task 9: CV layout per-domain + languages from criteria

**Files:**
- Modify: `engine/paths.py` (`CV_LAYOUT_PATH`), `engine/config.py` (`load_cv_layout()`), `engine/cv/render.py` (order/labels/sections from layout), `engine/cv/parse_check.py` (required-sections from layout), `engine/cv/build.py:16` (`ALLOWED_LANGUAGES` from `criteria.languages`)
- Test: `tests/test_cv_layout.py`

**Interfaces:** `load_cv_layout() -> dict` with `sections: [..]`, `labels: {..}`, `proof_source: str`; default = current data layout.

- [ ] **Step 1: Write failing test** (architecture layout renders Projects before Experience; a "Licenciatura/Registro" section label present; default profile unchanged).
- [ ] **Step 2: Run, expect FAIL** · **Step 3: Implement** · **Step 4: Run, expect PASS** · **Step 5: Commit** `feat(cv): per-domain layout + languages from criteria`

---

### Task 10: master_cv scaffold + import per-domain

**Files:**
- Modify: `engine/cv/import_cv.py` (richer per-domain draft scaffold incl. licensure, project metadata)
- Test: `tests/test_import_cv_domain.py`

- [ ] **Step 1: Write failing test** · **Step 2: FAIL** · **Step 3: Implement** · **Step 4: PASS** · **Step 5: Commit** `feat(cv): per-domain import scaffold`

---

### Task 11: Interview banks externalized

**Files:**
- Modify: `engine/paths.py` (`INTERVIEW_TOPICS_PATH`), `engine/config.py` (`load_interview_topics()`), `engine/interview/interview_prep.py` (read banks from config; `_DEFAULT_TECH` from ontology)
- Test: `tests/test_interview_domain.py`

- [ ] **Step 1: Write failing test** (architecture interview topics include "portafolio"/"fases de proyecto", not "system design"). · **Step 2: FAIL** · **Step 3: Implement** (fallback to embedded data bank when no file → data profile unchanged) · **Step 4: PASS** · **Step 5: Commit** `feat(interview): externalize question banks per domain`

---

### Task 12: Discovery defaults

**Files:**
- Modify: `engine/discovery/jobspy_source.py:100` (drop hardcoded `'USA'`; derive from criteria)
- Test: `tests/test_jobspy_defaults.py`

- [ ] **Step 1: Write failing test** · **Step 2: FAIL** · **Step 3: Implement** · **Step 4: PASS** · **Step 5: Commit** `fix(discovery): drop hardcoded USA default`

---

### Task 13: Backend API exposes domain + sources

**Files:**
- Modify: `dashboard/backend/main.py` (onboarding/profiles route returns `domain` + target label; ensure `source_health` enumerates real sources)
- Test: `tests/test_api_domain.py` (FastAPI TestClient)

- [ ] **Step 1: Write failing test** · **Step 2: FAIL** · **Step 3: Implement** · **Step 4: PASS** · **Step 5: Commit** `feat(api): expose profile domain + target label`

---

### Task 14: Frontend neutralization (apply atlas-design-system)

**Files:**
- Modify: `OnboardingGate.tsx`, `HelpGuide.tsx`, `CvAuditDialog.tsx`, `PortfolioViewer.tsx`, `App.tsx`, `InterviewPanel.tsx`, `Board.tsx`, `DetailDrawer.tsx`
- Verify: `npm --prefix dashboard/frontend run build` + preview tools

- [ ] **Step 1:** Replace hardcoded IA/ML strings with `domain`/target-label from API + neutral fallback; render `source_health` instead of `SEARCH_SOURCES`; backend-provided interview rounds; neutral tooltips.
- [ ] **Step 2:** `rtk tsc` / build clean; preview check (onboarding shows no IA/ML for architecture).
- [ ] **Step 3: Commit** `feat(ui): neutralize domain copy, read profile domain`

---

### Task 15: README copy

**Files:** Modify `README.md` (advisor described generically; IA/ML as *example* track)
- [ ] **Step 1:** Edit. · [ ] **Step 2: Commit** `docs: describe advisor generically`

---

### Task 16: Re-onboard Lucy (MAIN checkout)

**Files:** `profiles/lucy/...` in the MAIN checkout (after merge of the engine work, or run engine from worktree against main's profiles dir).
- [ ] **Step 1:** Set Lucy's `domain="architecture"` (re-create or migrate her profile entry); re-seed/merge architecture config (criteria, ontology, cv_layout) without losing her CV.
- [ ] **Step 2:** Rewrite `profiles/lucy/profile/master_cv.yaml` per `architecture-cv-recommendations.md` §6 (title "Arquitecta", projects-first, software with plain-text levels, `basics.pitch`, licensure section, portfolio-link reminder).
- [ ] **Step 3:** Run `uv run atlas --profile lucy discover` + `score` + `advise`; verify output is architecture-correct (no "te falta IA"; AEC keyword matches; realistic).
- [ ] **Step 4:** Deliver CV recommendations + onboarding summary to the user.

---

## Self-Review

- **Spec coverage:** §4.1→T1, §4.2→T2, §4.9→T3, §4.3→T4+T5, §4.4→T6+T7+T8, §4.5→T13+T14, §4.6→T9+T10, §4.7→T11, §4.8→T12, README→T15, Lucy→T16. ✓
- **Placeholder scan:** Tasks 7–13 compress TDD code blocks (test intent stated, code written at execution). Acceptable since the executor (me) holds full context; each still ends with an independently testable deliverable + commit.
- **Type consistency:** `domain_of`, `create_profile(..., domain=)`, `criteria.stretch_terms/core_keywords/repositioning_target`, `load_cv_layout`, `load_interview_topics`, `basics.pitch` used consistently across tasks.
