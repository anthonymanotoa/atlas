"""F3 §6.5: reverse ATS discovery — probing honesto de candidatas contra boards públicos."""

from __future__ import annotations

import httpx

from engine.config import Criteria
from engine.discovery import reverse

CRIT = Criteria(roles=["data scientist"])


def test_slug_candidates():
    assert reverse.slug_candidates("Acme Corp") == ["acmecorp", "acme-corp", "acme"]
    assert reverse.slug_candidates("Acme") == ["acme"]


def _fake_get_json(payloads: dict[str, object]):
    """URL → payload; cualquier otra URL simula 404."""

    def fake(client, url, params=None, retries=2):
        if url in payloads:
            return payloads[url]
        raise httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", url), response=httpx.Response(404)
        )

    return fake


def test_probe_company_finds_greenhouse_board(monkeypatch):
    gh_url = reverse.GREENHOUSE_URL.format(token="acmecorp")
    monkeypatch.setattr(
        reverse,
        "get_json",
        _fake_get_json({gh_url: {"jobs": [{"title": "Senior Data Scientist"}, {"title": "Chef"}]}}),
    )
    hit = reverse.probe_company("Acme Corp", client=None)
    assert hit == {
        "company": "Acme Corp",
        "ats": "greenhouse",
        "token": "acmecorp",
        "jobs_count": 2,
        "titles": ["Senior Data Scientist", "Chef"],
    }


def test_probe_company_falls_through_to_lever(monkeypatch):
    lever_url = reverse.LEVER_URL.format(token="acme")
    monkeypatch.setattr(
        reverse, "get_json", _fake_get_json({lever_url: [{"text": "Data Scientist"}]})
    )
    hit = reverse.probe_company("Acme", client=None)
    assert hit and hit["ats"] == "lever" and hit["titles"] == ["Data Scientist"]


def test_probe_company_none_when_no_board(monkeypatch):
    monkeypatch.setattr(reverse, "get_json", _fake_get_json({}))
    assert reverse.probe_company("Ghost Startup", client=None) is None


def test_suggest_companies_filters_by_role_terms_and_known(monkeypatch):
    gh_acme = reverse.GREENHOUSE_URL.format(token="acmecorp")
    gh_beta = reverse.GREENHOUSE_URL.format(token="betabakery")
    monkeypatch.setattr(
        reverse,
        "get_json",
        _fake_get_json(
            {
                gh_acme: {"jobs": [{"title": "Staff Data Scientist"}]},
                gh_beta: {"jobs": [{"title": "Pastry Chef"}]},  # sin match de rol → fuera
            }
        ),
    )
    monkeypatch.setattr(reverse, "load_companies", lambda: [])
    out = reverse.suggest_companies(["Acme Corp", "Beta Bakery", "  "], CRIT, client=None)
    assert len(out) == 1
    assert out[0]["company"] == "Acme Corp"
    assert out[0]["matching_titles"] == ["Staff Data Scientist"]


def test_suggest_companies_skips_already_configured(monkeypatch):
    from engine.config import CompanyTarget

    monkeypatch.setattr(
        reverse,
        "load_companies",
        lambda: [CompanyTarget(company="Acme Corp", ats="greenhouse", token="x")],
    )
    called = []
    monkeypatch.setattr(reverse, "probe_company", lambda n, c: called.append(n))
    assert reverse.suggest_companies(["Acme Corp"], CRIT, client=None) == []
    assert called == []  # ni siquiera se probó


def test_discovery_seeds_files_exist():
    from pathlib import Path

    for pack in ("default", "data", "architecture"):
        assert (Path("config/seeds") / pack / "discovery_seeds.yaml").exists()
