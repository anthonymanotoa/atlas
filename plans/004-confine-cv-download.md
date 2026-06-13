# Plan 004: Validate `language` and confine CV downloads to the outbox

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/cv/build.py dashboard/backend/main.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

The HTTP/CLI-controlled `language` value flows unvalidated into a filesystem
path used to write and later serve CV files. A `language` such as
`../../../../tmp/pwn` causes Atlas to write `cv_...docx`/`.pdf` **outside**
`data/outbox`, and the resulting absolute path is persisted to the DB and then
served verbatim by the download endpoint after only an `exists()` check — so a
crafted prep request can write a file to an arbitrary location and read it back
out through the API. This is SECURITY-01 (HIGH): a path-traversal write/read
primitive on a localhost-only single-user app. The fix closes it at the input
boundary: `language` is constrained to a two-value allowlist (`en`/`es`), and
the download endpoint refuses any stored path that does not resolve inside
`OUTBOX_DIR`. After this lands, no untrusted string reaches a path component and
no file outside the outbox can be served.

## Current state

Files and their roles:

- `dashboard/backend/main.py` — FastAPI backend. Declares `PrepBody.language`
  (unconstrained `str`), the `/api/jobs/{job_id}/prep` endpoint that forwards it,
  and the `/api/cv/{job_id}/{version_id}/download` endpoint that serves the
  persisted path.
- `engine/cv/build.py` — `build_for_job()` tailors → renders → persists one CV;
  it composes the output path from `language`.
- `engine/cv/render.py` — `render_docx`/`render_pdf` do `out_path.parent.mkdir(parents=True, ...)` + save. **Out of scope** (the fix is at the input boundary, not here).
- `engine/paths.py` — single source of truth for paths; defines `OUTBOX_DIR`.

The vulnerable code as it exists today:

`dashboard/backend/main.py:33-34` — `language` is an unconstrained string:

```python
class PrepBody(BaseModel):
    language: str = "en"
```

`dashboard/backend/main.py:86-96` — `api_prep` forwards `body.language` straight into the build:

```python
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
```

`engine/cv/build.py:29-44` — `language` is concatenated into the output path, then written; the absolute paths are persisted at lines 47-52:

```python
def build_for_job(db: DB, job_id: str, *, language: str = "en",
                  cv_override: Optional[dict] = None, make_pdf: bool = True) -> BuildResult:
    """Generate a tailored, parse-safe CV for `job_id`. `cv_override` lets the brain
    pass an LLM-reworded (still truthful) CV dict instead of the deterministic one."""
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    master = load_master_cv()
    ontology = load_ontology()
    result = tailor.tailor(master, job, ontology)
    cv = cv_override or result.cv

    out_dir = OUTBOX_DIR / job_id
    docx_path = out_dir / f"cv_{language}.docx"
    render.render_docx(cv, docx_path, language=language)
    pdf_path = render.render_pdf(cv, out_dir / f"cv_{language}.pdf", language=language) if make_pdf else None
```

`engine/cv/render.py:131-132` — the write side that makes traversal effective:

```python
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
```

`dashboard/backend/main.py:114-126` — `api_cv_download` serves the stored path with only an `exists()` check, no containment to the outbox:

```python
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
```

`engine/paths.py:9-12` — `OUTBOX_DIR` is the directory writes must stay inside:

```python
DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", REPO_ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "atlas.db"
INBOX_DIR = DATA_DIR / "inbox"
OUTBOX_DIR = DATA_DIR / "outbox"
```

Note `DATA_DIR` (and therefore `OUTBOX_DIR`) is already `.resolve()`d, so it is
absolute. `Path.is_relative_to` is available on Python 3.9+; the project targets
3.11+, so it is safe to use.

Conventions this plan must match (state and follow them):

- `from __future__ import annotations` at the top of every engine/backend module
  (see `dashboard/backend/main.py:7`, `engine/cv/build.py:2`).
- pydantic v2 `BaseModel` for request bodies (`dashboard/backend/main.py:15,29,33`).
- typer CLI elsewhere in the engine; `@dataclass` result objects
  (`engine/cv/build.py:14-26`, `BuildResult`).
- Validation failures in the engine raise `ValueError` (see
  `engine/cv/build.py:35`, `raise ValueError(f"job {job_id} not found")`).
- API validation failures raise `fastapi.HTTPException` with a status + message
  (see `dashboard/backend/main.py:71`, `raise HTTPException(400, ...)`, and
  `:119,122`, `raise HTTPException(404, ...)`).
