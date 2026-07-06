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
