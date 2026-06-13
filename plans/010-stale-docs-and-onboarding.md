# Plan 010: Fix stale LibreOffice text, the missing CV seed file, and advisor wording

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- engine/cli.py engine/outreach/build.py docs/SETUP.md README.md .gitignore profile/master_cv.example.yaml`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts below against the live code before proceeding; on a
> mismatch, treat it as a STOP condition. (This plan is documented as already
> implemented; if you are re-running it, expect the "after" text — see
> "Done criteria" — to already be present.)

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: docs
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Three independent onboarding/docs defects mislead a brand-new user on day one.
(1) The PDF path is now native (reportlab) — `engine/cv/render.py:140` `render_pdf`
explicitly says "no LibreOffice/Word needed" — yet four user-facing strings still
tell people they need LibreOffice and that the PDF is "skipped" without it; the PDF
is in fact always produced. (2) The setup docs instruct `cp profile/master_cv.example.yaml
profile/master_cv.yaml`, but that example file does not exist, and `.gitignore`'s
`profile/master_cv.*.yaml` glob would silently swallow it even if created — so the
first command in "Seed your data" fails and `load_master_cv()` falls back to `{}`.
(3) The docs and CLI call `advisor/cv_linkedin_advisor.md` "the cv-linkedin-advisor
skill", but it is a plain advisor doc, not a discoverable `SKILL.md` — the wording
overpromises. Fixing all three makes the documented onboarding match reality, with
zero behavioral code change.

## Current state

Files and their roles:

- `engine/cli.py` — typer CLI. The `tailor` command's `--pdf` help and its result
  printout carry stale LibreOffice text; the `advise` command's closing hint calls
  the advisor doc a "skill".
- `engine/outreach/build.py` — builds the per-job outreach markdown; the PDF line
  has a stale LibreOffice fallback string.
- `engine/cv/render.py` — CV renderer. `render_pdf` is native reportlab (this is the
  source of truth that LibreOffice is no longer used). Read-only here; it also defines
  the cv dict keys the new example file must contain.
- `docs/SETUP.md` — onboarding checklist; step 3 has the broken `cp` and a stale
  optional-LibreOffice step.
- `README.md` — "Configure it for you" section references the missing example and the
  "skill" wording.
- `.gitignore` — ignores private CV files but lacks a negation for the example.
- `engine/config.py` — `load_master_cv()` returns `{}` when neither private nor
  example file exists.
- `engine/paths.py` — `example_fallback()` resolves `<name>.example<suffix>` siblings.

Exact code as it exists at the planned-at commit (the stale "before" — what this
change replaced):

`engine/cli.py:124-134` (tailor command — stale LibreOffice text):
```python
@app.command()
def tailor(job_id: str,
           language: str = typer.Option("en", help="CV language: en | es"),
           pdf: bool = typer.Option(True, help="Also render a PDF (needs LibreOffice).")) -> None:
    """Generate a parse-safe, JD-tailored CV for a job (DOCX + optional PDF)."""
    from engine.cv.build import build_for_job
    with _db() as db:
        res = build_for_job(db, job_id, language=language, make_pdf=pdf)
    console.print(f"[bold]CV built[/] for {job_id}  (ATS: {res.ats_target})")
    console.print(f"  DOCX: {res.docx_path}")
    console.print(f"  PDF:  {res.pdf_path or '[yellow]skipped (LibreOffice not found)[/]'}")
```

`engine/cli.py:234-241` (advise command — "skill" wording; note line 235 prints the
LITERAL path and must NOT change):
```python
    s = result["summary"]
    console.print(f"[bold]Auditoría del CV[/] — {s['high']} altas · {s['med']} medias · {s['low']} bajas")
    ...
    console.print("\nPara la mejora completa (IA-forward, LinkedIn), corre el skill "
                  "[bold]cv-linkedin-advisor[/] (advisor/cv_linkedin_advisor.md).")
```

`engine/outreach/build.py:88-90` (stale LibreOffice fallback):
```python
        f"**CV (DOCX):** {cv.get('path_docx') or '—'}",
        f"**CV (PDF):** {cv.get('path_pdf') or '— (genera con LibreOffice)'}",
        "",
```

`engine/cv/render.py:140-141` (source of truth — PDF is native, no LibreOffice):
```python
def render_pdf(cv: dict, out_path: Path, language: str = "en") -> Optional[Path]:
    """Render a clean single-column PDF (reportlab — no LibreOffice/Word needed)."""
