"""Geo factor 2c + geo-mismatch 2d in the fit scorer (spec §5.2/§5.3). Fictional candidate."""

from __future__ import annotations

from engine.config import Criteria
from engine.scoring.fit import score_job


def test_criteria_geo_defaults_are_off():
    c = Criteria()
    assert c.candidate_country == ""  # empty = geo factor OFF (never a real country default)
    assert c.acceptable_regions == ["worldwide"]
    assert c.geo_penalty == 12.0
    assert c.re_apply_window_days == 0


# Fictional candidate: a data engineer living in a LatAm country ("xx" stand-ins avoided —
# we use "ec" as an EXAMPLE value in tests only; the code default is "" = off).
_GEO = Criteria(
    roles=["data engineer"],
    candidate_country="ec",
    acceptable_regions=["latam", "worldwide"],
    remote_required=True,
)


def _job(**kw) -> dict:
    base = {
        "title": "Data Engineer",
        "description": "python pipelines",
        "is_remote": 1,
        "workplace_type": "remote",
    }
    base.update(kw)
    return base


def test_us_only_remote_is_penalized_never_dq():
    restricted = score_job(_job(geo_scope="us", geo_restriction="Remote — US only"), _GEO)
    open_ = score_job(_job(geo_scope="worldwide"), _GEO)
    assert restricted.disqualified is False
    assert open_.score - restricted.score == 12.0
    assert any(k.startswith("remoto restringido a US") for k in restricted.knockouts)


def test_scope_in_acceptable_region_not_penalized():
    latam = score_job(_job(geo_scope="latam"), _GEO)
    own = score_job(_job(geo_scope="ec"), _GEO)
    open_ = score_job(_job(geo_scope="worldwide"), _GEO)
    assert latam.score == own.score == open_.score


def test_unknown_or_missing_scope_never_penalized():
    unknown = score_job(_job(geo_scope="unknown"), _GEO)
    missing = score_job(_job(), _GEO)  # no geo_scope key at all (pre-F2 rows)
    open_ = score_job(_job(geo_scope="worldwide"), _GEO)
    assert unknown.score == missing.score == open_.score


def test_factor_off_without_candidate_country():
    crit = Criteria(roles=["data engineer"], remote_required=True)  # candidate_country=""
    r = score_job(_job(geo_scope="us"), crit)
    assert not any("remoto restringido" in k for k in r.knockouts)


def test_geo_penalty_is_configurable():
    crit = Criteria(
        roles=["data engineer"],
        candidate_country="ec",
        acceptable_regions=["latam"],
        remote_required=True,
        geo_penalty=20.0,
    )
    restricted = score_job(_job(geo_scope="us"), crit)
    open_ = score_job(_job(geo_scope="worldwide"), crit)
    assert open_.score - restricted.score == 20.0


def test_onsite_job_ignores_geo_factor():
    crit = Criteria(roles=["data engineer"], candidate_country="ec", remote_required=False)
    r = score_job(
        {"title": "Data Engineer", "description": "x", "is_remote": 0, "geo_scope": ""}, crit
    )
    assert not any("remoto restringido" in k for k in r.knockouts)
