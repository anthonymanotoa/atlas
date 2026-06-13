"""Characterization tests for the FastAPI mutation routes.

Driven through ``fastapi.testclient.TestClient`` against an app pointed at a
throwaway DB (the ``atlas_app`` fixture redirects ``ATLAS_DATA_DIR`` before the
engine imports bind ``DB_PATH``). Used as a context manager so the lifespan
startup/shutdown (shared-connection model, plan 014) runs. No network, no writes
to the repo's real ``data/atlas.db``.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job(state: str | None = None) -> str:
    """Insert one job into the (already-redirected) DB and return its id."""
    from engine.db.models import DB
    from engine.normalize import Job
    with DB() as db:
        db.upsert_job(Job(source="greenhouse", source_job_id="1", title="Data Scientist",
                          company="Acme", url="https://x/1"))
        jid = db.list_jobs()[0]["id"]
        if state:
            db.set_state(jid, state, {"via": "test"})
    return jid


def test_set_state_rejects_invalid_state(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/state", json={"state": "bogus"})
    assert resp.status_code == 400


def test_set_state_unknown_job_is_404(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.post("/api/jobs/does-not-exist/state", json={"state": "applied"})
    assert resp.status_code == 404


def test_set_state_happy_path(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/state", json={"state": "shortlisted"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "state": "shortlisted"}


def test_mark_applied_on_real_job_schedules_cadence(atlas_app):
    """Current behavior: /applied flips state and starts the follow-up cadence."""
    from engine.db.models import DB
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/applied")
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    with DB() as db:
        assert db.get_job(jid)["state"] == "applied"
        assert len(db.followups_for_job(jid)) == 4   # Day 3/7/14 + breakup scheduled


def test_mark_sent_unknown_message_is_ok(atlas_app):
    """Characterize: the UPDATE matches zero rows but the route still returns ok."""
    with TestClient(atlas_app) as client:
        resp = client.post("/api/messages/999999/sent")
    assert resp.status_code == 200 and resp.json() == {"ok": True}
