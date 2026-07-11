"""Deterministic review report (`review.md`) for a tailored CV — the reviewer half of a
drafter-reviewer pattern. Every check here is a pure, reproducible function over the rendered
DOCX/PDF and the master CV — NO LLM involved, NOTHING here is a judgment call. `tailor` and
`prep` (engine/cli.py) call `build_review` right after the CV is built and write the resulting
markdown next to the DOCX/PDF, so every generated CV ships with a machine-checked receipt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from engine.config import load_cv_layout
from engine.cv.parse_check import extract_text
from engine.cv.pdf_check import check_page_count
from engine.cv.placeholder import find_placeholders
from engine.cv.render import HEADINGS as RENDER_HEADINGS

MIN_CHARS = 400  # below this, the DOCX is almost certainly empty/broken text extraction
COVERAGE_THRESHOLD = 0.6  # advisory only — see build_review()
DEFAULT_MAX_PAGES = 2
# The seed master CV ships with the "Ada Lovelace" template identity (engine/cv/placeholder.py
# covers basics.* structurally); these are the literal strings that must never survive into a
# rendered CV's body text even if find_placeholders() didn't flag the source field.
_TEMPLATE_TOKENS = ("ada lovelace", "example.com")

_EM_DASH_LINE = re.compile(r"^(?P<left>.+?) — (?P<right>.+)$")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class ReviewResult:
    passed: bool  # all non-advisory checks ok
    checks: list[Check] = field(default_factory=list)
    markdown: str = ""


def _master_companies(master_cv: dict) -> set[str]:
    return {
        (exp.get("company") or "").strip().lower()
        for exp in (master_cv.get("experience") or [])
        if (exp.get("company") or "").strip()
    }


def _heading_labels(key: str, layout: dict) -> set[str]:
    """All known uppercased heading strings for `key` (both shipped languages plus any
    per-profile cv_layout.yaml override) — headings are rendered as `text.upper()`
    (engine/cv/render.py `_section`), so matching is done in that same case."""
    labels = {RENDER_HEADINGS[lang].get(key, "").upper() for lang in RENDER_HEADINGS}
    override = (layout.get("labels") or {}).get(key) or {}
    labels.update(v.upper() for v in override.values() if v)
    return {lbl for lbl in labels if lbl}


def _all_heading_labels(layout: dict) -> set[str]:
    labels: set[str] = set()
    for key in RENDER_HEADINGS["en"]:
        labels |= _heading_labels(key, layout)
    return labels


def _experience_block(text: str, layout: dict) -> str:
    """Lines between the Experience/Experiencia heading and the next section heading (or EOF).
    Scoping to this block keeps the anti-fabrication scan below from tripping on Licensure or
    Certifications lines, which also render as em-dash-joined `"X — Y"` text."""
    lines = text.splitlines()
    exp_labels = _heading_labels("experience", layout)
    all_labels = _all_heading_labels(layout)
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() in exp_labels:
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip() in all_labels:
            end = i
            break
    return "\n".join(lines[start:end])


def companies_in_text(text: str, layout: dict | None = None) -> list[str]:
    """Extract company names from `"Title — Company"` experience-header lines (the exact format
    engine/cv/render.py emits for each experience entry), scoped to the Experience section.

    LIMITATION (documented, not silently swept under the rug): this is a line-shape heuristic,
    not a name-entity recognizer. It skips the `location | dates` meta line (has a "|") and
    anything that reads like prose (ends in "." or is long), but a highlight bullet that happens
    to contain a short, period-free " — " clause could still be misread as a header line. That
    tradeoff is intentional — a deterministic scan over free text cannot be a perfect NER, and
    false positives here just mean an extra name to eyeball in review.md, never a missed one.
    """
    layout = layout or load_cv_layout()
    block = _experience_block(text, layout)
    companies: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or "|" in line or line.endswith("."):
            continue
        m = _EM_DASH_LINE.match(line)
        if not m:
            continue
        left, right = m.group("left").strip(), m.group("right").strip()
        if not left or not right or len(left) > 80 or len(right) > 80:
            continue
        companies.append(right)
    return companies


def check_no_fabricated_companies(
    text: str, master_cv: dict, layout: dict | None = None
) -> tuple[bool, list[str]]:
    """Anti-fabrication lock (check 4): every company found by `companies_in_text` must exist in
    `master_cv["experience"]`. Deterministic tailoring (engine/cv/tailor.py) only reorders skills
    and re-ranks highlights — it deep-copies the master's experience entries verbatim and never
    invents a new employer — so on real pipeline output this check is a tautology-by-construction.
    It stays meaningful (capable of failing) because it re-derives the company list from the
    RENDERED TEXT rather than trusting the pipeline, catching a future regression that lets an
    override or a bug slip in an employer the master CV doesn't have.
    """
    master_companies = _master_companies(master_cv)
    found = companies_in_text(text, layout)
    foreign = [c for c in found if c.lower() not in master_companies]
    return (len(foreign) == 0), foreign


def _render_markdown(job: dict, checks: list[Check], advisory: set[str]) -> str:
    title = (job or {}).get("title") or ""
    company = (job or {}).get("company") or ""
    heading = " — ".join(p for p in (title, company) if p)
    lines = [f"# Revisión determinista del CV{f' — {heading}' if heading else ''}", ""]
    for c in checks:
        icon = "✅" if c.ok else "⚠️"
        tag = " _(informativo)_" if c.name in advisory else ""
        lines.append(f"- {icon} **{c.name}**{tag}: {c.detail}")
    lines.append("")
    return "\n".join(lines)


def build_review(
    docx_path: Path,
    pdf_path: Path | None,
    master_cv: dict,
    job: dict,
    coverage: dict,
) -> ReviewResult:
    """Run all deterministic checks over one tailored CV and render `review.md`.

    `coverage` is the JD-keyword coverage report from `tailor.TailorResult` /
    `build.BuildResult`, shaped `{"coverage": float, "matched": [...], "missing": [...]}`.
    """
    layout = load_cv_layout()
    text = extract_text(docx_path)
    checks: list[Check] = []

    # 1 — texto extraíble
    n_chars = len(text)
    checks.append(
        Check(
            "Texto extraíble",
            n_chars >= MIN_CHARS,
            f"{n_chars} caracteres extraídos del DOCX (mínimo {MIN_CHARS})"
            if n_chars >= MIN_CHARS
            else f"Solo {n_chars} caracteres extraídos (mínimo {MIN_CHARS}) — "
            "el DOCX puede estar vacío o mal formado para un ATS",
        )
    )

    # 2 — bloque de contacto (email del master presente en el texto extraído)
    email = ((master_cv.get("basics") or {}).get("email") or "").strip()
    has_email = bool(email) and email.lower() in text.lower()
    checks.append(
        Check(
            "Bloque de contacto",
            has_email,
            f"Email del master ({email}) encontrado en el texto extraído"
            if has_email
            else f"El email del master ({email or 'no definido en master_cv'}) NO aparece "
            "en el texto extraído",
        )
    )

    # 3 — sin placeholders (Task 1's structural check + a literal scan of the rendered text)
    master_placeholders = find_placeholders(master_cv)
    low = text.lower()
    literal_hits = [tok for tok in _TEMPLATE_TOKENS if tok in low]
    placeholders_ok = not master_placeholders and not literal_hits
    detail3_parts = []
    if master_placeholders:
        detail3_parts.append("master_cv: " + "; ".join(master_placeholders))
    if literal_hits:
        detail3_parts.append("texto renderizado contiene: " + ", ".join(literal_hits))
    checks.append(
        Check(
            "Sin placeholders",
            placeholders_ok,
            "Sin restos de la plantilla (Ada Lovelace / example.com)"
            if placeholders_ok
            else " | ".join(detail3_parts),
        )
    )

    # 4 — anti-fabricación (empresas del CV adaptado ⊆ empresas del master)
    fab_ok, foreign = check_no_fabricated_companies(text, master_cv, layout)
    checks.append(
        Check(
            "Anti-fabricación (empresas)",
            fab_ok,
            "Todas las empresas listadas en Experiencia existen en el master_cv "
            "(chequeo por línea 'Título — Empresa'; ver limitación documentada en "
            "engine/cv/review_report.py::companies_in_text)"
            if fab_ok
            else "Empresa(s) en el CV renderizado que NO están en master_cv.experience: "
            + ", ".join(foreign),
        )
    )

    # 5 — cobertura de keywords (ADVISORY — informative signal, not a hard gate: the JD may list
    # nice-to-haves the candidate genuinely lacks, and tailor.py already refuses to invent them)
    cov = float((coverage or {}).get("coverage") or 0.0)
    missing = (coverage or {}).get("missing") or []
    cov_ok = cov >= COVERAGE_THRESHOLD
    detail5 = f"{cov:.0%} de cobertura de keywords de la vacante"
    if missing:
        detail5 += " — faltan: " + ", ".join(missing[:10])
    checks.append(Check("Cobertura de keywords", cov_ok, detail5))

    # 6 — páginas dentro del límite
    max_pages = layout.get("max_pages") or DEFAULT_MAX_PAGES
    if pdf_path:
        pc = check_page_count(pdf_path, max_pages=max_pages)
        checks.append(Check("Páginas", pc["ok"], pc["reason"]))
    else:
        checks.append(
            Check("Páginas", False, "No se generó PDF — no se pudo verificar el conteo de páginas")
        )

    advisory = {"Cobertura de keywords"}
    passed = all(c.ok for c in checks if c.name not in advisory)
    markdown = _render_markdown(job, checks, advisory)
    return ReviewResult(passed=passed, checks=checks, markdown=markdown)
