# Plan 012: PDF render no longer silently drops project descriptions (DOCX/PDF parity)

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the
> change for the record. It is written in the imperative as the spec that was
> executed; an executor re-running it against a clean tree should reproduce the
> same result.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- engine/cv/render.py tests/test_engine.py`
> If either in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug (subset of TECHDEBT-01)
- **Planned at**: commit `c3e2679`, 2026-06-13
- **Issue**: (none)

## Why this matters

`engine/cv/render.py` renders a CV dict to two artifacts: a DOCX (`render_docx`)
and a PDF (`render_pdf`). For the **Projects** section the two diverged:
`render_docx` emits the project name **plus its description** plus highlights,
while `render_pdf` emits the project name and highlights but **silently omits the
description**. The PDF is the file most users actually send to employers, so the
candidate's own project blurb — the sentence that frames each project — vanished
from the artifact that matters most, with no error and no warning. This plan
restores parity: the PDF Projects block emits the same escaped description the
DOCX does. Cost of the bug was a quietly weaker CV; the fix is a few lines plus a
regression test that locks the two renderers to the same content for Projects.

This is the concrete, shippable slice of TECHDEBT-01 (the broader observation
that `render_docx` and `render_pdf` duplicate all section-iteration logic and
will keep drifting). The full dedup refactor is **deferred** — see Maintenance
notes and Scope/Out.

## Current state

Files:

- `engine/cv/render.py` — single module that renders a CV dict to DOCX and PDF.
  Module docstring (lines 1–6) states the parse-safety contract; `HEADINGS`
  (lines 15–25) holds the `en`/`es` section titles including `"projects"`.
  Two public functions: `render_docx(cv, out_path, language="en")` and
  `render_pdf(cv, out_path, language="en")`. The Projects logic is duplicated
  between them and is where they diverge.
- `tests/test_engine.py` — network-free unit tests for the engine's guarantees.
  `test_parse_check_passes_for_rendered_cv` (lines 89–99) is the existing render
  test and the structural pattern to model the new test after.

### The DOCX Projects block (renders the description) — `engine/cv/render.py:119-133`

```python
    # Projects
    projects = cv.get("projects") or []
    if projects:
        _section(doc, h["projects"])
        for pr in projects:
            p = doc.add_paragraph()
            p.add_run(pr.get("name", "")).bold = True
            if pr.get("description"):
                doc.add_paragraph(" ".join(pr["description"].split()))
            for hl in pr.get("highlights") or []:
                doc.add_paragraph(" ".join(hl.split()), style="List Bullet")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
```

Note line 126–127: the description is emitted, whitespace-collapsed via
`" ".join(pr["description"].split())`.

### The `_esc` helper used by the PDF path — `engine/cv/render.py:136-137`

```python
def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

reportlab `Paragraph` text is mini-HTML, so any string fed to it must go through
`_esc` (and bold is expressed as `<b>...</b>`, as seen elsewhere in the function).

### The PDF Projects block (DROPS the description — the bug) — `engine/cv/render.py:197-212`

```python
    projects = cv.get("projects") or []
    if projects:
        story.append(Paragraph(h["projects"].upper(), head_s))
        for pr in projects:
            story.append(Paragraph(f"<b>{_esc(pr.get('name',''))}</b>", body_s))
            if pr.get("highlights"):
                story.append(bullets(pr["highlights"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER, topMargin=0.5 * inch,
                            bottomMargin=0.5 * inch, leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    try:
        doc.build(story)
    except Exception:  # noqa: BLE001
        return None
    return out_path if out_path.exists() else None
```

The loop goes straight from the name `Paragraph` (line 201) to the highlights
(lines 202–203). There is **no** `if pr.get("description")` branch — that is the
defect. `body_s` (defined at line 154:
`body_s = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=13)`)
is the correct style for a description paragraph, matching how `render_pdf`
renders the summary body at lines 168–170.

