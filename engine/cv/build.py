"""Tailor → render → parse-check → persist, for one job. Reused by CLI and the brain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import engine.paths as paths
from engine.config import load_master_cv, load_ontology
from engine.cv import parse_check, render, tailor
from engine.db.models import DB

# Languages the renderer supports. Also a hard guard: `language` is interpolated into the
# output filename (cv_{language}.docx), so anything outside this set is rejected before it
# can introduce path separators / traversal into the write path.
ALLOWED_LANGUAGES = {"en", "es"}


@dataclass
class BuildResult:
    job_id: str
    docx_path: Path
    pdf_path: Path | None
    coverage: float
    matched: list[str]
    missing: list[str]
    ats_target: str
    parse_ok: bool
    parse_issues: list[str]
    cv_version_id: int
    notes: list[str]


def build_for_job(
    db: DB,
    job_id: str,
    *,
    language: str = "en",
    cv_override: dict | None = None,
    make_pdf: bool = True,
) -> BuildResult:
    """Generate a tailored, parse-safe CV for `job_id`. `cv_override` lets the brain
    pass an LLM-reworded (still truthful) CV dict instead of the deterministic one."""
    if language not in ALLOWED_LANGUAGES:
        raise ValueError(f"unsupported language {language!r}; allowed: {sorted(ALLOWED_LANGUAGES)}")
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    master = load_master_cv()
    ontology = load_ontology()
    result = tailor.tailor(master, job, ontology)
    cv = cv_override or result.cv

    out_dir = paths.OUTBOX_DIR / job_id
    docx_path = out_dir / f"cv_{language}.docx"
    render.render_docx(cv, docx_path, language=language)
    pdf_path = (
        render.render_pdf(cv, out_dir / f"cv_{language}.pdf", language=language)
        if make_pdf
        else None
    )
    parse_ok, issues = parse_check.check(docx_path, cv, language=language)

    # Mirror a human-readable copy into the per-profile CV library so every tailored CV lands
    # in one browsable folder named by company/role (the canonical store stays under job_id/).
    from engine.cv.naming import copy_to_library

    cv_name = (master.get("basics") or {}).get("name")
    company, title = job.get("company"), job.get("title")
    copy_to_library(
        docx_path, cv_name=cv_name, company=company, title=title, language=language, fmt="docx"
    )
    if pdf_path:
        copy_to_library(
            pdf_path, cv_name=cv_name, company=company, title=title, language=language, fmt="pdf"
        )

    cv_version_id = db.add_cv_version(
        job_id,
        language=language,
        ats_target=result.ats_target,
        path_docx=str(docx_path),
        path_pdf=str(pdf_path) if pdf_path else None,
        keyword_coverage=result.coverage,
        matched=result.matched,
        missing=result.missing,
        parse_ok=parse_ok,
    )
    db.set_state(job_id, "tailored", {"coverage": result.coverage, "cv_version": cv_version_id})
    return BuildResult(
        job_id=job_id,
        docx_path=docx_path,
        pdf_path=pdf_path,
        coverage=result.coverage,
        matched=result.matched,
        missing=result.missing,
        ats_target=result.ats_target,
        parse_ok=parse_ok,
        parse_issues=issues,
        cv_version_id=cv_version_id,
        notes=result.notes,
    )
