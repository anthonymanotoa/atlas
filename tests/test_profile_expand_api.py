"""Endpoints de profile expansions (F4 §7.2): GET drafts + apply confirmed-only + origin guard.

$0: el backend nunca llama a un LLM — apply_items es mutación determinista del YAML del perfil.
Los tests apuntan MASTER_CV_PATH a un archivo temporal (nunca al perfil real commiteado).
"""

from __future__ import annotations

import yaml
from fastapi.testclient import TestClient


def _seed_expansion() -> int:
    from engine.db.models import DB

    items = [
        {"target": "skills", "value": "Rust", "source": "github.com/ada"},
        {"target": "skills", "value": "Python", "source": "github (existe)"},
        {
            "target": "certification",
            "value": {"name": "CKA", "issuer": "CNCF", "date": "2026"},
            "source": "cncf.io/cka",
        },
    ]
    with DB() as db:
        return db.add_profile_expansion(intent_id=None, items=items)


def _seed_master_cv(tmp_path, monkeypatch):
    import engine.paths as paths

    master = tmp_path / "master_cv.yaml"
    master.write_text(
        yaml.safe_dump(
            {"basics": {"name": "Ada"}, "skills": ["Python", "SQL"], "certifications": []},
            sort_keys=False,
        )
    )
    monkeypatch.setattr(paths, "MASTER_CV_PATH", master)
    return master


def test_get_profile_expansions_latest_first(atlas_app):
    with TestClient(atlas_app) as client:
        _seed_expansion()
        second = _seed_expansion()
        r = client.get("/api/profile-expansions")
        assert r.status_code == 200
        exps = r.json()["expansions"]
        assert len(exps) == 2
        assert exps[0]["id"] == second  # última primero


def test_apply_writes_only_confirmed_indices(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    master = _seed_master_cv(tmp_path, monkeypatch)
    with TestClient(atlas_app) as client:
        exp_id = _seed_expansion()
        # solo confirmamos el índice 0 (Rust) — la cert (índice 2) NO debe escribirse.
        r = client.post(f"/api/profile-expansions/{exp_id}/apply", json={"indices": [0]})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] and body["applied"] == 1 and body["skipped_existing"] == 0
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert "Rust" in cv["skills"]
    assert cv["certifications"] == []  # no confirmado → no escrito
    # el CV preexistente sigue intacto
    assert cv["basics"] == {"name": "Ada"}
    assert "Python" in cv["skills"] and "SQL" in cv["skills"]
    assert master.exists()


def test_apply_is_idempotent_and_skips_existing(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    _seed_master_cv(tmp_path, monkeypatch)
    with TestClient(atlas_app) as client:
        exp_id = _seed_expansion()
        r = client.post(f"/api/profile-expansions/{exp_id}/apply", json={"indices": [0, 1, 2]})
        body = r.json()
        assert body["applied"] == 2 and body["skipped_existing"] == 1  # Python ya existía
        again = client.post(f"/api/profile-expansions/{exp_id}/apply", json={"indices": [0]})
        assert again.json()["applied"] == 0 and again.json()["skipped_existing"] == 1
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert cv["skills"].count("Python") == 1  # no duplicó


def test_apply_unknown_expansion_is_404(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/profile-expansions/9999/apply", json={"indices": [0]})
    assert r.status_code == 404


def test_apply_out_of_range_index_is_400(atlas_app, tmp_path, monkeypatch):
    _seed_master_cv(tmp_path, monkeypatch)
    with TestClient(atlas_app) as client:
        exp_id = _seed_expansion()
        r = client.post(f"/api/profile-expansions/{exp_id}/apply", json={"indices": [99]})
    assert r.status_code == 400


def test_apply_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        exp_id = _seed_expansion()
        r = client.post(
            f"/api/profile-expansions/{exp_id}/apply",
            json={"indices": [0]},
            headers={"Origin": "https://evil.example"},
        )
    assert r.status_code == 403
