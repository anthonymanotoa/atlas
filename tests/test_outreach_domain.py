"""Outreach drafts take the candidate's identity from basics.pitch, not a hardcoded
'senior data scientist … e-commerce' persona."""

from __future__ import annotations

from engine.outreach.templates import build_package


def test_outreach_uses_pitch_not_hardcoded_ds():
    job = {"company": "Studio X", "title": "Junior Architect"}
    candidate = {
        "name": "Lucy P",
        "headline": "Arquitecta",
        "linkedin": "li",
        "pitch": {
            "identity_line": "una arquitecta junior enfocada en BIM y visualización",
            "role_noun": "arquitecta",
            "impact_domain": "diseño residencial y rehabilitación patrimonial",
            "value_verb": "diseño y documento",
        },
    }
    drafts = build_package(job, candidate, ["Revit", "AutoCAD"], language="es")
    bodies = " ".join(d.body for d in drafts).lower()
    assert "data scientist" not in bodies
    assert "e-commerce" not in bodies
    assert "arquitecta" in bodies


def test_outreach_neutral_without_pitch_en():
    job = {"company": "Studio X", "title": "Designer"}
    candidate = {"name": "Sam Lee", "headline": "Industrial Designer", "linkedin": "li"}
    drafts = build_package(job, candidate, [], language="en")
    bodies = " ".join(d.body for d in drafts).lower()
    assert "data scientist" not in bodies
    assert "industrial designer" in bodies
