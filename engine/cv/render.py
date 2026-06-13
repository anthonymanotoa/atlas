"""Render a CV dict to a parse-safe DOCX (and optional PDF).

Parse-safety rules baked in (from ATS-parser research): single column, standard
section headings, Month-YYYY dates, no tables/text-boxes/headers-footers/graphics,
contact info in the body, reverse-chronological. DOCX is the default (best parse rate).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

HEADINGS = {
    "en": {"summary": "Professional Summary", "skills": "Skills",
           "experience": "Experience", "education": "Education",
           "certs": "Certifications", "projects": "Projects"},
    "es": {"summary": "Resumen Profesional", "skills": "Habilidades",
           "experience": "Experiencia", "education": "Educación",
           "certs": "Certificaciones", "projects": "Proyectos"},
}


def _section(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)


def _contact_line(basics: dict) -> str:
    parts = [basics.get("email"), basics.get("phone"), basics.get("location"),
             basics.get("linkedin"), basics.get("github"), basics.get("website")]
    return "  |  ".join(p for p in parts if p)


def render_docx(cv: dict, out_path: Path, language: str = "en") -> Path:
    h = HEADINGS.get(language, HEADINGS["en"])
    basics = cv.get("basics", {}) or {}
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Pt(40)
        section.left_margin = section.right_margin = Pt(54)

    # Name + target title + contact (all in the body, no header/footer).
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = name_p.add_run(basics.get("name", ""))
    r.bold = True
    r.font.size = Pt(20)
    if basics.get("label"):
        lp = doc.add_paragraph()
        lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lr = lp.add_run(basics["label"])
        lr.italic = True
        lr.font.size = Pt(12)
    cp = doc.add_paragraph(_contact_line(basics))
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Summary
    if basics.get("summary"):
        _section(doc, h["summary"])
        doc.add_paragraph(" ".join(basics["summary"].split()))

    # Skills (single inline line — no tables/columns)
    skills = cv.get("skills") or []
    if skills:
        _section(doc, h["skills"])
        doc.add_paragraph("  ·  ".join(skills))

    # Experience (reverse-chron as authored)
    exp = cv.get("experience") or []
    if exp:
        _section(doc, h["experience"])
        for e in exp:
            head = doc.add_paragraph()
            hr = head.add_run(f"{e.get('title','')} — {e.get('company','')}")
            hr.bold = True
            meta = "  |  ".join(p for p in [e.get("location"),
                    f"{e.get('start','')} – {e.get('end','')}".strip(" –")] if p)
            if meta:
                mp = head.add_run(f"\n{meta}")
                mp.italic = True
                mp.font.size = Pt(10)
            for hl in e.get("highlights") or []:
                doc.add_paragraph(" ".join(hl.split()), style="List Bullet")

    # Education
    edu = cv.get("education") or []
    if edu:
        _section(doc, h["education"])
        for ed in edu:
            line = " ".join(p for p in [
                ed.get("degree"), ed.get("area"), "—" if ed.get("institution") else None,
                ed.get("institution")] if p)
            dates = f"{ed.get('start','')} – {ed.get('end','')}".strip(" –")
            p = doc.add_paragraph()
            p.add_run(line).bold = True
            if dates:
                dr = p.add_run(f"  ({dates})")
                dr.font.size = Pt(10)

    # Certifications
    certs = [c for c in (cv.get("certifications") or []) if c.get("name")]
    if certs:
        _section(doc, h["certs"])
        for c in certs:
            txt = " — ".join(p for p in [c.get("name"), c.get("issuer"), c.get("date")] if p)
            doc.add_paragraph(txt, style="List Bullet")

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


def _soffice() -> Optional[str]:
    for cand in ("soffice", "libreoffice",
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        path = shutil.which(cand) if "/" not in cand else (cand if Path(cand).exists() else None)
        if path:
            return path
    return None


def render_pdf(docx_path: Path) -> Optional[Path]:
    """Best-effort DOCX→PDF via LibreOffice headless. Returns None if unavailable."""
    soffice = _soffice()
    if not soffice:
        return None
    try:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir",
                        str(docx_path.parent), str(docx_path)],
                       check=True, capture_output=True, timeout=90)
    except (subprocess.SubprocessError, OSError):
        return None
    pdf = docx_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None
