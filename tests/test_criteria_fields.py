"""Per-profile fields that de-hardcode scoring/tuning/positioning from the 'data' persona."""

from __future__ import annotations

from engine.config import Criteria


def test_new_fields_have_backcompat_defaults():
    c = Criteria()
    # Title-ladder + stretch (defaults preserve today's data behavior).
    assert c.stretch_terms == ["staff", "principal", "distinguished", "fellow"]
    assert c.stretch_min_years == 8
    assert c.senior_terms == ["senior", "sr.", "sr ", "lead"]
    assert "director" in c.exec_terms and "chief" in c.exec_terms
    assert "junior" in c.junior_terms and "intern" in c.junior_terms
    # Positioning / advisor.
    assert c.repositioning_target == ""
    assert c.core_keywords == []
    # CV tuning constants, promoted to config.
    assert c.top_jd_keywords == 25
    assert c.max_skills == 18
    assert c.max_highlights_per_role == 4


def test_architecture_can_relax_ladder():
    c = Criteria(stretch_terms=[], exclude_exec=False, core_keywords=["revit", "bim"])
    assert c.stretch_terms == []
    assert c.exclude_exec is False
    assert c.core_keywords == ["revit", "bim"]
