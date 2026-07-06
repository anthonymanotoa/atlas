"""F3: endpoints nuevos del dashboard (followups, analytics, stories, ops)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job(state: str | None = None) -> str:
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        db.upsert_job(
            Job(source="greenhouse", source_job_id="1", title="Data Scientist",
                company="Acme", url="https://x/1")
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
            db.add_followup(jid, channel="email", touch_number=1,
                            due_at="2026-07-11T00:00:00+00:00", kind="applied")
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
            db.add_followup(jid, channel="email", touch_number=1,
                            due_at="2020-01-01T00:00:00+00:00", kind="applied")  # muy vencido
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
            fid = db.add_followup(jid, channel="email", touch_number=1,
                                  due_at="2026-07-11T00:00:00+00:00", kind="applied")
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
            db.add_followup(jid, channel="email", touch_number=1,
                            due_at="2026-07-11T00:00:00+00:00", kind="applied")
            fid1 = db.followups_for_job(jid)[0]["id"]
            db.mark_followup(fid1, "done")
            fid2 = db.add_followup(jid, channel="email", touch_number=2,
                                   due_at="2026-07-18T00:00:00+00:00", kind="applied")
        r = client.post(f"/api/followups/{fid2}/sent", json={"confirm": True})
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["next_id"] is None


def test_followup_sent_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/followups/1/sent", json={"confirm": True},
                        headers={"origin": "https://evil.example.com"})
    assert r.status_code == 403
