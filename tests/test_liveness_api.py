"""POST /api/liveness/sweep: origin-guarded, background, expires dead jobs."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job(url: str) -> str:
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        db.upsert_job(Job(source="lever", title="Data Scientist", company="Acme", url=url))
        return db.list_jobs()[0]["id"]


def test_sweep_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.post("/api/liveness/sweep", headers={"origin": "https://evil.example.com"})
    assert resp.status_code == 403


def test_sweep_expires_dead_jobs(atlas_app, monkeypatch):
    import engine.discovery.liveness as liveness
    from engine.db.models import DB

    monkeypatch.setattr(liveness, "check_url", lambda client, url: ("dead", "http 404"))
    with TestClient(atlas_app) as client:  # TestClient runs BackgroundTasks on exit of request
        jid = _seed_job("https://x.co/jobs/1")
        resp = client.post("/api/liveness/sweep")
        assert resp.status_code == 200 and resp.json()["started"] is True
        status = client.get("/api/liveness/status").json()
        assert "running" in status
    with DB() as db:
        assert db.get_job(jid)["state"] == "expired"


def test_discover_runs_liveness_only_when_enabled(tmp_path, monkeypatch):
    from engine.db.models import DB
    from engine.discovery import runner

    calls: list[int] = []
    monkeypatch.setattr(
        "engine.discovery.liveness.sweep_liveness",
        lambda db, limit=40, client=None: calls.append(limit) or {"checked": 0},
    )
    cfg_off = {
        "ats": {"enabled": False},
        "jobspy": {"enabled": False},
        "himalayas": {"enabled": False},
        "adzuna": {"enabled": False},
    }
    with DB(tmp_path / "a.db") as db:
        runner.discover(db, sources_cfg=cfg_off, companies=[], terms=[])
        assert calls == []  # default: off
        runner.discover(
            db,
            sources_cfg={**cfg_off, "liveness": {"enabled": True, "limit": 7}},
            companies=[],
            terms=[],
        )
        assert calls == [7]
