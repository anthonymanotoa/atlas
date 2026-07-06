"""engine/cv/review.py — dump del CV tailoreado + (Task 7) apply_edit/resolve_flag."""

from __future__ import annotations

import pytest
import yaml

import engine.paths as paths
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    with DB(tmp_path / "t.db") as d:
        d.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="Data Scientist",
                company="Acme",
                url="https://x/1",
                description="We need Python and SQL for analytics.",
            )
        )
        yield d


def test_dump_tailored_cv_writes_parseable_yaml(db):
    from engine.cv.review import dump_tailored_cv

    jid = db.list_jobs()[0]["id"]
    path = dump_tailored_cv(db, jid)
    assert path.name == "cv_for_review.yaml"
    cv = yaml.safe_load(path.read_text())
    assert isinstance(cv, dict)  # estructura de master_cv tailoreada


def test_dump_unknown_job_raises(db):
    from engine.cv.review import dump_tailored_cv

    with pytest.raises(ValueError):
        dump_tailored_cv(db, "nope")


# ── Task 7: writer + apply_edit + resolve_flag ─────────────────────────────────
def _review_result() -> dict:
    return {
        "edits": [
            {
                "file": "cv",
                "old_string": "Data Scientist",
                "new_string": "Data Scientist, Analytics",
                "reason": "mirror the posting title",
            }
        ],
        "critique": {
            "missed_keywords": ["sql: ya está en skills, súbelo al summary"],
            "company_angles": ["Acme publica su stack en el blog — cita dbt"],
            "reframing": ["el bullet de ETL puede enmarcarse hacia analytics"],
            "tone_register": ["nada que señalar"],
        },
        "flags": [
            {
                "file": "cv",
                "bullet": "",  # se rellena en el test con un highlight real
                "classification": "Flag",
                "reason": "¿lideraste tú el proyecto o participaste?",
                "softened": "Contributed to the ETL redesign that cut runtime 40%",
            }
        ],
    }


def test_cv_review_writer_persists_and_marks_done(db):
    from engine import intents

    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cv_review", {}, job_id=jid)
    intents.mark_running(db, iid)
    result = _review_result()
    result["flags"] = []  # este test no ejercita flags
    ref = intents.apply_result(db, iid, result)
    assert ref.startswith("cv_review:")
    review = db.cv_reviews_for(jid)[0]
    assert review["critique"]["company_angles"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_cv_review_writer_rejects_missing_critique_category(db):
    from engine import intents

    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cv_review", {}, job_id=jid)
    intents.mark_running(db, iid)
    bad = _review_result()
    del bad["critique"]["tone_register"]
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, bad)
    assert intents.get_intent(db, iid)["status"] == "running"  # queda reintentable


def test_cv_review_writer_rejects_bad_edit_file(db):
    from engine import intents

    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cv_review", {}, job_id=jid)
    intents.mark_running(db, iid)
    bad = _review_result()
    bad["flags"] = []
    bad["edits"][0]["file"] = "bio"  # not in EDIT_FILES
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, bad)
    assert intents.get_intent(db, iid)["status"] == "running"