```

`docs/SETUP.md:22-23` (broken `cp` + "skill" wording):
```
- [ ] **Master CV:** `cp profile/master_cv.example.yaml profile/master_cv.yaml`, then run the
      `cv-linkedin-advisor` skill (it reads your LinkedIn via Claude in Chrome + your Claude
```

`docs/SETUP.md:32-33` (stale optional-LibreOffice step):
```
- [ ] **(Optional) PDF export:** install LibreOffice so `atlas tailor` can also emit a PDF
      (DOCX is the ATS-preferred default and always produced).
```

`README.md:91-92` (missing example + "skill" wording):
```
- `profile/master_cv.yaml` — your structured CV (seed it via the `cv-linkedin-advisor` skill /
  Claude in Chrome). Copy from `master_cv.example.yaml`.
```

`README.md:83` ("skill" wording in the command table):
```
| `atlas advise [--json]` | Audit your CV; pairs with the `cv-linkedin-advisor` skill |
```

`.gitignore:1-9` (no negation for the example — the glob on line 3 would ignore it):
```
# ── Personal data — NEVER commit (this is the whole point) ───────────────────
profile/master_cv.yaml
profile/master_cv.*.yaml
config/criteria.md
config/companies.yaml
config/sources.local.yaml
data/
!data/.gitkeep
*.db
```

`engine/config.py:20-25` (returns `{}` when neither private nor example exists —
why a missing example silently degrades the engine):
```python
def load_master_cv() -> dict:
    """Load the private master_cv.yaml, falling back to the committed example."""
    path = example_fallback(MASTER_CV_PATH)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}
```

CV dict keys the example file MUST contain (derived from reading both
`render_docx` and `render_pdf` in `engine/cv/render.py`; the example must exercise
every branch so a fresh user sees a complete sample CV):

- `basics`: object with `name`, `label`, `summary`, and the contact fields used by
  `_contact_line` (`engine/cv/render.py:36-39`): `email`, `phone`, `location`,
  `linkedin`, `github`, `website`.
- `skills`: list of strings (`render.py:74`, `:171`).
- `experience`: list of objects, each with `title`, `company`, `location`, `start`,
  `end`, `highlights` (list of strings) — `render.py:80-94`, `:174-183`.
- `education`: list of objects, each with `degree`, `area`, `institution`, `start`,
  `end` — `render.py:97-109`, `:184-191`.
- `certifications`: list of objects, each with `name`, `issuer`, `date` (only items
  with a truthy `name` are rendered) — `render.py:112-117`, `:192-196`.
- `projects`: list of objects, each with `name`, `description`, `highlights` (list
  of strings) — `render.py:120-129`, `:197-203`. Note `render_pdf` renders only
  `name` + `highlights` for projects; `render_docx` also renders `description`. Include
  all three so both renderers have data.

Conventions to match (this repo): typer CLI; pydantic v2 models; `rich.console`
for output; `sqlite3` parameterized queries + WAL; `@dataclass` result objects;
`from __future__ import annotations` at the top of modules; sha1 16-char natural
keys; UPSERT + COALESCE gap-fill; existing tests live in `tests/test_engine.py`
(model any new test after those). None of these apply to this docs-only change
except: keep the YAML example in the same field-name vocabulary the renderer reads
(above), and keep Spanish wording in `engine/cli.py` `advise` output and
`engine/outreach/build.py` consistent with the surrounding Spanish strings.

## Commands you will need

| Purpose            | Command                                              | Expected on success                          |
|--------------------|------------------------------------------------------|----------------------------------------------|
| Python tests       | `uv run --extra dev pytest`                          | `9 passed`                                   |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors                            |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0, build completes                      |
| YAML parse check   | `uv run python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('profile/master_cv.example.yaml').read_text()); print('ok')"` | prints `ok` |
| Example resolves   | `uv run python -c "from engine.config import load_master_cv as f; d=f(); print(sorted(d))"` | non-empty list incl. `basics`, `experience` (only if private `profile/master_cv.yaml` absent) |

Do NOT use a bare `pytest` — the global interpreter is missing `docx`, `rapidfuzz`,
and `reportlab` and will falsely fail 2 tests. Always go through
`uv run --extra dev pytest`. (This matches the project rule to route tests through
the managed environment.)

## Scope

**In scope** (the only files you should modify/create):
- `engine/cli.py` — text only (help string + two `console.print` strings). No logic change.
- `engine/outreach/build.py` — text only (one fallback string). No logic change.
- `docs/SETUP.md`
- `README.md`
- `.gitignore`
- `profile/master_cv.example.yaml` — **new file**.

**Out of scope** (do NOT touch, even though they look related):
- `engine/cv/render.py` — already correct (native reportlab). Read-only reference for
  the example's keys.
- `engine/config.py`, `engine/paths.py` — the fallback logic already works; no change.
- `advisor/cv_linkedin_advisor.md` — do NOT rename or move it. `engine/cli.py:235`
  prints the literal path `advisor/cv_linkedin_advisor.md`; renaming would break that
  reference. The fix is wording in the docs/CLI, not the file.
