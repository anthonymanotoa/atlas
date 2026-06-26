"""Per-profile language: a hard off-language filter + a profile-default output language, so a
Spanish-only profile (Lucy) searches/keeps only Spanish and generates its CV/messages in Spanish."""

from __future__ import annotations

from engine.config import Criteria
from engine.scoring.fit import score_job

_EN_JOB = {
    "title": "Architect",
    "description": (
        "We are seeking an architect to join our team. You will lead residential projects and "
        "work with our designers. The role requires experience with construction documents and "
        "the ability to manage your own deliverables for the team."
    ),
}
_ES_JOB = {
    "title": "Arquitecto",
    "description": "Buscamos un arquitecto para liderar proyectos residenciales de vivienda en obra.",
}


def test_language_hard_disqualifies_off_language_posting():
    es_only = Criteria(roles=["arquitecto"], languages=["es"], language_hard=True, remote_required=False)
    assert score_job(_EN_JOB, es_only).disqualified is True
    assert score_job(_ES_JOB, es_only).disqualified is False  # Spanish posting survives


def test_language_soft_does_not_disqualify_when_not_hard():
    es_soft = Criteria(roles=["arquitecto"], languages=["es"], remote_required=False)  # hard defaults False
    assert score_job(_EN_JOB, es_soft).disqualified is False  # penalized, not DQ'd


def test_default_language_is_profile_primary(monkeypatch):
    import engine.config as cfg

    monkeypatch.setattr(cfg, "load_criteria", lambda: cfg.Criteria(languages=["es"]))
    assert cfg.default_language() == "es"


def test_default_language_falls_back_to_en(monkeypatch):
    import engine.config as cfg

    monkeypatch.setattr(cfg, "load_criteria", lambda: cfg.Criteria(languages=[]))
    assert cfg.default_language() == "en"
