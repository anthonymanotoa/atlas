"""Interview question banks are per-profile (interview_topics.yaml); they fall back to the
embedded data banks when a profile ships none, so the data profile is unchanged."""

from __future__ import annotations

from engine.interview import interview_prep

ARCH_TOPICS = {
    "behavioral": {
        "es": ["Cuéntame sobre tu portafolio y un proyecto del que estés orgulloso."],
        "en": ["Tell me about your portfolio and a project you're proud of."],
    },
    "role_topics": [
        {
            "keywords": ["architect", "bim", "revit"],
            "es": ["¿Cómo coordinas un modelo BIM entre disciplinas?"],
            "en": ["How do you coordinate a BIM model across disciplines?"],
        }
    ],
    "default_tech": {
        "es": ["Explícame las fases de un proyecto y tu aporte en cada una."],
        "en": ["Walk me through project phases and your contribution at each."],
    },
}


def test_role_questions_use_loaded_topics(monkeypatch):
    monkeypatch.setattr(interview_prep, "load_interview_topics", lambda: ARCH_TOPICS)
    qs = interview_prep._role_questions("BIM Architect", "Revit coordination", "es")
    assert any("BIM" in q for q in qs)
    assert not any("A/B test" in q for q in qs)  # the data bank is not used


def test_behavioral_uses_loaded_topics(monkeypatch):
    monkeypatch.setattr(interview_prep, "load_interview_topics", lambda: ARCH_TOPICS)
    bq = interview_prep._behavioral("es")
    assert any("portafolio" in q.lower() for q in bq)
    assert not any("IA/ML" in q for q in bq)


def test_falls_back_to_embedded_data_banks(monkeypatch):
    monkeypatch.setattr(interview_prep, "load_interview_topics", lambda: {})
    bq = interview_prep._behavioral("es")
    assert any("IA/ML" in q for q in bq)  # embedded data default preserved
    qs = interview_prep._role_questions("Data Scientist", "machine learning", "es")
    assert any("A/B test" in q for q in qs)
