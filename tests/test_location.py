"""On-site location gate: a confirmed on-site posting must be in one of criteria.onsite_locations
(e.g. Ecuador only); remote postings are exempt (remote is worldwide). Undetermined → kept."""

from __future__ import annotations

from engine.config import Criteria
from engine.scoring.fit import score_job

_EC_ONSITE = Criteria(
    roles=["arquitecto", "architect"],
    onsite_locations=["ecuador", ", ec", "guayaquil", "loja"],
    remote_required=False,
    languages=["es", "en"],
)


def test_onsite_job_outside_locations_is_disqualified():
    us = {"title": "Architect", "description": "x", "location": "Miami, FL", "is_remote": 0}
    assert score_job(us, _EC_ONSITE).disqualified is True


def test_onsite_job_inside_locations_survives():
    # Ecuadorian listings come through as "City, Province, EC" (country code), not "Ecuador".
    ec = {"title": "Arquitecto", "description": "x", "location": "Guayaquil, G, EC", "is_remote": 0}
    assert score_job(ec, _EC_ONSITE).disqualified is False


def test_remote_job_is_exempt_worldwide():
    remote_anywhere = {"title": "Arquitecto", "description": "x", "location": "Madrid, ES", "is_remote": 1}
    assert score_job(remote_anywhere, _EC_ONSITE).disqualified is False


def test_undetermined_location_or_remote_is_not_filtered():
    unknown = {"title": "Arquitecto", "description": "x", "location": "Bogotá, Colombia"}  # is_remote unset
    assert score_job(unknown, _EC_ONSITE).disqualified is False


def test_no_onsite_locations_means_no_gate():
    crit = Criteria(roles=["architect"], onsite_locations=[], remote_required=False)
    us = {"title": "Architect", "description": "x", "location": "Miami, FL", "is_remote": 0}
    assert score_job(us, crit).disqualified is False  # gate off when unset