### Conventions this repo follows (match them)

- `from __future__ import annotations` at the top of every module
  (`render.py:8`, `tests/test_engine.py:6`).
- Python 3.11+. Package manager: `uv`. Tests live in `tests/test_engine.py` and
  are network-free; model any new test after the ones there.
- reportlab strings are escaped through `_esc(...)`; bold via `<b>...</b>` inline
  markup, never via a separate run.
- Whitespace in free text is collapsed with `" ".join(s.split())` before
  rendering (DOCX line 127; PDF summary line 170; `bullets()` helper line 165).
- Git: work on a branch `advisor/012-pdf-render-parity`. Do NOT push or open a PR.

### PDF text is NOT plain-text in the output bytes (load-bearing for the test)

reportlab compresses page content streams, so a substring search over
`out_path.read_bytes()` for the description text **returns False even when the
description is correctly rendered** (verified during recon). Additionally,
**no PDF text-extraction library is installed** in this repo's dev environment
(`pypdf` and `pdfminer` both raise `ModuleNotFoundError`). Therefore the
regression test must assert on the **in-memory list of flowables** the PDF is
built from, not on the output file's bytes. See Step 2 for how this is done
without adding a dependency.

## Commands you will need

| Purpose            | Command                                              | Expected on success                  |
|--------------------|------------------------------------------------------|--------------------------------------|
| Python tests       | `uv run --extra dev pytest`                          | exit 0; `9 passed` before, `10 passed` after the new test |
| Run one test       | `uv run --extra dev pytest tests/test_engine.py -k pdf` | the targeted test(s) pass         |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0 (unaffected — sanity only)    |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0 (unaffected — sanity only)    |

> Do NOT run a bare `pytest`. The global interpreter is missing `docx`,
> `rapidfuzz`, and `reportlab`, so bare `pytest` falsely fails 2 tests. Always
> use `uv run --extra dev pytest`, which resolves the project's dev extras.

The frontend commands are listed only as a no-regression sanity check; this plan
touches no frontend code and they should be unaffected.

## Scope

**In scope** (the only files you may modify):

- `engine/cv/render.py` — the `render_pdf` Projects block **only** (lines
  197–203). Add the description paragraph; change nothing else in the function.
- `tests/test_engine.py` — add one new test (see Step 2). Touch no existing test.

**Out of scope** (do NOT touch, even though they look related):

- The `render_docx`/`render_pdf` duplication refactor (single shared
  section-descriptor list consumed by both backends). This is the durable fix
  for TECHDEBT-01 but is explicitly **deferred** — it is a larger change with
  its own review surface and is tracked in `plans/README.md` as "TECHDEBT-01
  full". Do not attempt it here.
- Any other section in either renderer (summary, skills, experience, education,
  certifications) — they already match; do not "tidy" them.
- Output styling/margins/fonts of the PDF — no visual redesign.
- `dashboard/`, `brain/`, any frontend file.

## Git workflow

- Branch: `advisor/012-pdf-render-parity` (created from latest `origin/main`).
- One commit for the fix + its test is fine. Commit message style — short
  imperative subject, matching recent history (e.g. `c3e2679 Add one-command
  dashboard launcher (scripts/run.sh)`). Suggested:
  `cv/render: emit project description in PDF (DOCX/PDF parity)`.
- Stage only the two in-scope files **by name** (`git add engine/cv/render.py
  tests/test_engine.py`). Never `git add .` / `git add -A`.
- Do NOT push and do NOT open a PR. The operator merges.

## Steps

### Step 1: Emit the project description in the PDF Projects loop

In `engine/cv/render.py`, inside `render_pdf`, in the Projects block at lines
197–203, add a description paragraph **between** the name line and the highlights,
mirroring the DOCX behavior (lines 126–127) and the PDF summary body (lines
168–170). The block becomes:

