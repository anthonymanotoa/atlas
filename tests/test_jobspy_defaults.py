"""JobSpy discovery carries no hardcoded US bias: country_indeed comes from sources.yaml,
not a baked-in 'USA' default."""

from __future__ import annotations

import sys
import types

from engine.discovery import jobspy_source


def _fake_jobspy(monkeypatch, captured: dict) -> None:
    fake = types.ModuleType("jobspy")
    fake.scrape_jobs = lambda **k: captured.update(k) or None  # _df_records handles None
    monkeypatch.setitem(sys.modules, "jobspy", fake)


def test_indeed_country_not_hardcoded_usa(monkeypatch):
    captured: dict = {}
    _fake_jobspy(monkeypatch, captured)
    jobspy_source.fetch({"sites": ["indeed"], "results_wanted": 1}, ["architect"])
    assert captured.get("country_indeed") != "USA"  # no silent US default


def test_indeed_country_from_config(monkeypatch):
    captured: dict = {}
    _fake_jobspy(monkeypatch, captured)
    jobspy_source.fetch(
        {"sites": ["indeed"], "country_indeed": "Ecuador", "results_wanted": 1}, ["architect"]
    )
    assert captured.get("country_indeed") == "Ecuador"
