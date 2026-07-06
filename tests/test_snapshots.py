"""Posting archive (spec §5.3): snapshot the posting when you apply, as evidence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from engine.db.models import DB
from engine.normalize import Job


def _seed() -> str:
    with DB() as db:
        db.upsert_job(
            Job(
                source="greenhouse",
                title="Data Scientist",
                company="Acme",
                url="https://x.co/jobs/1",
                description="Build models.",
                salary_min=90000.0,
            )
        )
        return db.list_jobs()[0]["id"]


def test_snapshot_posting_is_idempotent(tmp_path):
    with DB(tmp_path / "a.db") as db:
        db.upsert_job(Job(source="lever", title="DE", company="Acme", description="x"))
        jid = db.list_jobs()[0]["id"]
        first = db.snapshot_posting(jid)
        second = db.snapshot_posting(jid)
        snaps = db.snapshots_for(jid)
    assert first is not None and second is None
    assert len(snaps) == 1
    assert snaps[0]["payload"]["title"] == "DE"
    assert snaps[0]["captured_at"]


def test_snapshot_posting_unknown_job_returns_none(tmp_path):
    with DB(tmp_path / "a.db") as db:
        assert db.snapshot_posting("does-not-exist") is None
        assert db.snapshots_for("does-not-exist") == []


def test_mark_applied_persists_snapshot(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed()
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200  # re-POST: still one
    with DB() as db:
        snaps = db.snapshots_for(jid)
    assert len(snaps) == 1
    assert snaps[0]["payload"]["company"] == "Acme"
    assert snaps[0]["payload"]["salary_min"] == 90000.0


def test_state_transition_to_applied_also_snapshots(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed()
        client.post(f"/api/jobs/{jid}/state", json={"state": "applied"})
    with DB() as db:
        assert len(db.snapshots_for(jid)) == 1


def test_snapshot_survives_posting_death(tmp_path):
    """Evidence outlives the posting: clearing the job's fields keeps the snapshot intact."""
    with DB(tmp_path / "a.db") as db:
        db.upsert_job(
            Job(source="lever", title="MLE", company="Acme", description="Ship pipelines.")
        )
        jid = db.list_jobs()[0]["id"]
        db.snapshot_posting(jid)
        # The posting dies later — description wiped, as a stale/dead listing would be.
        db.conn.execute("UPDATE jobs SET description=NULL, title='' WHERE id=?", (jid,))
        db.conn.commit()
        snaps = db.snapshots_for(jid)
    assert len(snaps) == 1
    assert snaps[0]["payload"]["title"] == "MLE"
    assert snaps[0]["payload"]["description"] == "Ship pipelines."
