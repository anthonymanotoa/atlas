"""Characterization tests for the ATS parsers.

These lock the *current observed* field mapping of each keyless ATS source by
feeding a saved JSON fixture through an offline stub client (no network). If a
vendor renames a field or a mapping drifts, the relevant assertion fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.config import CompanyTarget
from engine.discovery.ats import greenhouse, lever, smartrecruiters

FIX = Path(__file__).parent / "fixtures"


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}

    def raise_for_status(self):  # 200 → no-op
        return None

    def json(self):
        return self._payload


class _StubClient:
    """Returns queued payloads in call order; matches get_json's client.get(url, params=)."""

    def __init__(self, *payloads):
        self._queue = list(payloads)

    def get(self, url, params=None):
        return _StubResponse(self._queue.pop(0))


def _load(name):
    return json.loads((FIX / name).read_text())


def test_greenhouse_maps_fields_and_dehtmls():
    target = CompanyTarget(company="Acme", ats="greenhouse", token="acme")
    jobs = greenhouse.fetch(target, _StubClient(_load("greenhouse_jobs.json")))
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "greenhouse"
    assert j.source_job_id == "4012345"  # stringified id
    assert j.title == "Senior Data Scientist"  # stripped
    assert j.company == "Acme"
    assert j.location == "Remote - US"
    assert "Python" in j.description and "<" not in j.description  # de-HTML'd
    assert j.date_posted == "2026-06-01"  # 10-char slice
    assert j.raw["departments"] == ["Data", "Engineering"]


def test_lever_remote_salary_and_location_join():
    target = CompanyTarget(company="Acme", ats="lever", token="acme")
    jobs = lever.fetch(target, _StubClient(_load("lever_postings.json")))
    assert len(jobs) == 3
    remote, onsite, unknown = jobs

    # remote posting: tri-state True, salary interval canonicalized, list-location joined
    assert remote.is_remote is True and remote.workplace_type == "remote"
    assert remote.location == "Remote, US"  # the ", ".join branch
    assert remote.salary_interval == "yearly"  # "per-year-salary" → yearly
    assert remote.salary_min == 180000 and remote.salary_max == 220000

    # on-site posting: tri-state False
    assert onsite.is_remote is False and onsite.workplace_type == "on-site"
    assert onsite.location == "New York, NY"

    # workplaceType absent: tri-state None, workplace_type "unknown"
    assert unknown.is_remote is None and unknown.workplace_type == "unknown"


def test_smartrecruiters_remote_tristate_and_urls():
    target = CompanyTarget(company="Acme", ats="smartrecruiters", token="AcmeCorp")
    client = _StubClient(
        _load("smartrecruiters_postings.json"),
        _load("smartrecruiters_detail.json"),  # detail for posting-1
        _load("smartrecruiters_detail.json"),  # detail for posting-2
    )
    jobs = smartrecruiters.fetch(target, client)
    assert len(jobs) == 2
    remote, other = jobs
    assert remote.is_remote is True  # location.remote == true
    assert remote.title == "Senior Data Scientist"
    assert remote.url == "https://jobs.smartrecruiters.com/AcmeCorp/posting-1"
    assert remote.apply_url == "https://jobs.smartrecruiters.com/AcmeCorp/posting-1"
    assert "Python" in remote.description and "<" not in remote.description
    # second posting has no "remote" key → tri-state None
    assert other.is_remote is None
