"""F3: endpoints nuevos del dashboard (followups, analytics, stories, ops)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job(state: str | None = None) -> str:
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


# ── §6.1 Follow-ups v2 ────────────────────────────────────────────────────────
def test_mark_applied_seeds_v2_cadence(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200  # idempotente
    with DB() as db:
        rows = db.followups_for_job(jid)
    assert len(rows) == 1 and rows[0]["kind"] == "applied" and rows[0]["touch_number"] == 1


def test_state_applied_seeds_v2_cadence_and_is_idempotent(atlas_app):
    """El otro camino (POST /state → applied) siembra la MISMA cadencia y no duplica,
    ni cruzándose con /applied."""
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        assert client.post(f"/api/jobs/{jid}/state", json={"state": "applied"}).status_code == 200
        # segundo /state y luego /applied: ninguno debe crear un segundo pending toque 1.
        assert client.post(f"/api/jobs/{jid}/state", json={"state": "applied"}).status_code == 200
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200
    with DB() as db:
        rows = db.followups_for_job(jid)
    assert len(rows) == 1 and rows[0]["kind"] == "applied" and rows[0]["touch_number"] == 1


def test_state_interview_seeds_thankyou(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        assert client.post(f"/api/jobs/{jid}/state", json={"state": "interview"}).status_code == 200
    with DB() as db:
        kinds = {f["kind"] for f in db.followups_for_job(jid)}
    assert "interview" in kinds


def test_state_responded_cancels_pending_and_seeds(atlas_app):
    """responded cancela los toques pendientes (register_reply) y siembra su propia cadencia."""
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        with DB() as db:
            db.add_followup(
                jid,
                channel="email",
                touch_number=1,
                due_at="2026-07-11T00:00:00+00:00",
                kind="applied",
            )
        assert client.post(f"/api/jobs/{jid}/state", json={"state": "responded"}).status_code == 200
    with DB() as db:
        rows = db.followups_for_job(jid)
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    # el toque applied pendiente quedó cancelado; hay un toque responded pendiente
    assert all(r["state"] == "cancelled" for r in by_kind.get("applied", []))
    assert any(r["state"] == "pending" for r in by_kind.get("responded", []))


def test_get_followups_buckets_with_drafts(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        with DB() as db:
            db.add_followup(
                jid,
                channel="email",
                touch_number=1,
                due_at="2020-01-01T00:00:00+00:00",
                kind="applied",
            )  # muy vencido
        data = client.get("/api/followups").json()["buckets"]
    assert set(data) == {"urgent", "overdue", "waiting", "cold"}
    assert data["overdue"], "un toque vencido hace años debe caer en OVERDUE"
    item = data["overdue"][0]
    assert item["company"] == "Acme" and item["draft"]["body"]
    assert "just checking in" not in item["draft"]["body"].lower()


def test_followup_sent_requires_confirm_and_seeds_next(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        with DB() as db:
            fid = db.add_followup(
                jid,
                channel="email",
                touch_number=1,
                due_at="2026-07-11T00:00:00+00:00",
                kind="applied",
            )
        assert client.post(f"/api/followups/{fid}/sent", json={"confirm": False}).status_code == 400
        r = client.post(f"/api/followups/{fid}/sent", json={"confirm": True})
        assert r.status_code == 200 and r.json()["ok"] is True and r.json()["next_id"]
        assert client.post("/api/followups/99999/sent", json={"confirm": True}).status_code == 404


def test_followup_sent_stops_at_cap(atlas_app):
    """Al confirmar el ÚLTIMO toque (touch 2, cap=2 para applied) no se siembra siguiente."""
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job("applied")
        with DB() as db:
            # toque 1 ya done, toque 2 pending → confirmar toque 2 debe cerrar la cadencia
            db.add_followup(
                jid,
                channel="email",
                touch_number=1,
                due_at="2026-07-11T00:00:00+00:00",
                kind="applied",
            )
            fid1 = db.followups_for_job(jid)[0]["id"]
            db.mark_followup(fid1, "done")
            fid2 = db.add_followup(
                jid,
                channel="email",
                touch_number=2,
                due_at="2026-07-18T00:00:00+00:00",
                kind="applied",
            )
        r = client.post(f"/api/followups/{fid2}/sent", json={"confirm": True})
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["next_id"] is None


def test_followup_sent_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/followups/1/sent",
            json={"confirm": True},
            headers={"origin": "https://evil.example.com"},
        )
    assert r.status_code == 403


# ── §6.2 Analytics + apply-rec ────────────────────────────────────────────────
def test_get_analytics_shape(atlas_app):
    with TestClient(atlas_app) as client:
        _seed_job("applied")
        p = client.get("/api/analytics").json()
    assert {"funnel", "score_floor", "recommendations", "response_times"} <= set(p)
    assert p["funnel"][0]["stage"] == "discovered"


def test_apply_rec_set_criteria_writes_frontmatter(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "criteria.md")
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/analytics/apply-rec",
            json={
                "id": "threshold-66",
                "action_type": "set_criteria",
                "payload": {"field": "shortlist_threshold", "value": 66.0},
            },
        )
        assert r.status_code == 200 and r.json()["ok"] is True
    assert "shortlist_threshold: 66" in (tmp_path / "criteria.md").read_text()


def test_apply_rec_block_company(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "criteria.md")
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/analytics/apply-rec",
            json={
                "id": "block-ghost",
                "action_type": "block_company",
                "payload": {"company": "Ghost Corp"},
            },
        )
        assert r.status_code == 200
    assert "Ghost Corp" in (tmp_path / "criteria.md").read_text()


def test_apply_rec_block_company_is_idempotent(atlas_app, tmp_path, monkeypatch):
    """Aplicar el mismo block dos veces no duplica la empresa en el blocklist."""
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "criteria.md")
    body = {
        "id": "block-ghost",
        "action_type": "block_company",
        "payload": {"company": "Ghost Corp"},
    }
    with TestClient(atlas_app) as client:
        assert client.post("/api/analytics/apply-rec", json=body).status_code == 200
        assert client.post("/api/analytics/apply-rec", json=body).status_code == 200
    assert (tmp_path / "criteria.md").read_text().count("Ghost Corp") == 1


def test_apply_rec_rejects_unknown_action_and_field(atlas_app):
    with TestClient(atlas_app) as client:
        assert (
            client.post(
                "/api/analytics/apply-rec", json={"id": "x", "action_type": "rm-rf", "payload": {}}
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/analytics/apply-rec",
                json={
                    "id": "x",
                    "action_type": "set_criteria",
                    "payload": {"field": "roles", "value": ["hacker"]},
                },
            ).status_code
            == 400
        )


def test_apply_rec_set_criteria_rejects_non_coercible_value(atlas_app, tmp_path, monkeypatch):
    """Un value no coercible (p. ej. "abc" para shortlist_threshold: float) devuelve 400, no 500."""
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "criteria.md")
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/analytics/apply-rec",
            json={
                "id": "threshold-bad",
                "action_type": "set_criteria",
                "payload": {"field": "shortlist_threshold", "value": "abc"},
            },
        )
    assert r.status_code == 400


def test_apply_rec_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/analytics/apply-rec",
            json={
                "id": "x",
                "action_type": "set_criteria",
                "payload": {"field": "shortlist_threshold", "value": 66.0},
            },
            headers={"origin": "https://evil.example.com"},
        )
    assert r.status_code == 403


# ── §6.3 Story bank ───────────────────────────────────────────────────────────
def test_stories_crud_and_match(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/stories",
            json={
                "title": "Pipeline caído en Black Friday",
                "situation": "ETL caído",
                "task": "Restaurar",
                "action": "Rollback en Airflow",
                "result": "40min",
                "reflection": "Alertas",
                "skills": ["python", "airflow"],
            },
        )
        assert r.status_code == 200
        sid = r.json()["id"]
        stories = client.get("/api/stories").json()["stories"]
        assert stories[0]["skills"] == ["python", "airflow"]
        assert client.put(f"/api/stories/{sid}", json={"result": "35min"}).status_code == 200
        assert client.get("/api/stories").json()["stories"][0]["result"] == "35min"
        m = client.get("/api/stories/match", params={"q": "python incident on airflow"}).json()
        assert m["matches"] and m["matches"][0]["story"]["id"] == sid
        assert "Situación:" in m["matches"][0]["formatted"]
        assert client.delete(f"/api/stories/{sid}").status_code == 200
        assert client.get("/api/stories").json()["stories"] == []


def test_stories_put_delete_unknown_404(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.put("/api/stories/999", json={"title": "x"}).status_code == 404
        assert client.delete("/api/stories/999").status_code == 404


def test_stories_match_empty_query_returns_no_matches(atlas_app):
    """Una query vacía (o solo stopwords) no revienta: devuelve matches vacío, no 500."""
    with TestClient(atlas_app) as client:
        client.post("/api/stories", json={"title": "x", "situation": "y", "skills": ["python"]})
        assert client.get("/api/stories/match", params={"q": ""}).json()["matches"] == []


def test_stories_post_requires_title(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/stories", json={"situation": "x"}).status_code == 422


def test_stories_mutations_reject_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        hdr = {"origin": "https://evil.example.com"}
        assert client.post("/api/stories", json={"title": "x"}, headers=hdr).status_code == 403
        assert client.put("/api/stories/1", json={"title": "x"}, headers=hdr).status_code == 403
        assert client.delete("/api/stories/1", headers=hdr).status_code == 403


# ── §6.5 Ops: resolve/add company, import connections, system health ──────────
def test_resolve_company_returns_ats_contract(atlas_app, monkeypatch):
    import dashboard.backend.main as backend_main

    monkeypatch.setattr(
        backend_main,
        "resolve_ats",
        lambda url, client=None: {"ats": "greenhouse", "token": "acmerobotics", "eu": False},
    )
    monkeypatch.setattr(
        backend_main, "_probe_company_jobs", lambda ats, token: (3, "Acme Robotics")
    )
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/companies/resolve", json={"url": "https://boards.greenhouse.io/acmerobotics"}
        )
    body = r.json()
    assert r.status_code == 200 and body["resolved"] is True
    assert body["ats"] == "greenhouse" and body["token"] == "acmerobotics"
    assert body["preview_jobs_count"] == 3 and body["already_configured"] is False


def test_resolve_company_unknown_ats_is_not_error(atlas_app, monkeypatch):
    import dashboard.backend.main as backend_main

    monkeypatch.setattr(backend_main, "resolve_ats", lambda url, client=None: None)
    with TestClient(atlas_app) as client:
        r = client.post("/api/companies/resolve", json={"url": "https://example.com/careers"})
    assert r.status_code == 200 and r.json()["resolved"] is False


def test_resolve_company_requires_url(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/companies/resolve", json={}).status_code == 422


def test_add_company_appends_and_dedupes(atlas_app, tmp_path, monkeypatch):
    import engine.paths as paths

    monkeypatch.setattr(paths, "COMPANIES_PATH", tmp_path / "companies.yaml")
    entry = {"company": "Acme Robotics", "ats": "greenhouse", "token": "acmerobotics"}
    with TestClient(atlas_app) as client:
        r1 = client.post("/api/companies/add", json=entry)
        r2 = client.post("/api/companies/add", json=entry)
    assert r1.status_code == 200 and r1.json() == {"ok": True, "added": True}
    assert r2.status_code == 200 and r2.json() == {"ok": True, "added": False}
    import yaml

    data = yaml.safe_load((tmp_path / "companies.yaml").read_text())
    assert len(data["companies"]) == 1 and data["companies"][0]["token"] == "acmerobotics"


def test_add_company_rejects_invalid(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.post("/api/companies/add", json={"token": "x"}).status_code == 400


def test_suggest_companies_uses_reverse(atlas_app, monkeypatch):
    import dashboard.backend.main as backend_main

    monkeypatch.setattr(
        backend_main.reverse,
        "suggest_companies",
        lambda names, criteria, client=None: [
            {
                "company": "Acme Corp",
                "ats": "greenhouse",
                "token": "acmecorp",
                "jobs_count": 2,
                "matching_titles": ["Staff Data Scientist"],
            }
        ],
    )
    with TestClient(atlas_app) as client:
        r = client.post("/api/discovery/suggest", json={"names": ["Acme Corp"]})
    body = r.json()
    assert r.status_code == 200 and body["suggestions"][0]["company"] == "Acme Corp"


def test_import_connections_multipart(atlas_app):
    csv = (
        "First Name,Last Name,Company,Position,URL,Email Address\n"
        "Jane,Doe,Acme,Data Lead,https://x/jane,jane@x.com\n"
        "John,Roe,Beta,ML Eng,https://x/john,john@x.com\n"
    )
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/connections/import",
            files={"file": ("Connections.csv", csv, "text/csv")},
        )
    assert r.status_code == 200 and r.json() == {"ok": True, "imported": 2}


def test_import_connections_rejects_empty(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/connections/import", files={"file": ("empty.csv", "", "text/csv")})
    assert r.status_code == 200 and r.json()["imported"] == 0


def test_system_health_consolidates_status_and_doctor(atlas_app, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    with TestClient(atlas_app) as client:
        _seed_job("applied")
        h = client.get("/api/system/health").json()
    assert h["db"]["ok"] is True and h["db"]["jobs"] >= 1
    assert "applied" in h["counts"]
    assert isinstance(h["sources"], list)
    assert h["safeguards"]["api_key_unset"] is True
    assert set(h) >= {"profile", "db", "counts", "last_run", "sources", "safeguards"}


def test_ops_posts_reject_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        hdr = {"origin": "https://evil.example.com"}
        assert (
            client.post("/api/companies/resolve", json={"url": "x"}, headers=hdr).status_code == 403
        )
        assert client.post("/api/companies/add", json={}, headers=hdr).status_code == 403
        assert client.post("/api/discovery/suggest", json={}, headers=hdr).status_code == 403
        assert (
            client.post(
                "/api/connections/import",
                files={"file": ("c.csv", "", "text/csv")},
                headers=hdr,
            ).status_code
            == 403
        )
