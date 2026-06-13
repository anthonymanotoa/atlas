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
        db.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="Data Scientist",
                company="Acme",
                url="https://x/1",
            )
        )
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
        assert len(db.followups_for_job(jid)) == 4  # Day 3/7/14 + breakup scheduled


def test_mark_sent_unknown_message_is_ok(atlas_app):
    """Characterize: the UPDATE matches zero rows but the route still returns ok."""
    with TestClient(atlas_app) as client:
        resp = client.post("/api/messages/999999/sent")
    assert resp.status_code == 200 and resp.json() == {"ok": True}


# ── Plan 014: the schema is initialized once at startup, not once per request ──
def test_schema_init_runs_once_across_requests(atlas_app, monkeypatch):
    from engine.db.models import DB

    calls = {"n": 0}
    original = DB.init_schema

    def counting(self):
        calls["n"] += 1
        return original(self)

    monkeypatch.setattr(DB, "init_schema", counting)
    # Entering the context triggers the lifespan startup → one shared DB → one init.
    with TestClient(atlas_app) as client:
        for _ in range(4):
            assert client.get("/api/overview").status_code == 200
            assert client.get("/api/board").status_code == 200
    assert calls["n"] == 1  # not 8 (was once per request before the shared connection)


# ── Plan 020: state-mutating POSTs enforce a trusted Origin server-side ────────
def test_mutating_post_rejects_foreign_origin(atlas_app):
    # The dependency fires before the handler, so no seed/DB state is needed.
    with TestClient(atlas_app) as client:
        resp = client.post(
            "/api/jobs/anyjob/applied", headers={"origin": "https://evil.example.com"}
        )
    assert resp.status_code == 403


def test_mutating_post_allows_no_origin(atlas_app):
    # No Origin header → same-origin / non-browser → allowed past the check (handler runs).
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/applied")
    assert resp.status_code != 403


def test_mutating_post_allows_allowlisted_origin(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/applied", headers={"origin": "http://localhost:8787"})
    assert resp.status_code != 403


# ── P1-B: settings + CSV export ────────────────────────────────────────────────
def test_settings_roundtrip_and_whitelist(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/settings", json={"key": "evil", "value": "x"}).status_code == 400
        r = client.post(
            "/api/settings", json={"key": "csv_columns", "value": '["title","company"]'}
        )
        assert r.status_code == 200
        assert client.get("/api/settings").json()["csv_columns"] == '["title","company"]'


def test_export_csv_headers_and_columns(atlas_app):
    with TestClient(atlas_app) as client:
        _seed_job("shortlisted")
        r = client.get("/api/export?columns=title,company")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    assert "Puesto,Empresa" in r.text and "Data Scientist,Acme" in r.text


def test_csv_columns_lists_catalog(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.get("/api/csv/columns").json()
    ids = {c["id"] for c in r["available"]}
    assert {"title", "company", "salary"} <= ids
    assert r["selected"]


# ── P2-D: learning loop ─────────────────────────────────────────────────────────
def test_record_outcome_creates_learnings(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        r = client.post(
            f"/api/jobs/{jid}/outcome",
            json={"final_state": "offer", "recruiter_source": "referral", "interview_count": 2},
        )
        assert r.status_code == 200
        assert any(learning["pattern_type"] == "offer_rate" for learning in r.json()["learnings"])
        assert client.get("/api/learnings").json()["learnings"]


# ── P2-C: supervised social search ──────────────────────────────────────────────
def test_social_search_flow(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job("shortlisted")
        r = client.post(f"/api/jobs/{jid}/start-social-search")
        assert r.status_code == 200 and "queries" in r.json()
        assert any(
            p["job_id"] == jid for p in client.get("/api/pending-searches").json()["pending"]
        )
        add = client.post(
            f"/api/jobs/{jid}/social_mentions",
            json={"platform": "linkedin", "recruiter_name": "Jane"},
        )
        assert add.status_code == 200
        ms = client.get(f"/api/jobs/{jid}/social_mentions").json()["mentions"]
        assert ms and ms[0]["recruiter_name"] == "Jane"
        # capturing a mention clears the pending search
        assert all(
            p["job_id"] != jid for p in client.get("/api/pending-searches").json()["pending"]
        )


# ── P1-G: onboarding gate ───────────────────────────────────────────────────────
def test_onboarding_status_and_complete(atlas_app):
    with TestClient(atlas_app) as client:
        st = client.get("/api/onboarding").json()
        assert st["complete"] is False
        assert "summary" in st["audit"] and "findings" in st["audit"]
        assert client.post("/api/onboarding/complete").status_code == 200
        assert client.get("/api/onboarding").json()["complete"] is True


# ── Plan 019: dashboard-triggered discover→score (deterministic, keyless) ──────
def test_discover_endpoint_runs_deterministic_pipeline(atlas_app, monkeypatch):
    import engine.discovery.runner as runner_mod
    import engine.scoring.run as score_mod

    calls = {"discover": 0, "score": 0}

    def fake_discover(db, **kw):
        calls["discover"] += 1
        return {"sources": {}, "new": 0, "seen": 0, "fetched": 0, "errors": []}

    def fake_score(db, criteria, **kw):
        calls["score"] += 1
        return (0, 0)

    # Stub the engine fns so the test makes NO network calls (the real run hits HTTP).
    monkeypatch.setattr(runner_mod, "discover", fake_discover)
    monkeypatch.setattr(score_mod, "score_jobs", fake_score)

    with TestClient(atlas_app) as client:
        resp = client.post("/api/discover")
        assert resp.status_code == 200
        assert resp.json().get("started") is True
        # The BackgroundTask runs within the request cycle under TestClient.
        assert calls["discover"] == 1 and calls["score"] == 1
        assert client.get("/api/discover/status").json() == {"running": False}