```python
    projects = cv.get("projects") or []
    if projects:
        story.append(Paragraph(h["projects"].upper(), head_s))
        for pr in projects:
            story.append(Paragraph(f"<b>{_esc(pr.get('name',''))}</b>", body_s))
            if pr.get("description"):
                story.append(Paragraph(_esc(" ".join(pr["description"].split())), body_s))
            if pr.get("highlights"):
                story.append(bullets(pr["highlights"]))
```

Requirements that make this match repo conventions:

- Escape the text with `_esc(...)` (reportlab mini-HTML).
- Collapse whitespace with `" ".join(pr["description"].split())`, exactly as the
  DOCX path and the summary body do.
- Use `body_s` (line 154) as the style, matching the summary body paragraph.
- Guard with `if pr.get("description"):` so projects without a description are
  unchanged. Change nothing else in the function — same name line, same
  highlights call, same `doc.build` tail.

**Verify**: `uv run --extra dev pytest` → exits 0, still `9 passed` (no test
added yet; this confirms the edit did not break existing behavior).

### Step 2: Add a regression test asserting PDF/DOCX parity for the description

Add one test to `tests/test_engine.py`, modeled structurally on
`test_parse_check_passes_for_rendered_cv` (lines 89–99): build a small CV dict
that includes a project with a `description` containing a unique marker string,
render it, and assert the description reaches the PDF.

Because the output PDF's bytes are compressed and no PDF text-extraction library
is installed (see "Current state"), assert on the **in-memory flowables** rather
than the file. The lowest-friction way that requires **no production-code change
beyond Step 1** is to capture the flowables reportlab builds by monkeypatching
`SimpleDocTemplate.build` to record its `story` argument. Use the existing
`tmp_path` fixture and the project's escaping convention. Target shape:

```python
def test_pdf_render_includes_project_description(tmp_path: Path, monkeypatch):
    from reportlab.platypus import SimpleDocTemplate
    from engine.cv import render

    cv = {"basics": {"name": "Ana Tester", "email": "a@b.com"},
          "projects": [{"name": "Atlas",
                        "description": "Unique project blurb marker_xyzzy.",
                        "highlights": ["Shipped the engine"]}]}

    captured: list = []
    real_build = SimpleDocTemplate.build

    def spy_build(self, story, *a, **k):
        captured.append(story)
        return real_build(self, story, *a, **k)

    monkeypatch.setattr(SimpleDocTemplate, "build", spy_build)
    out = render.render_pdf(cv, tmp_path / "cv.pdf")
    assert out is not None and out.exists()

    flat = "  ".join(getattr(p, "text", "") for p in captured[0])
    assert "marker_xyzzy" in flat            # description reached the PDF story
    assert "Atlas" in flat                   # name still present
    assert "Shipped the engine" in flat      # highlight still present
```

Notes for the executor:

- `Paragraph` flowables expose their text via `.text`; `getattr(p, "text", "")`
  safely skips non-paragraph flowables (`Spacer`, `ListFlowable`). The highlight
  lives inside a `ListFlowable`, so to assert the highlight too you may instead
  flatten recursively, OR drop the highlight assertion and keep only the
  description+name assertions (the description is what this plan fixes). Either
  is acceptable; do not over-engineer. The **mandatory** assertion is that the
  description marker reaches the story.
- Do not add `pypdf`/`pdfminer` or any new dependency. If you find yourself
  wanting to parse the PDF file, stop — use the in-memory `captured[0]` instead.

**Verify**: `uv run --extra dev pytest tests/test_engine.py -k pdf` → the new
test passes. Then `uv run --extra dev pytest` → exits 0, `10 passed`.

### Step 3: Confirm the test actually guards the bug (regression sanity)

Temporarily revert the Step 1 edit (remove the new `if pr.get("description"):`
paragraph), run `uv run --extra dev pytest tests/test_engine.py -k pdf`, and
confirm the new test now **fails** (the description marker is absent). Re-apply
Step 1 and confirm it passes again. This proves the test is wired to the defect,
not to something else.

