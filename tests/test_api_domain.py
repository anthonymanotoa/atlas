"""The dashboard API exposes the active profile's domain + target label so the UI can drop
its hardcoded 'reposition toward AI/ML' copy and read the profile instead."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_onboarding_exposes_domain_and_target(atlas_app):
    with TestClient(atlas_app) as client:
        data = client.get("/api/onboarding").json()
    assert data.get("domain") == "data"  # legacy/default profile resolves to 'data'
    assert "target_label" in data  # short label for "toward X" copy (may be empty)


def test_target_label_empty_when_no_repositioning(atlas_app, monkeypatch):
    # An architecture profile has repositioning_target="" — onboarding must NOT fall back to the
    # CV headline (which would read "reposiciónate hacia Arquitecta"); empty → neutral copy.
    import engine.config as cfg
    from engine.config import Criteria

    monkeypatch.setattr(cfg, "load_criteria", lambda: Criteria(repositioning_target=""))
    monkeypatch.setattr(cfg, "load_master_cv", lambda: {"basics": {"label": "Arquitecta"}})
    with TestClient(atlas_app) as client:
        data = client.get("/api/onboarding").json()
    assert data["target_label"] == ""


def test_profiles_entries_carry_domain(atlas_app):
    # list_profiles entries include a 'domain' key once any profile exists; the route shape
    # always includes the 'active' pointer.
    with TestClient(atlas_app) as client:
        data = client.get("/api/profiles").json()
    assert "profiles" in data and "active" in data
    for p in data["profiles"]:
        assert "domain" in p
