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
    """F3 v2: /applied siembra el PRIMER follow-up de la cadencia applied (7d, kind='applied')."""
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        resp = client.post(f"/api/jobs/{jid}/applied")
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    with DB() as db:
        rows = db.followups_for_job(jid)
        assert db.get_job(jid)["state"] == "applied"
    assert len(rows) == 1 and rows[0]["kind"] == "applied"


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


def test_mutating_post_allows_any_loopback_port(atlas_app):
    # Atlas may be served on any port the user picks (or our verify server on 8799); a loopback
    # origin on ANY port is the app itself and must be allowed — a remote site can't forge one.
    with TestClient(atlas_app) as client:
        jid = _seed_job()
        for origin in ("http://127.0.0.1:8799", "http://localhost:9999", "http://[::1]:3000"):
            resp = client.post(f"/api/jobs/{jid}/applied", headers={"origin": origin})
            assert resp.status_code != 403, origin


def test_mutating_post_rejects_lookalike_loopback_host(atlas_app):
    # Defense against an origin that merely contains 'localhost' but isn't a loopback host.
    with TestClient(atlas_app) as client:
        resp = client.post(
            "/api/jobs/anyjob/applied", headers={"origin": "http://localhost.evil.com"}
        )
    assert resp.status_code == 403


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


# ── P3-F: portfolio + peers ──────────────────────────────────────────────────────
def test_portfolio_generate_and_peers(atlas_app):
    with TestClient(atlas_app) as client:
        gen = client.post("/api/portfolio/generate", json={"include_github": False})
        assert gen.status_code == 200
        pid = gen.json()["id"]
        latest = client.get("/api/portfolio/latest").json()["portfolio"]
        assert latest and latest["id"] == pid
        prev = client.get(f"/api/portfolio/{pid}/preview")
        assert prev.status_code == 200 and "text/html" in prev.headers["content-type"]
        client.post("/api/peers", json={"peer_name": "Grace", "peer_portfolio_url": "https://x"})
        peers = client.get("/api/peers").json()["peers"]
        assert peers and peers[0]["peer_name"] == "Grace"


# ── P3-E: interview prep ─────────────────────────────────────────────────────────
def test_interview_flow(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed_job("interview")
        iid = client.post(
            f"/api/jobs/{jid}/interview", json={"scheduled_at": "2026-07-15", "round": "technical"}
        ).json()["id"]
        client.post(
            f"/api/interview/{iid}/interviewer", json={"name": "Jane", "linkedin_url": "https://x"}
        )
        prep = client.post(f"/api/interview/{iid}/prep", json={"language": "en"})
        assert prep.status_code == 200 and "Interview prep" in prep.json()["markdown"]
        ivs = client.get(f"/api/jobs/{jid}/interviews").json()["interviews"]
        assert ivs and ivs[0]["interviewers"][0]["name"] == "Jane"


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


def test_learning_feedback_unknown_id_is_404(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.post("/api/learnings/999999/feedback", json={"feedback_type": "disagree"})
    assert resp.status_code == 404


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


# ── FASE B: CV↔JD match score persists + surfaces via the job-detail API ───────
def test_match_score_surfaces_in_job_detail(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            db.set_match(jid, 72, ["kubernetes", "terraform"])
        detail = client.get(f"/api/jobs/{jid}").json()
    assert detail["job"]["match_score"] == 72
    assert detail["job"]["missing_keywords"] == ["kubernetes", "terraform"]


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


# ── SPA fallback (Atlas v2 F1): el router de frontend necesita deep links ────


def test_spa_fallback_serves_index_for_client_routes(atlas_app, tmp_path, monkeypatch):
    import dashboard.backend.main as backend

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>atlas-spa</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(backend, "_DIST", dist)

    with TestClient(atlas_app) as client:
        for path in ("/", "/pipeline", "/jobs/abc123", "/settings", "/onboarding"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert "atlas-spa" in resp.text, path
        # los archivos reales del build se sirven tal cual
        resp = client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text


def test_spa_fallback_unknown_api_route_is_404_not_index(atlas_app, tmp_path, monkeypatch):
    import dashboard.backend.main as backend

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>atlas-spa</html>")
    monkeypatch.setattr(backend, "_DIST", dist)

    with TestClient(atlas_app) as client:
        assert client.get("/api/definitely-not-a-route").status_code == 404


def test_spa_fallback_api_like_route_serves_index(atlas_app, tmp_path, monkeypatch):
    """Routes like /apikeys (not /api/*) should serve index.html, not 404."""
    import dashboard.backend.main as backend

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>atlas-spa</html>")
    monkeypatch.setattr(backend, "_DIST", dist)

    with TestClient(atlas_app) as client:
        resp = client.get("/apikeys")
        assert resp.status_code == 200, "apikeys should be treated as a client route"
        assert "atlas-spa" in resp.text


def test_spa_fallback_without_built_dist_is_404(atlas_app, tmp_path, monkeypatch):
    import dashboard.backend.main as backend

    monkeypatch.setattr(backend, "_DIST", tmp_path / "no-dist")
    with TestClient(atlas_app) as client:
        assert client.get("/pipeline").status_code == 404


# ── F4 §7.2: upskill report endpoints (read-only; $0) ────────────────────────────
def test_upskill_latest_is_null_when_empty(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.get("/api/upskill/latest").json() == {"report": None}


def test_upskill_latest_returns_persisted_report(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        with DB() as db:
            rid = db.add_upskill_report(
                intent_id=None,
                report_md="# Plan de upskilling\n\n## Kubernetes",
                heatmap=[{"skill": "Kubernetes", "severity": "Critical", "note": "gate"}],
                hard_gaps={"skills": [{"skill": "kubernetes", "score": 0.7}], "jobs_considered": 1},
            )
        latest = client.get("/api/upskill/latest").json()["report"]
        assert latest["id"] == rid
        assert latest["report_md"].startswith("# Plan")
        assert latest["heatmap"][0]["severity"] == "Critical"  # parsed from json
        assert latest["hard_gaps"]["jobs_considered"] == 1
        one = client.get(f"/api/upskill/{rid}")
        assert one.status_code == 200 and one.json()["id"] == rid


def test_upskill_report_unknown_id_is_404(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.get("/api/upskill/999999").status_code == 404
