"""Endpoints de la cola de intents (F4 §7.1): validación por tipo + origin guard."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job() -> str:
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        db.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="Data Scientist",
                company="Acme",
                url="https://x/1",
            )
        )
        return db.list_jobs()[0]["id"]


def test_enqueue_unknown_type_is_400(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/intents", json={"type": "world_peace", "payload": {}})
    assert r.status_code == 400


def test_enqueue_cv_review_requires_existing_job(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/intents", json={"type": "cv_review", "job_id": "nope"})
    assert r.status_code == 404


def test_enqueue_cv_review_happy_path_and_listing(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        r = client.post("/api/intents", json={"type": "cv_review", "job_id": jid, "payload": {}})
        assert r.status_code == 200 and r.json()["ok"] is True
        iid = r.json()["id"]
        lst = client.get("/api/intents?status=pending").json()
        assert lst["pending"] == 1
        assert [i["id"] for i in lst["intents"]] == [iid]
        one = client.get(f"/api/intents/{iid}")
        assert one.status_code == 200 and one.json()["type"] == "cv_review"


def test_enqueue_legitimacy_batch_validates_job_ids(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        bad = client.post(
            "/api/intents",
            json={"type": "legitimacy_batch", "payload": {"job_ids": []}},
        )
        assert bad.status_code == 400  # lista vacía
        ghost = client.post(
            "/api/intents",
            json={"type": "legitimacy_batch", "payload": {"job_ids": [jid, "nope"]}},
        )
        assert ghost.status_code == 404
        ok = client.post(
            "/api/intents",
            json={"type": "legitimacy_batch", "payload": {"job_ids": [jid]}},
        )
        assert ok.status_code == 200


def test_enqueue_rejects_extra_payload_keys(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        r = client.post(
            "/api/intents",
            json={"type": "cv_review", "job_id": jid, "payload": {"rm": "-rf"}},
        )
    assert r.status_code == 400


def test_enqueue_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/intents",
            json={"type": "upskill_report", "payload": {}},
            headers={"Origin": "https://evil.example"},
        )
    assert r.status_code == 403


def test_intents_list_invalid_status_is_400(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.get("/api/intents?status=bogus").status_code == 400
        assert client.get("/api/intents/unknown-id").status_code == 404
