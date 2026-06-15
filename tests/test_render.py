"""CV PDF/DOCX rendering: parse-safety + the no-overlapping-text regression guard.

The header bug this locks down: reportlab's ParagraphStyle defaults `leading` to a fixed
12pt, so a 19pt name with no explicit leading had a line box shorter than its glyphs and the
target-title line was drawn ON TOP of the name. We render a stress case (long name + long
title) and assert via per-character geometry that nothing overlaps the name's vertical band.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.cv import render

CV = {
    "basics": {
        "name": "Ada Lovelace",
        "label": "Senior Data Scientist, Retention & Experimentation (Remote, LATAM)",
        "email": "a@example.com",
        "phone": "+1 555 0100",
        "location": "Remote · Anytown, Argentina",
        "linkedin": "https://www.linkedin.com/in/example",
        "github": "https://github.com/example",
        "summary": "Senior data scientist with 5+ years in retention, experimentation and GenAI.",
    },
    "skills": ["SQL", "Python", "A/B Testing", "Large Language Models"],
    "experience": [
        {
            "title": "Senior Data Specialist",
            "company": "Acme Corp",
            "location": "Remote",
            "start": "Feb 2025",
            "end": "Present",
            "highlights": ["Own retention analytics (AOV, CVR, LTV) with SQL on Redshift."],
        }
    ],
    "education": [
        {
            "institution": "Example University",
            "degree": "B.Eng. Civil Engineering",
            "start": "2016",
            "end": "2021",
        }
    ],
    "certifications": [{"name": "dbt Fundamentals", "issuer": "dbt Labs", "date": "2023"}],
}


def test_pdf_renders(tmp_path: Path):
    out = render.render_pdf(CV, tmp_path / "cv.pdf", language="en")
    assert out is not None and out.exists() and out.stat().st_size > 1000


def test_pdf_header_has_no_overlapping_text(tmp_path: Path):
    """The name and the (long) target-title line must never collide — the exact bug the
    user reported as 'palabras se sobreescribían sobre otras'."""
    pdfplumber = pytest.importorskip("pdfplumber")
    out = render.render_pdf(CV, tmp_path / "cv.pdf", language="en")
    assert out is not None
    with pdfplumber.open(out) as pdf:
        chars = pdf.pages[0].chars
    big = [c for c in chars if c["size"] > 15]  # the 19pt name
    assert big, "name should render at a large font size"
    name_top = min(c["top"] for c in big)
    name_bottom = max(c["bottom"] for c in big)
    # No other glyph may share the name's vertical band (1pt epsilon for kerning/rounding).
    overlappers = [
        c
        for c in chars
        if c["size"] <= 15 and c["top"] < name_bottom - 1 and c["bottom"] > name_top + 1
    ]
    assert not overlappers, f"text overlaps the name band: {[c['text'] for c in overlappers][:10]}"


def test_cv_filename_is_company_aware_and_ascii_safe():
    from engine.cv.naming import cv_filename, slug

    fn = cv_filename("Ada Lovelace", "Açme Inc.", "Señor Data Scientist", "es", "pdf")
    assert fn == "Anthony_Manotoa__Acme_Inc__Senor_Data_Scientist__es.pdf"
    assert slug("Über Niño") == "Uber_Nino"  # accents transliterated, no spaces
    # never produces path separators / traversal, whatever the inputs
    assert "/" not in cv_filename("a/b", "../x", "..", "en", "pdf")
    assert cv_filename(None, None, None, "en", "pdf").endswith(".pdf")


def test_pdf_returns_none_on_failure(tmp_path: Path, monkeypatch):
    """A render failure returns None (callers persist path_pdf=None) rather than raising."""
    import reportlab.platypus as platypus

    class Boom:
        def __init__(self, *a, **k):
            pass

        def build(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(platypus, "SimpleDocTemplate", Boom)
    assert render.render_pdf(CV, tmp_path / "cv.pdf") is None
