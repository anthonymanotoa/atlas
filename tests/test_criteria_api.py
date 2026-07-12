"""GET/PUT /api/criteria: the wizard's read/write path for the active profile's criteria."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _redirect_criteria(monkeypatch, tmp_path):
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "config" / "criteria.md")


def test_get_criteria_returns_fields_and_prose(atlas_app, tmp_path, monkeypatch):
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        resp = client.get("/api/criteria")
    assert resp.status_code == 200
    body = resp.json()
    assert "candidate_country" in body["criteria"]
    assert "prose" not in body["criteria"]
    assert isinstance(body["prose"], str)


def test_put_criteria_roundtrip(atlas_app, tmp_path, monkeypatch):
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        got = client.get("/api/criteria").json()
        got["criteria"]["candidate_country"] = "ec"
        got["criteria"]["acceptable_regions"] = ["latam", "worldwide"]
        got["criteria"]["roles"] = ["data engineer"]
        resp = client.put(
            "/api/criteria", json={"criteria": got["criteria"], "prose": "# Mi búsqueda"}
        )
        assert resp.status_code == 200 and resp.json()["ok"] is True
        again = client.get("/api/criteria").json()
    assert again["criteria"]["candidate_country"] == "ec"
    assert again["criteria"]["acceptable_regions"] == ["latam", "worldwide"]
    assert "Mi búsqueda" in again["prose"]
    assert (tmp_path / "config" / "criteria.md").exists()


def test_put_criteria_rejects_invalid_payload(atlas_app, tmp_path, monkeypatch):
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        resp = client.put(
            "/api/criteria", json={"criteria": {"salary_floor_usd": "not-a-number"}, "prose": ""}
        )
    assert resp.status_code == 422


def test_put_invalid_does_not_corrupt_existing_file(atlas_app, tmp_path, monkeypatch):
    """A 422 must leave the existing criteria.md UNTOUCHED (never half-write a corrupt file)."""
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        # Persist a valid file first.
        good = client.get("/api/criteria").json()
        good["criteria"]["candidate_country"] = "ec"
        assert (
            client.put(
                "/api/criteria", json={"criteria": good["criteria"], "prose": "# Original"}
            ).status_code
            == 200
        )
        before = (tmp_path / "config" / "criteria.md").read_text()
        # Now push garbage: it must be rejected and the file left as-is.
        resp = client.put(
            "/api/criteria", json={"criteria": {"salary_floor_usd": "not-a-number"}, "prose": "# Bad"}
        )
        assert resp.status_code == 422
        after = (tmp_path / "config" / "criteria.md").read_text()
        reloaded = client.get("/api/criteria").json()
    assert after == before  # byte-for-byte identical — no partial write
    assert reloaded["criteria"]["candidate_country"] == "ec"
    assert "Original" in reloaded["prose"]


def test_put_preserves_prose_when_only_frontmatter_changes(atlas_app, tmp_path, monkeypatch):
    """A PUT that changes a frontmatter field but resends the prose keeps the body intact."""
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        # Seed a prose body.
        seed = client.get("/api/criteria").json()
        assert (
            client.put(
                "/api/criteria",
                json={"criteria": seed["criteria"], "prose": "# Contexto\n\nBusco algo remoto."},
            ).status_code
            == 200
        )
        # Change only a frontmatter field; resend the prose unchanged (wizard behavior).
        state = client.get("/api/criteria").json()
        state["criteria"]["salary_floor_usd"] = 80000.0
        assert (
            client.put(
                "/api/criteria", json={"criteria": state["criteria"], "prose": state["prose"]}
            ).status_code
            == 200
        )
        final = client.get("/api/criteria").json()
    assert final["criteria"]["salary_floor_usd"] == 80000.0
    assert "Busco algo remoto." in final["prose"]


def test_put_criteria_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.put(
            "/api/criteria",
            json={"criteria": {}, "prose": ""},
            headers={"origin": "https://evil.example.com"},
        )
    assert resp.status_code == 403
