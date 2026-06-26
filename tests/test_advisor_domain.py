"""The CV audit is domain-driven: positioning nudges are gated on criteria.repositioning_target
and 'core terms' come from criteria.core_keywords — no hardcoded data/AI assumptions."""

from __future__ import annotations

from engine.advisor import audit_cv
from engine.config import Criteria

ARCH_CV = {
    "basics": {
        "email": "a@b.c",
        "linkedin": "x",
        "summary": "Arquitecta con experiencia en Revit, AutoCAD y rehabilitacion patrimonial "
        "que entrega documentacion tecnica y modelos BIM con 3 anios de practica.",
    },
    "skills": ["Revit", "AutoCAD", "Lumion", "ArchiCAD"],
    "experience": [
        {"title": "Dibujante", "company": "P&P", "highlights": ["Produje 12 planos", "Coordine 3 obras"]}
    ],
}


def test_no_repositioning_findings_when_target_empty():
    arch = Criteria(repositioning_target="", core_keywords=["revit", "autocad", "bim"])
    findings = audit_cv(ARCH_CV, arch)
    assert not any("posicionamiento" in f.area.lower() for f in findings)
    blob = " ".join(f.message + " " + f.suggestion for f in findings)
    assert "IA" not in blob and "IA/ML" not in blob


def test_core_terms_come_from_criteria_not_hardcoded_data():
    bare = {"basics": {"email": "a@b.c"}, "skills": [], "experience": []}
    findings = audit_cv(bare, Criteria(core_keywords=["revit", "bim"]))
    core_finding = next((f for f in findings if "núcleo" in f.message), None)
    assert core_finding is not None
    assert "revit" in core_finding.message.lower()
    assert "python" not in core_finding.message.lower()


def test_core_keyword_covered_by_ontology_alias_not_flagged(monkeypatch):
    # A core term whose ALIAS appears in the CV (per the ontology) must not be reported missing.
    import engine.advisor as adv

    monkeypatch.setattr(adv, "load_ontology", lambda: {"machine learning": ["ml"]})
    cv = {
        "basics": {"email": "a@b.c", "linkedin": "x"},
        "skills": ["ML", "Python"],
        "experience": [{"title": "A", "company": "B", "highlights": ["Shipped 5 models"]}],
    }
    findings = adv.audit_cv(cv, Criteria(core_keywords=["machine learning"], repositioning_target=""))
    assert not any("núcleo" in f.message for f in findings)  # covered via alias 'ml'


def test_data_profile_keeps_repositioning_nudge():
    data = Criteria(repositioning_target="AI/ML", core_keywords=["python", "machine learning", "llm"])
    cv = {
        "basics": {"email": "a@b.c", "linkedin": "x", "summary": "Analista con foco en dashboards y reporting."},
        "skills": ["Excel", "Tableau"],
        "experience": [{"title": "Analyst", "company": "X", "highlights": ["Hice 5 reportes", "Subi 10%"]}],
    }
    findings = audit_cv(cv, data)
    assert any("AI/ML" in f.suggestion for f in findings)