- Tests live in `tests/test_engine.py`; model new tests after the existing ones
  there (same imports, fixtures, and `assert`/`pytest.raises` style).

## Commands you will need

| Purpose          | Command                                          | Expected on success            |
|------------------|--------------------------------------------------|--------------------------------|
| Python tests     | `uv run --extra dev pytest`                      | exit 0, "9 passed" (more after new tests are added — see Test plan) |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck` | exit 0, no errors              |
| Frontend build   | `npm --prefix dashboard/frontend run build`      | exit 0                         |
| Drift check      | `git diff --stat c3e2679..HEAD -- engine/cv/build.py dashboard/backend/main.py tests/test_engine.py` | (drift check, see header) |

Do NOT run bare `pytest`: the global interpreter is missing `docx`, `rapidfuzz`,
and `reportlab`, so it falsely fails 2 tests. Always go through
`uv run --extra dev pytest`.

## Scope

**In scope** (the only files you should modify):

- `engine/cv/build.py`
- `dashboard/backend/main.py`
- `tests/test_engine.py`

**Out of scope** (do NOT touch, even though they look related):

- `engine/cv/render.py` — the write itself (`mkdir(parents=True)` + `save`).
  Fix at the input boundary (validate `language`); do not try to harden the
  renderer. Changing it widens the blast radius and the renderer is also called
  with already-validated input from the CLI/brain.
- `engine/paths.py` — `OUTBOX_DIR` is correct as-is; only read it.
- The frontend (`dashboard/frontend/`) — it already sends `en`/`es` only; no
  change needed (typecheck/build are run only as regression gates).

## Git workflow

- Branch: `advisor/004-confine-cv-download` (created from latest `main`).
- Commit per logical unit (e.g. one commit for the engine+API guards, one for
  the tests), or a single squashed commit — match the repo's style.
- Stage only the in-scope files by name (`git add engine/cv/build.py dashboard/backend/main.py tests/test_engine.py`). Never `git add .` / `git add -A`.
- Do NOT push or open a PR. The merge to `main` is decided by the operator.

## Steps

### Step 1: Constrain `language` to `{en, es}` in `build_for_job`

In `engine/cv/build.py`, inside `build_for_job`, reject any `language` not in the
allowlist **before** it is used to compose a path. Add the guard immediately
after the `job` existence check (after `engine/cv/build.py:35`), so it raises
before any rendering or DB write:

```python
    if language not in ("en", "es"):
        raise ValueError(f"unsupported language {language!r}; expected 'en' or 'es'")
```

This matches the existing `ValueError` convention in the same function and stops
a traversal string at the boundary. Keep the existing `language: str = "en"`
default signature unchanged.

**Verify**: `uv run --extra dev pytest` → exit 0, existing tests still pass
("9 passed", before the new tests from Step 4 are added).

### Step 2: Constrain `PrepBody.language` at the API boundary

In `dashboard/backend/main.py`, change `PrepBody.language` from an unconstrained
`str` to a pydantic v2 `Literal` so FastAPI rejects bad values with a 422 before
any handler runs. Add `from typing import Literal` to the imports and update the
model (`dashboard/backend/main.py:33-34`):

```python
class PrepBody(BaseModel):
    language: Literal["en", "es"] = "en"
```

This is defense-in-depth on top of Step 1 (the engine guard still protects the
CLI and the brain, which do not go through `PrepBody`).

**Verify**: `uv run --extra dev pytest` → exit 0. (The import + type change must
not break collection.)

### Step 3: Confine the download endpoint to `OUTBOX_DIR`

In `dashboard/backend/main.py`, `api_cv_download` (`:114-126`), add a containment
check after the `exists()` check: resolve the stored path and 404 unless it is
inside the resolved `OUTBOX_DIR`. `OUTBOX_DIR` is already imported at
`dashboard/backend/main.py:20`. Replace the body of the path-validation section
so it reads:

```python
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, f"{fmt} file not available")
    try:
        resolved = p.resolve()
    except OSError:
        raise HTTPException(404, f"{fmt} file not available")
    if not resolved.is_relative_to(OUTBOX_DIR.resolve()):
        raise HTTPException(404, f"{fmt} file not available")
