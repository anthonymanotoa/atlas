"""Render a CV dict to a parse-safe DOCX (and optional PDF).

Parse-safety rules baked in (from ATS-parser research): single column, standard
section headings, Month-YYYY dates, no tables/text-boxes/headers-footers/graphics,
contact info in the body, reverse-chronological. DOCX is the default (best parse rate).
"""
from __future__ import annotations

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


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_pdf(cv: dict, out_path: Path, language: str = "en") -> Optional[Path]:
    """Render a clean single-column PDF (reportlab — no LibreOffice/Word needed)."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    h = HEADINGS.get(language, HEADINGS["en"])
    basics = cv.get("basics", {}) or {}
    name_s = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=19, alignment=TA_CENTER, spaceAfter=2)
    label_s = ParagraphStyle("label", fontName="Helvetica-Oblique", fontSize=11, alignment=TA_CENTER, textColor="#333333")
    contact_s = ParagraphStyle("contact", fontName="Helvetica", fontSize=9, alignment=TA_CENTER, textColor="#444444", spaceAfter=8)
    head_s = ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=11.5, textColor="#1a1a1a", spaceBefore=10, spaceAfter=3)
    body_s = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=13)
    role_s = ParagraphStyle("role", fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=5)
    meta_s = ParagraphStyle("meta", fontName="Helvetica-Oblique", fontSize=9, textColor="#555555", spaceAfter=2)
    bullet_s = ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.5, leading=12.5)

    story = [Paragraph(_esc(basics.get("name", "")), name_s)]
    if basics.get("label"):
        story.append(Paragraph(_esc(basics["label"]), label_s))
    story.append(Paragraph(_esc(_contact_line(basics)), contact_s))

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(_esc(" ".join(i.split())), bullet_s), leftIndent=12)
                             for i in items], bulletType="bullet", start="•", leftIndent=10)

    if basics.get("summary"):
        story += [Paragraph(h["summary"].upper(), head_s),
                  Paragraph(_esc(" ".join(basics["summary"].split())), body_s)]
    if cv.get("skills"):
        story += [Paragraph(h["skills"].upper(), head_s),
                  Paragraph("  ·  ".join(_esc(s) for s in cv["skills"]), body_s)]
    if cv.get("experience"):
        story.append(Paragraph(h["experience"].upper(), head_s))
        for e in cv["experience"]:
            story.append(Paragraph(f"{_esc(e.get('title',''))} — {_esc(e.get('company',''))}", role_s))
            meta = "  |  ".join(p for p in [_esc(e.get("location")),
                    f"{e.get('start','')} – {e.get('end','')}".strip(" –")] if p)
            if meta:
                story.append(Paragraph(meta, meta_s))
            if e.get("highlights"):
                story.append(bullets(e["highlights"]))
    edu = cv.get("education") or []
    if edu:
        story.append(Paragraph(h["education"].upper(), head_s))
        for ed in edu:
            line = " ".join(p for p in [ed.get("degree"), ed.get("area"),
                    "—" if ed.get("institution") else None, ed.get("institution")] if p)
            dates = f"{ed.get('start','')} – {ed.get('end','')}".strip(" –")
            story.append(Paragraph(f"<b>{_esc(line)}</b>" + (f"  ({dates})" if dates else ""), body_s))
    certs = [c for c in (cv.get("certifications") or []) if c.get("name")]
    if certs:
        story.append(Paragraph(h["certs"].upper(), head_s))
        story.append(bullets([" — ".join(p for p in [c.get("name"), c.get("issuer"), c.get("date")] if p)
                              for c in certs]))
    projects = cv.get("projects") or []
    if projects:
        story.append(Paragraph(h["projects"].upper(), head_s))
        for pr in projects:
            story.append(Paragraph(f"<b>{_esc(pr.get('name',''))}</b>", body_s))
            if pr.get("description"):  # parity with render_docx — PDF previously dropped this
                story.append(Paragraph(_esc(" ".join(pr["description"].split())), body_s))
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
