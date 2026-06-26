"""Scoring reads the title-ladder + stretch vocabulary from Criteria, so non-data domains
(e.g. architecture, where 'Principal Architect' is a normal level) score correctly."""

from __future__ import annotations

from engine.config import Criteria
from engine.scoring.fit import score_job

ARCH = Criteria(
    roles=["architect"],
    remote_required=False,
    exclude_exec=False,
    stretch_terms=[],
    candidate_years=1,
)


def test_principal_architect_not_penalized_when_stretch_disabled():
    r = score_job({"title": "Principal Architect", "description": "Revit AutoCAD"}, ARCH)
    assert r.disqualified is False
    assert not any("staff/principal" in k.lower() for k in r.knockouts)


def test_director_of_design_not_dq_when_exec_allowed():
    r = score_job({"title": "Director of Design", "description": "architecture studio"}, ARCH)
    assert r.disqualified is False


def test_data_profile_still_penalizes_stretch():
    data = Criteria(roles=["data scientist"], candidate_years=5)  # defaults keep stretch ON
    r = score_job({"title": "Principal Data Scientist", "description": "ml"}, data)
    assert any("principal" in k.lower() for k in r.knockouts)  # label derives from matched term


def test_data_profile_still_dqs_exec():
    data = Criteria(roles=["data scientist"])  # exclude_exec defaults True
    r = score_job({"title": "Head of Data", "description": "lead the team"}, data)
    assert r.disqualified is True


def test_junior_title_not_dq_when_targeting_junior_roles():
    # Architecture explicitly targets "junior architect" — a Junior Architect posting must NOT
    # be hard-DQ'd as "under-qualified".
    arch = Criteria(roles=["architect", "junior architect"], remote_required=False)
    r = score_job({"title": "Junior Architect", "description": "Revit AutoCAD"}, arch)
    assert r.disqualified is False


def test_data_profile_still_dqs_junior():
    # A senior data candidate (roles don't include a junior term) still rejects junior postings.
    data = Criteria(roles=["data scientist"])
    r = score_job({"title": "Junior Data Scientist", "description": "ml"}, data)
    assert r.disqualified is True
