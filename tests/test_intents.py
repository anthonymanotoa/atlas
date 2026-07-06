"""Cola de intents (F4): enqueue/list/transiciones. Los writers por tipo se testean
en las tareas de cada tipo; aquí solo el ciclo de vida genérico."""

from __future__ import annotations

import pytest

from engine import intents
from engine.db.models import DB


@pytest.fixture
def db(tmp_path):
    with DB(tmp_path / "t.db") as d:
        yield d


def test_enqueue_and_list_pending(db):
    iid = intents.enqueue(db, "cv_review", {"language": "en"}, job_id=None)
    assert iid.startswith("in_")
    rows = intents.list_intents(db, status="pending")
    assert [r["id"] for r in rows] == [iid]
    assert rows[0]["payload"] == {"language": "en"}
    assert rows[0]["status"] == "pending" and rows[0]["created_at"]


def test_enqueue_unknown_type_raises(db):
    with pytest.raises(ValueError):
        intents.enqueue(db, "world_peace", {})


def test_lifecycle_pending_running_done(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    assert intents.get_intent(db, iid)["status"] == "running"
    intents.mark_done(db, iid, "upskill_report:1")
    row = intents.get_intent(db, iid)
    assert row["status"] == "done"
    assert row["result_ref"] == "upskill_report:1"
    assert row["completed_at"]


def test_mark_running_only_from_pending_or_error(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_done(db, iid, "x:1")
    with pytest.raises(ValueError):
        intents.mark_running(db, iid)


def test_error_intent_can_be_retried(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_error(db, iid, "boom")
    row = intents.get_intent(db, iid)
    assert row["status"] == "error" and row["error"] == "boom" and row["completed_at"]
    intents.mark_running(db, iid)  # reintento permitido
    assert intents.get_intent(db, iid)["status"] == "running"


def test_mark_done_requires_running(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):
        intents.mark_done(db, iid, "x:1")


def test_list_pending_only_returns_pending(db):
    pend = intents.enqueue(db, "cv_review", {})
    done = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, done)
    intents.mark_done(db, done, "x:1")
    running = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, running)
    assert {r["id"] for r in intents.list_pending(db)} == {pend}


def test_all_six_intent_types_enqueue(db):
    assert set(intents.INTENT_TYPES) == {
        "cv_review",
        "legitimacy_batch",
        "upskill_report",
        "interview_prep_deep",
        "profile_expand",
        "cover_letter",
    }
    for t in intents.INTENT_TYPES:
        iid = intents.enqueue(db, t)
        assert intents.get_intent(db, iid)["type"] == t


def test_apply_result_rejects_unknown_writer_without_touching_db(db):
    """A known type with no registered writer (skeleton) leaves the intent `running`
    and raises — the brain can re-run once the writer lands."""
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"ok": True})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_result_requires_running_and_dict(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):  # still pending
        intents.apply_result(db, iid, {"ok": True})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):  # non-dict result
        intents.apply_result(db, iid, ["not", "a", "dict"])


def test_apply_result_routes_to_registered_writer(db, monkeypatch):
    """apply_result validates the type, calls its writer, and marks done with the ref."""
    seen: dict = {}

    def _fake_writer(db_, intent, result):
        seen["intent_type"] = intent["type"]
        seen["result"] = result
        return "upskill_report:42"

    monkeypatch.setitem(intents._RESULT_WRITERS, "upskill_report", _fake_writer)
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    ref = intents.apply_result(db, iid, {"score": 7})
    assert ref == "upskill_report:42"
    assert seen == {"intent_type": "upskill_report", "result": {"score": 7}}
    row = intents.get_intent(db, iid)
    assert row["status"] == "done" and row["result_ref"] == "upskill_report:42"
