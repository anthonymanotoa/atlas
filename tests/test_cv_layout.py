"""CV section order/labels are per-domain (cv_layout.yaml): architecture puts Projects above
Experience and adds a Licensure/Registration section; data keeps its legacy order."""

from __future__ import annotations

from docx import Document

from engine.cv.render import render_docx

BASE = {
    "basics": {"name": "Lucy", "label": "Arquitecta", "summary": "Resumen profesional."},
    "skills": ["Revit", "AutoCAD"],
    "experience": [{"title": "Dibujante", "company": "P&P", "highlights": ["Produje planos"]}],
    "projects": [{"name": "Vivienda Sanchez", "highlights": ["Levantamiento integral"]}],
    "licensure": [{"title": "Arquitecta", "issuer": "UTPL", "status": "En tramite"}],
}


def _headings(docx_path) -> list[str]:
    return [p.text for p in Document(str(docx_path)).paragraphs]


def test_architecture_layout_projects_before_experience_and_licensure(tmp_path):
    layout = {
        "order": ["summary", "projects", "experience", "licensure"],
        "labels": {"licensure": {"es": "Licenciatura y Registro"}},
    }
    out = render_docx(BASE, tmp_path / "cv.docx", language="es", layout=layout)
    texts = _headings(out)
    assert texts.index("PROYECTOS") < texts.index("EXPERIENCIA")
    assert "LICENCIATURA Y REGISTRO" in texts
    # 'skills' is populated but not in this order → appended after the ordered sections,
    # never dropped (losing real data is worse than an extra, lower-priority section).
    assert "HABILIDADES" in texts
    assert texts.index("HABILIDADES") > texts.index("EXPERIENCIA")


def test_empty_proof_source_normalizes_to_none(tmp_path, monkeypatch):
    # An explicitly-empty proof_source must NOT be treated as the github default (which would
    # trigger a surprise live api.github.com fetch); it means "no proof section".
    import engine.paths as paths
    from engine.config import load_cv_layout

    p = tmp_path / "cv_layout.yaml"
    p.write_text('proof_source: ""\norder: [summary]\n')
    monkeypatch.setattr(paths, "CV_LAYOUT_PATH", p)
    assert load_cv_layout()["proof_source"] == "none"


def test_default_layout_keeps_legacy_order(tmp_path):
    out = render_docx(BASE, tmp_path / "cv.docx", language="en", layout=None)
    texts = _headings(out)
    assert texts.index("EXPERIENCE") < texts.index("PROJECTS")  # legacy order preserved
    assert "SKILLS" in texts


def test_populated_section_missing_from_order_is_appended_not_dropped(tmp_path):
    # A section with real data that the layout's `order` forgot must still render (appended),
    # never silently dropped — losing real CV data is worse than an extra section.
    cv = {**BASE, "certifications": [{"name": "BIM con Revit", "issuer": "X", "date": "2025"}]}
    layout = {"order": ["summary", "projects", "experience"], "labels": {}}
    out = render_docx(cv, tmp_path / "cv.docx", language="es", layout=layout)
    assert "CERTIFICACIONES" in _headings(out)