**Verify**: with Step 1 reverted → new test FAILS; with Step 1 reapplied →
`uv run --extra dev pytest` exits 0, `10 passed`. Leave the tree in the
reapplied (fixed) state.

## Test plan

- New test in `tests/test_engine.py`:
  `test_pdf_render_includes_project_description`. Cases covered:
  - happy path: a project with a description renders that description into the
    PDF story (the regression this plan fixes);
  - the project name and at least one other rendered token are still present
    (the fix added content, it did not replace anything).
- Structural pattern: model after `test_parse_check_passes_for_rendered_cv`
  (`tests/test_engine.py:89-99`) — same `tmp_path` usage, same
  `from engine.cv import render` import style, same dict-shaped fixture CV.
- Verification: `uv run --extra dev pytest` → all pass, `10 passed` (the 9
  pre-existing plus the 1 new test).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `git diff --stat c3e2679..HEAD -- engine/cv/render.py tests/test_engine.py`
      shows only those two files changed.
- [ ] `uv run --extra dev pytest` exits 0 and prints `10 passed`.
- [ ] `uv run --extra dev pytest tests/test_engine.py -k pdf` passes the new
      `test_pdf_render_includes_project_description`.
- [ ] `grep -n "pr\[.description.\]" engine/cv/render.py` returns **two** hits —
      one in `render_docx` (line ~127) and the new one in `render_pdf` — proving
      both renderers now reference the description.
- [ ] `grep -n "pypdf\|pdfminer" tests/test_engine.py` returns no matches (no new
      dependency was introduced).
- [ ] No files outside `engine/cv/render.py` and `tests/test_engine.py` are
      modified (`git status`).
- [ ] `plans/README.md` status row for plan 012 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The "Current state" excerpts for `render_pdf` (lines 197–203) or `render_docx`
  (lines 119–133) do not match the live code — the file drifted since c3e2679
  (the drift-check diff is non-empty for `engine/cv/render.py`).
- `uv run --extra dev pytest` reports anything other than `9 passed` **before**
  your changes — the baseline is not what this plan assumes; do not proceed.
- The new test passes even with Step 1 reverted (Step 3) — it is not actually
  guarding the description, so the test is wrong; fix the test before claiming
  done.
- Making the test pass appears to require touching `render_pdf` beyond the single
  added description paragraph, or any file outside the in-scope list.
- `render_pdf` already contains an `if pr.get("description")` branch — the bug
  was fixed independently; mark plan 012 REJECTED in `plans/README.md` ("fixed
  upstream") and stop.

## Maintenance notes

For whoever owns this code next:

- **The duplication is still there.** `render_docx` (lines 119–133) and
  `render_pdf` (lines 197–203) still iterate every CV section independently. This
  plan patched the one divergence that was already biting (Projects /
  description); it did **not** remove the structural risk. The two renderers
  **will drift again** the next time a section gains a field in one path but not
  the other.
- **The durable fix (deferred — TECHDEBT-01 full):** introduce a single ordered
  list of section descriptors (heading key, the CV sub-object, and the field map:
  title field, meta fields, body/description field, bullet field) and have both
  `render_docx` and `render_pdf` consume it through two thin backend adapters
  (one emitting `docx` paragraphs, one emitting reportlab flowables). Then adding
  a field is a one-line change that both artifacts honor automatically. Track and
  schedule this separately; it is intentionally out of scope here.
- **What a reviewer should scrutinize in this PR:** (1) the description is
  escaped via `_esc` and whitespace-collapsed exactly as the DOCX path does —
  unescaped text would break reportlab's mini-HTML parsing on `&`/`<`/`>`;
  (2) the new test asserts on the in-memory story, not on PDF bytes, and adds no
  `pypdf`/`pdfminer` dependency; (3) only the two in-scope files changed.
