"""Deterministic PDF page-count check — the machine-verifiable half of the brain's visual CV
review (F4 §7.2). The brain does the rest by READING the rendered PDF (orphaned headings,
mixed fonts) — that judgment is not deterministic and lives in brain/prompts/pdf_check.md.

$0, no LLM: this is pure file/byte inspection. Uses `pdfplumber` (already a project dependency,
see pyproject.toml) to count pages; if the library can't parse a given file it falls back to
counting `/Type /Page` objects in the raw bytes, which is exact for the single-column PDFs
engine/cv/render.py produces via reportlab."""

from __future__ import annotations

import re
from pathlib import Path


def _byte_scan_pages(data: bytes) -> int:
    """Count page objects in raw PDF bytes: `/Type /Page` NOT followed by `s` (which would be
    the `/Pages` tree node) or another letter. Exact for reportlab's flat single-column PDFs."""
    return len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", data))


def page_count(pdf_path: str | Path) -> int:
    """Number of pages in the rendered PDF. `0` when the file is missing or unreadable.

    Prefers `pdfplumber` (a declared dependency); falls back to a raw-bytes `/Type /Page` scan
    if the parser errors on the file (e.g. a minimal/hand-built PDF without an xref table)."""
    p = Path(pdf_path)
    if not p.exists():
        return 0
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(p)) as pdf:
            n = len(pdf.pages)
        if n > 0:
            return n
    except Exception:  # noqa: BLE001 — any parse/import failure falls back to the byte scan
        pass
    try:
        return _byte_scan_pages(p.read_bytes())
    except OSError:
        return 0


def check_page_count(pdf_path: str | Path, *, max_pages: int, tail_line_slack: int = 5) -> dict:
    """Fail when the CV spills past `max_pages`. `tail_line_slack` documents the human rule
    (a 3rd page with under N lines is still a fail); the deterministic gate here is the page
    count — the line judgment is the brain's when it reads the PDF (brain/prompts/pdf_check.md).

    Returns ``{"pages": int, "max_pages": int, "ok": bool, "reason": str}``."""
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