- Any behavioral code, the `--pdf` default (stays `True`), the actual rendering, or
  the dashboard. The only `render.py` interaction is reading it to author the example.

## Git workflow

- Branch: `advisor/010-stale-docs-and-onboarding` (off the latest `main`/`master`).
- Commit per logical unit (e.g. one commit for the LibreOffice text, one for the
  seed file + gitignore, one for the advisor wording) or one squashed docs commit.
- Stage only the in-scope files by name — never `git add .` / `git add -A`.
- Do NOT push or open a PR. Merge to the default branch is decided by the operator.

## Steps

### Step 1: Remove stale LibreOffice text from `engine/cli.py`

In `engine/cli.py`, edit the `tailor` command (lines 124-134), text only:

- Line 127 `--pdf` help: change `"Also render a PDF (needs LibreOffice)."` to
  `"Also render a PDF (native — always produced)."` (or equivalent that drops
  LibreOffice and reflects that reportlab always emits the PDF).
- Line 134 fallback: change `'[yellow]skipped (LibreOffice not found)[/]'` to a
  message that no longer mentions LibreOffice — e.g. `'[yellow]not generated[/]'`.
  (The `or` fallback only fires if `res.pdf_path` is falsy; with native reportlab it
  normally won't, but keep a neutral fallback rather than a LibreOffice one.)

Do NOT touch line 135-141 logic or `make_pdf=pdf`.

**Verify**: `grep -rn "LibreOffice" engine/` → returns no matches in `.py` files
(matches inside `__pycache__/*.pyc` may appear from a stale build; ignore those, or
run `grep -rn --include='*.py' "LibreOffice" engine/` → no output).

### Step 2: Remove stale LibreOffice text from `engine/outreach/build.py`

In `engine/outreach/build.py:89`, change the PDF fallback string
`'— (genera con LibreOffice)'` to a neutral Spanish placeholder consistent with the
DOCX line above it (`'—'`) — e.g. `f"**CV (PDF):** {cv.get('path_pdf') or '—'}"`.
Text only; do not change surrounding list structure.

**Verify**: `grep -rn --include='*.py' "LibreOffice" engine/` → no output.

### Step 3: Add the `.gitignore` negation for the example file

In `.gitignore`, after the `profile/master_cv.*.yaml` line (line 3), add a negation so
the committed example is never ignored:
```
profile/master_cv.*.yaml
!profile/master_cv.example.yaml
```
Order matters: the negation must come AFTER the glob it overrides.

**Verify**: `git check-ignore -v profile/master_cv.example.yaml` → exits non-zero
(no output) meaning the path is NOT ignored. As a contrast,
`git check-ignore profile/master_cv.yaml` → prints the path (still ignored).

### Step 4: Create `profile/master_cv.example.yaml`

Create the new file `profile/master_cv.example.yaml` with a realistic, fully-populated
sample CV using exactly the keys the renderer reads (see "Current state" key list).
Use obvious placeholder values (e.g. `Jane Doe`, `jane@example.com`) so the user knows
to replace them, but make every section non-empty so both `render_docx` and
`render_pdf` exercise every branch. Required top-level keys: `basics` (with `name`,
`label`, `summary`, `email`, `phone`, `location`, `linkedin`, `github`, `website`),
`skills` (list), `experience` (list of objects with `title`, `company`, `location`,
`start`, `end`, `highlights`), `education` (list with `degree`, `area`, `institution`,
`start`, `end`), `certifications` (list with `name`, `issuer`, `date`), `projects`
(list with `name`, `description`, `highlights`).

**Verify**:
`uv run python -c "import yaml,pathlib; d=yaml.safe_load(pathlib.Path('profile/master_cv.example.yaml').read_text()); assert set(['basics','skills','experience','education','certifications','projects']) <= set(d), d.keys(); assert d['basics'].get('name'); print('ok')"`
→ prints `ok`.

### Step 5: Fix `docs/SETUP.md`

- Lines 22-23: the `cp` command is now valid (Step 4 created the source), so keep it.
  Change the "skill" wording: replace "run the `cv-linkedin-advisor` skill" with
  "follow the advisor doc (`advisor/cv_linkedin_advisor.md`)".
- Lines 32-33: rewrite the optional-LibreOffice step. PDF is now always produced
  natively, so this is no longer an optional install. Either delete the step or replace
  it with a note that the PDF is emitted automatically alongside the DOCX (no
  LibreOffice needed). Keep the surrounding checklist formatting (`- [ ]`).

**Verify**: `grep -n "LibreOffice\|cv-linkedin-advisor skill" docs/SETUP.md` → no output.

### Step 6: Fix `README.md`

- Line 83: change "pairs with the `cv-linkedin-advisor` skill" to "pairs with the
  advisor doc (`advisor/cv_linkedin_advisor.md`)".
- Lines 91-92: change "seed it via the `cv-linkedin-advisor` skill" to "seed it via the
  advisor doc (`advisor/cv_linkedin_advisor.md`)". Keep "Copy from `master_cv.example.yaml`."
  (now accurate after Step 4).

**Verify**: `grep -n "cv-linkedin-advisor\` skill\|cv-linkedin-advisor skill" README.md`
→ no output. And `grep -n "advisor/cv_linkedin_advisor.md" README.md` → at least 2 matches.

## Test plan

This is a docs/onboarding change with no behavioral code. No new unit tests are added.
The relevant guarantee is that nothing regressed:

- The full Python suite still passes: `uv run --extra dev pytest` → `9 passed`.
- The example YAML parses and resolves through `load_master_cv()` (covered by the
  YAML/resolve commands in the Commands table; only run the `load_master_cv` check in
  a clean checkout where no private `profile/master_cv.yaml` exists, since
  `example_fallback` prefers the private file when present).
- Frontend is untouched but verify it still builds/typechecks since this plan's Done
  criteria gate on it: `npm --prefix dashboard/frontend run typecheck` and
  `npm --prefix dashboard/frontend run build`.

If you want a structural pattern for any future test, model it after
`tests/test_engine.py`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn --include='*.py' "LibreOffice" engine/` → no output
- [ ] `grep -n "LibreOffice" docs/SETUP.md` → no output
- [ ] `git check-ignore -v profile/master_cv.example.yaml` → exits non-zero / no output (not ignored)
- [ ] `profile/master_cv.example.yaml` exists and parses (Step 4 verify prints `ok`)
- [ ] `grep -rn "cv-linkedin-advisor\b" README.md docs/SETUP.md` shows no occurrence preceded/followed by the word "skill" (the wording now says "advisor doc"); `engine/cli.py:226` and `:241` may still contain `cv-linkedin-advisor` as a literal label/path — that is allowed and out of scope
- [ ] `uv run --extra dev pytest` → `9 passed`
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0
- [ ] `npm --prefix dashboard/frontend run build` exits 0
- [ ] No files outside the in-scope list are modified (`git status` shows only:
      `engine/cli.py`, `engine/outreach/build.py`, `docs/SETUP.md`, `README.md`,
      `.gitignore`, and new `profile/master_cv.example.yaml`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts — e.g.
  `engine/cv/render.py:141` no longer says "no LibreOffice/Word needed", or the
  `.gitignore` glob `profile/master_cv.*.yaml` is gone (the codebase drifted since
  this plan was written).
- `engine/cli.py:235`/`:241` no longer prints the literal path
  `advisor/cv_linkedin_advisor.md` — the advisor file may have been renamed, which
  would change the correct wording and put you out of scope.
- Reading `engine/cv/render.py` reveals additional CV keys not listed here (the
  renderer gained new sections) — pause and reconcile the example file before writing it.
- `uv run --extra dev pytest` reports anything other than `9 passed`, or reports a
  collection error mentioning `docx`/`rapidfuzz`/`reportlab` (you ran the wrong
  interpreter — re-run via `uv run --extra dev pytest`, not bare `pytest`).
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (especially
  `advisor/cv_linkedin_advisor.md`, `engine/cv/render.py`, or `engine/config.py`).

## Maintenance notes

For the human/agent who owns this code after the change lands:

- If a future renderer change in `engine/cv/render.py` adds, removes, or renames a CV
  section/field, `profile/master_cv.example.yaml` must be updated in lockstep — it is
  the single committed sample that exercises every render branch and the fallback for
  `load_master_cv()`.
- If `advisor/cv_linkedin_advisor.md` is ever promoted to a real discoverable
  `SKILL.md`, revisit the "advisor doc" wording in `README.md`, `docs/SETUP.md`, and
  `engine/cli.py` — at that point "skill" becomes accurate again.
- The `.gitignore` negation `!profile/master_cv.example.yaml` must stay AFTER the
  `profile/master_cv.*.yaml` glob; reordering would re-ignore the example. A reviewer
  should confirm `git check-ignore` on both the example (not ignored) and a private
  `master_cv.es.yaml`-style file (still ignored).
- Reviewer focus: confirm no behavioral diff — the only `engine/*.py` hunks are string
  literals; the `--pdf` default stays `True` and no rendering logic changed.
- Deferred out of this plan: no renaming of the advisor file (kept to keep the literal
  CLI path reference valid); no change to the optional Adzuna / LibreOffice install
  steps beyond removing the now-obsolete LibreOffice line.