```

Keep the `if not path or ...` guard for the missing-path case. The endpoint must
never serve a file outside the outbox, even if such a path is somehow already
persisted in the DB. Continue to return the existing `FileResponse(str(p), ...)`.

**Verify**: `uv run --extra dev pytest` → exit 0.

### Step 4: Add regression tests

In `tests/test_engine.py`, add two tests modeled on the existing tests in that
file (same import style, same fixtures, `pytest.raises` for the engine guard):

1. `build_for_job` rejects a traversal `language`. Build a job in the test DB the
   same way the existing build tests do, then assert:

   ```python
   with pytest.raises(ValueError):
       build_for_job(db, job_id, language="../../../../tmp/pwn")
   ```

   (If a less invasive form fits the existing fixtures better — e.g. asserting
   `build_for_job(..., language="fr")` also raises — that is acceptable; the
   point is any non-`{en, es}` value raises before a path is composed.)

2. The download endpoint refuses an out-of-outbox path. Using FastAPI's
   `TestClient` (or a direct call to `api_cv_download`), arrange a persisted CV
   version whose `path_docx` points outside `OUTBOX_DIR` (e.g. a temp file under
   `tmp_path`), then assert the download returns **404** (not 200) — i.e. the
   containment check fires even when the file exists on disk.

Match whatever DB/fixture helpers the existing tests in `tests/test_engine.py`
already use; do not invent new fixtures if an existing one fits.

**Verify**: `uv run --extra dev pytest` → exit 0, with **2 more** tests passing
than before (was "9 passed" → now "11 passed", or "9 passed" plus the count of
tests you actually added).

### Step 5: Frontend regression gate

Confirm the frontend still typechecks and builds (no frontend change is expected;
this only guards against accidental coupling).

**Verify**:
- `npm --prefix dashboard/frontend run typecheck` → exit 0, no errors
- `npm --prefix dashboard/frontend run build` → exit 0

## Test plan

- New tests in `tests/test_engine.py`:
  1. **Engine guard**: `build_for_job(db, job_id, language="../../../../tmp/pwn")`
     raises `ValueError` (path-traversal language rejected at the boundary).
  2. **Download containment**: a CV version whose stored path resolves outside
     `OUTBOX_DIR` returns HTTP 404 from `api_cv_download` even though the file
     exists on disk.
- Structural pattern: model both after the existing tests in
  `tests/test_engine.py` (same imports, fixtures, and assertion style).
- Verification: `uv run --extra dev pytest` → all pass, including the 2 new tests
  (count rises from "9 passed" to "11 passed").

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports 2 more passing tests than the pre-change "9 passed" baseline (i.e. "11 passed").
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] `grep -n 'language: str = "en"' dashboard/backend/main.py` returns NO match (the `PrepBody.language` annotation is now a `Literal`).
- [ ] `grep -n 'is_relative_to' dashboard/backend/main.py` returns a match inside `api_cv_download`.
- [ ] `grep -n "unsupported language" engine/cv/build.py` returns a match (the engine guard exists).
- [ ] No files outside the in-scope list are modified (`git status` shows only `engine/cv/build.py`, `dashboard/backend/main.py`, `tests/test_engine.py`).
- [ ] `plans/README.md` status row for plan 004 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" does not match the quoted excerpts
  (the codebase has drifted since commit `c3e2679` — the drift-check `git diff`
  shows in-scope files changed).
- `uv run --extra dev pytest` does not report "9 passed" on a clean checkout
  before your changes — the baseline is wrong; investigate before editing.
- Adding the `is_relative_to` containment check breaks an existing download test
  because legitimate CV paths are NOT under `OUTBOX_DIR` (e.g. a custom
  `ATLAS_DATA_DIR` is in play that the test fixtures do not resolve the same way).
  Do not loosen the check to make it pass — report instead.
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (especially
  `engine/cv/render.py` or `engine/paths.py`).

## Maintenance notes

For the human/agent who owns this code after the change lands:

- The allowlist is duplicated in two places by design (the engine `ValueError`
  in `build_for_job` and the API `Literal` in `PrepBody`): the engine guard also
  covers the typer CLI and the brain, which never construct a `PrepBody`. If a
  third language is ever added, update **both** the `("en", "es")` tuple in
  `engine/cv/build.py` and the `Literal["en", "es"]` in
  `dashboard/backend/main.py`, plus the `HEADINGS` map in
  `engine/cv/render.py:16-23`.
- A reviewer should confirm: (a) the engine guard raises *before* any path is
  composed or any file written; (b) the download check uses
  `.resolve().is_relative_to(OUTBOX_DIR.resolve())` (both sides resolved) so
  symlink/`..` tricks cannot escape; (c) no legitimate download regressed.
- Deferred out of this plan: hardening `engine/cv/render.py` itself (e.g.
  refusing to write outside `OUTBOX_DIR` at the save site). Left out because the
  input-boundary fix is sufficient and the renderer is also called with
  already-validated input; revisit only if a new caller can pass an
  attacker-controlled `out_path`.