def test_cv_review_writer_rejects_flag_without_softened(db):
    from engine import intents

    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cv_review", {}, job_id=jid)
    intents.mark_running(db, iid)
    bad = _review_result()
    bad["flags"][0]["bullet"] = "some current bullet"
    del bad["flags"][0]["softened"]  # a Flag needs a softened alternative
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, bad)
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_edit_on_cv_rewrites_dump_and_rerenders(db):
    from engine.cv.review import apply_edit, dump_tailored_cv

    jid = db.list_jobs()[0]["id"]
    dump_path = dump_tailored_cv(db, jid)
    old = "Data Scientist"  # el label/target title siempre está en el dump
    assert dump_path.read_text().count(old) >= 1
    rid = db.add_cv_review(
        jid,
        intent_id=None,
        cv_version_id=None,
        edits=[
            {
                "file": "cv",
                "old_string": old,
                "new_string": "Lead Data Scientist",
                "reason": "t",
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
    # old_string debe ser único: si aparece >1 vez, apply_edit debe rechazarlo
    text = dump_path.read_text()
    if text.count(old) != 1:
        with pytest.raises(ValueError):
            apply_edit(db, rid, 0)
        # hazlo único apuntando al label
        unique_old = "label: Data Scientist"
        assert text.count(unique_old) == 1
        db.set_cv_review_edits(
            rid,
            [
                {
                    "file": "cv",
                    "old_string": unique_old,
                    "new_string": "label: Lead Data Scientist",
                    "reason": "t",
                }
            ],
        )
    out = apply_edit(db, rid, 0)
    assert out["ok"] and out["applied_ref"].startswith("cv_version:")
    assert "Lead Data Scientist" in dump_path.read_text()
    edits = db.get_cv_review(rid)["edits"]
    assert edits[0]["applied"] is True
    assert db.cv_versions_for(jid)  # se re-renderizó una versión


def test_apply_edit_non_matching_old_string_fails_gracefully(db):
    from engine.cv.review import apply_edit, dump_tailored_cv

    jid = db.list_jobs()[0]["id"]
    dump_tailored_cv(db, jid)
    rid = db.add_cv_review(
        jid,
        intent_id=None,
        cv_version_id=None,
        edits=[
            {
                "file": "cv",
                "old_string": "nope-this-string-is-not-in-the-cv",
                "new_string": "x",
                "reason": "t",
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
    with pytest.raises(ValueError):  # not a 500 — a careful, refused edit
        apply_edit(db, rid, 0)
    assert db.get_cv_review(rid)["edits"][0].get("applied") is not True
    assert not db.cv_versions_for(jid)  # nothing re-rendered


# ── Task 7: apply_edit on a message body (cover letter / recruiter / hiring_manager) ──
# The message branch must mirror the cv branch's uniqueness guard: old_string appears
# EXACTLY once, or the edit is refused with the body left untouched.
_COVER_LETTER = (
    "Dear Hiring Manager,\n\n"
    "I am excited to apply for the Data Scientist role at Acme. "
    "My background in Python and SQL analytics is a strong match.\n\n"
    "Sincerely,\nJane Doe"
)


def _add_review_with_message_edit(db, jid, old_string, new_string="x"):
    return db.add_cv_review(
        jid,
        intent_id=None,
        cv_version_id=None,
        edits=[
            {
                "file": "cover_letter",
                "old_string": old_string,
                "new_string": new_string,
                "reason": "t",
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


def test_apply_edit_on_message_unique_old_string_applies(db):
    from engine.cv.review import apply_edit

    jid = db.list_jobs()[0]["id"]
    mid = db.add_message(jid, channel="email", kind="cover_letter", body=_COVER_LETTER)
    rid = _add_review_with_message_edit(db, jid, old_string="Jane Doe", new_string="Jane A. Doe")
    out = apply_edit(db, rid, 0)
    assert out["ok"] and out["applied_ref"] == f"message:{mid}"
    body = db.messages_for(jid)[-1]["body"]
    assert "Jane A. Doe" in body and "Jane Doe" not in body
    assert db.get_cv_review(rid)["edits"][0]["applied"] is True


def test_apply_edit_on_message_non_unique_old_string_fails_and_leaves_body(db):
    from engine.cv.review import apply_edit

    jid = db.list_jobs()[0]["id"]
    # A body where "Acme" appears twice — the ambiguous edit the guard must refuse.
    body = "Acme is great. I want to work at Acme."
    db.add_message(jid, channel="email", kind="cover_letter", body=body)
    assert body.count("Acme") == 2
    rid = _add_review_with_message_edit(db, jid, old_string="Acme", new_string="Acme Corp")
    with pytest.raises(ValueError):  # not a 500 — a careful, refused edit
        apply_edit(db, rid, 0)
    assert db.messages_for(jid)[-1]["body"] == body  # body UNCHANGED
    assert db.get_cv_review(rid)["edits"][0].get("applied") is not True


def test_apply_edit_on_message_absent_old_string_fails(db):
    from engine.cv.review import apply_edit

    jid = db.list_jobs()[0]["id"]
    db.add_message(jid, channel="email", kind="cover_letter", body=_COVER_LETTER)
    rid = _add_review_with_message_edit(db, jid, old_string="this-string-is-not-in-the-letter")
    with pytest.raises(ValueError):
        apply_edit(db, rid, 0)
    assert db.messages_for(jid)[-1]["body"] == _COVER_LETTER  # untouched


def test_apply_edit_message_missing_draft_fails(db):
    from engine.cv.review import apply_edit

    jid = db.list_jobs()[0]["id"]
    rid = _add_review_with_message_edit(db, jid, old_string="anything")
    with pytest.raises(ValueError):  # no cover_letter drafted → refused, not a 500
        apply_edit(db, rid, 0)


def test_apply_edit_index_out_of_range_raises(db):
    from engine.cv.review import apply_edit

    jid = db.list_jobs()[0]["id"]
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
        flags=[],
    )
    with pytest.raises(ValueError):
        apply_edit(db, rid, 0)


def test_resolve_flag_drop_removes_bullet_and_rerenders(db):
    import yaml as _yaml

    from engine.cv.review import dump_tailored_cv, resolve_flag

    jid = db.list_jobs()[0]["id"]
    dump_path = dump_tailored_cv(db, jid)
    cv = _yaml.safe_load(dump_path.read_text())
    experiences = [e for e in cv.get("experience", []) if e.get("highlights")]
    if not experiences:  # el master de ejemplo siempre trae highlights; guard por si acaso
        pytest.skip("example master CV has no highlights")
    bullet = experiences[0]["highlights"][0]
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
                "bullet": bullet,
                "classification": "Flag",
                "reason": "r",
                "softened": "softened version",
            }
        ],
    )
    out = resolve_flag(db, rid, 0, "drop")
    assert out["ok"]
    assert bullet not in dump_path.read_text()
    assert db.get_cv_review(rid)["flags"][0]["resolution"] == "drop"


def test_resolve_flag_soften_replaces_bullet(db):
    import yaml as _yaml

    from engine.cv.review import dump_tailored_cv, resolve_flag

    jid = db.list_jobs()[0]["id"]
    dump_path = dump_tailored_cv(db, jid)
    cv = _yaml.safe_load(dump_path.read_text())
    experiences = [e for e in cv.get("experience", []) if e.get("highlights")]
    if not experiences:
        pytest.skip("example master CV has no highlights")
    bullet = experiences[0]["highlights"][0]
    softened = "Contributed to the pipeline that cut runtime measurably."
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
                "bullet": bullet,
                "classification": "Flag",
                "reason": "r",
                "softened": softened,
            }
        ],
    )
    out = resolve_flag(db, rid, 0, "soften")
    assert out["ok"]
    text = dump_path.read_text()
    assert softened in text
    assert bullet not in text
    assert db.get_cv_review(rid)["flags"][0]["resolution"] == "soften"


def test_resolve_flag_keep_only_annotates(db):
    from engine.cv.review import dump_tailored_cv, resolve_flag

    jid = db.list_jobs()[0]["id"]
    dump_tailored_cv(db, jid)
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
                "bullet": "whatever",
                "classification": "Flag",
                "reason": "r",
                "softened": "s",
            }
        ],
    )
    out = resolve_flag(db, rid, 0, "keep")
    assert out["ok"]
    assert db.get_cv_review(rid)["flags"][0]["resolution"] == "keep"
    assert not db.cv_versions_for(jid)  # keep must NOT re-render


def test_resolve_flag_invalid_action_raises(db):
    from engine.cv.review import resolve_flag

    jid = db.list_jobs()[0]["id"]
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
            {"file": "cv", "bullet": "b", "classification": "Flag", "reason": "r", "softened": "s"}
        ],
    )
    with pytest.raises(ValueError):
        resolve_flag(db, rid, 0, "nuke")
