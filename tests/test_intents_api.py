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


# ── cv_reviews endpoints (F4 §7.2) ─────────────────────────────────────────────
def test_cv_reviews_listing_and_apply_edit_flow(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            rid = db.add_cv_review(
                jid,
                intent_id=None,
                cv_version_id=None,
                edits=[
                    {
                        "file": "cv",
                        "old_string": "nope-not-there",
                        "new_string": "x",
                        "reason": "r",
                    }
                ],
                critique={
                    "missed_keywords": [],
                    "company_angles": [],
                    "reframing": [],
                    "tone_register": [],
                },
                flags=[],
            )
        lst = client.get(f"/api/jobs/{jid}/cv-reviews").json()["reviews"]
        assert lst[0]["id"] == rid
        assert lst[0]["critique"] == {
            "missed_keywords": [],
            "company_angles": [],
            "reframing": [],
            "tone_register": [],
        }
        bad = client.post(f"/api/cv-reviews/{rid}/apply-edit", json={"index": 5})
        assert bad.status_code == 400  # index fuera de rango


def test_cv_reviews_unknown_job_is_404(atlas_app):
    with TestClient(atlas_app) as client:
        assert client.get("/api/jobs/nope/cv-reviews").status_code == 404


def test_apply_edit_non_matching_old_string_is_400_not_500(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            rid = db.add_cv_review(
                jid,
                intent_id=None,
                cv_version_id=None,
                edits=[
                    {
                        "file": "cv",
                        "old_string": "definitely-not-in-the-cv",
                        "new_string": "x",
                        "reason": "r",
                    }
                ],
                critique={
                    "missed_keywords": [],
                    "company_angles": [],
                    "reframing": [],
                    "tone_register": [],
                },
                flags=[],
            )
        r = client.post(f"/api/cv-reviews/{rid}/apply-edit", json={"index": 0})
        assert r.status_code == 400  # graceful, not a 500


def test_resolve_flag_keep_persists(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            rid = db.add_cv_review(
                jid,
                intent_id=None,
                cv_version_id=None,
                edits=[],
                critique={
                    "missed_keywords": [],
                    "company_angles": [],
                    "reframing": [],
                    "tone_register": [],
                },
                flags=[
                    {
                        "file": "cv",
                        "bullet": "b",
                        "classification": "Flag",
                        "reason": "r",
                        "softened": "s",
                    }
                ],
            )
        r = client.post(f"/api/cv-reviews/{rid}/resolve-flag", json={"index": 0, "action": "keep"})
        assert r.status_code == 200 and r.json()["resolution"] == "keep"
        with DB() as db:
            assert db.get_cv_review(rid)["flags"][0]["resolution"] == "keep"


def test_apply_edit_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/cv-reviews/1/apply-edit",
            json={"index": 0},
            headers={"Origin": "https://evil.example"},
        )
    assert r.status_code == 403


def test_resolve_flag_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/cv-reviews/1/resolve-flag",
            json={"index": 0, "action": "keep"},
            headers={"Origin": "https://evil.example"},
        )
    assert r.status_code == 403


def test_resolve_flag_invalid_action_is_422(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/cv-reviews/1/resolve-flag", json={"index": 0, "action": "nuke"})
    assert r.status_code == 422  # Literal-constrained body rejects before the handler


# ── interview debrief endpoint (Task 11) ───────────────────────────────────────
# Saves the candidate's post-interview debrief and, when reanalyze=true, re-enqueues an
# interview_prep_deep intent for that interview (a follow-up analysis — no LLM here, $0).
def test_interview_debrief_saves_and_can_reanalyze(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            ivid = db.add_interview(jid, round="technical")
        r = client.post(
            f"/api/interview/{ivid}/debrief",
            json={"debrief_md": "Preguntaron mucho de SQL.", "reanalyze": True},
        )
        assert r.status_code == 200 and r.json()["ok"] is True
        assert r.json()["intent_id"].startswith("in_")
        with DB() as db:
            assert "SQL" in db.get_interview(ivid)["debrief_md"]
        # The re-enqueued intent is a pending interview_prep_deep tied to the same interview.
        lst = client.get("/api/intents?status=pending").json()
        deep = [i for i in lst["intents"] if i["type"] == "interview_prep_deep"]
        assert deep and deep[0]["payload"]["interview_id"] == ivid


def test_interview_debrief_without_reanalyze_enqueues_nothing(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            ivid = db.add_interview(jid, round="phone")
        r = client.post(
            f"/api/interview/{ivid}/debrief",
            json={"debrief_md": "Fue una charla corta.", "reanalyze": False},
        )
        assert r.status_code == 200 and r.json()["intent_id"] is None
        assert client.get("/api/intents?status=pending").json()["pending"] == 0


def test_interview_debrief_unknown_interview_is_404(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post("/api/interview/9999/debrief", json={"debrief_md": "x"})
    assert r.status_code == 404


def test_interview_debrief_rejects_empty(atlas_app):
    from engine.db.models import DB

    with TestClient(atlas_app) as client:
        jid = _seed_job()
        with DB() as db:
            ivid = db.add_interview(jid, round="final")
        r = client.post(f"/api/interview/{ivid}/debrief", json={"debrief_md": "   "})
    assert r.status_code == 400


def test_interview_debrief_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        r = client.post(
            "/api/interview/1/debrief",
            json={"debrief_md": "x"},
            headers={"Origin": "https://evil.example"},
        )
    assert r.status_code == 403
