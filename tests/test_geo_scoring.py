"""Geo factor 2c + geo-mismatch 2d in the fit scorer (spec §5.2/§5.3). Fictional candidate."""

from __future__ import annotations

from engine.config import Criteria


def test_criteria_geo_defaults_are_off():
    c = Criteria()
    assert c.candidate_country == ""  # empty = geo factor OFF (never a real country default)
    assert c.acceptable_regions == ["worldwide"]
    assert c.geo_penalty == 12.0
    assert c.re_apply_window_days == 0
