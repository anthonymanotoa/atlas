"""F3: migraciones aditivas (knockout_warnings, score_breakdown, followups.kind) + tabla stories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _seed(db: DB) -> str:
    db.upsert_job(Job(source="greenhouse", title="Data Scientist", company="Acme", location="Remote"))
    return db.list_jobs()[0]["id"]


def test_migration_adds_f3_columns(db: DB):
    cols_jobs = {r["name"] for r in db.conn.execute("PRAGMA table_info(jobs)")}
    cols_fu = {r["name"] for r in db.conn.execute("PRAGMA table_info(followups)")}
    assert {"knockout_warnings", "score_breakdown"} <= cols_jobs
    assert "kind" in cols_fu


def test_migration_is_idempotent(db: DB):
    # Running _migrate again must not raise (columns already exist).
    db._migrate()
    db._migrate()
    cols_jobs = {r["name"] for r in db.conn.execute("PRAGMA table_info(jobs)")}
    assert {"knockout_warnings", "score_breakdown"} <= cols_jobs


def test_set_fit_persists_warnings_and_breakdown(db: DB):
    jid = _seed(db)
    db.set_fit(jid, 71.0, ["role matches title"], [],
               warnings=[{"code": "work_authorization", "label": "pide autorización US", "evidence": "authorized to work in the US"}],
               breakdown={"base": 50.0, "final": 71.0, "factors": [{"factor": "role", "delta": 25.0, "note": "role matches title"}]})
    row = db.get_job(jid)
    assert json.loads(row["knockout_warnings"])[0]["code"] == "work_authorization"
    assert json.loads(row["score_breakdown"])["final"] == 71.0


def test_set_fit_without_kwargs_keeps_previous_breakdown(db: DB):
    jid = _seed(db)
    db.set_fit(jid, 71.0, [], [], breakdown={"base": 50.0, "final": 71.0, "factors": []})
    db.set_fit(jid, 60.0, [], [])  # llamada legacy: no borra el breakdown previo
    assert json.loads(db.get_job(jid)["score_breakdown"])["final"] == 71.0


def test_add_followup_with_kind(db: DB):
    jid = _seed(db)
    fid = db.add_followup(jid, channel="email", touch_number=1, due_at="2026-07-11T00:00:00+00:00", kind="applied")
    rows = db.followups_for_job(jid)
    assert rows and rows[0]["id"] == fid and rows[0]["kind"] == "applied"


def test_pending_followups_joins_job_fields(db: DB):
    jid = _seed(db)
    db.add_followup(jid, channel="email", touch_number=1, due_at="2026-07-11T00:00:00+00:00", kind="applied")
    rows = db.pending_followups()
    assert rows[0]["company"] == "Acme" and rows[0]["title"] == "Data Scientist"
    assert rows[0]["job_id"] == jid and rows[0]["state"] == "pending"


def test_stories_crud_roundtrip(db: DB):
    sid = db.add_story(title="Pipeline caído en Black Friday", situation="ETL crítico caído",
                       task="Restaurar en <1h", action="Rollback + circuit breaker",
                       result="Recuperado en 40min", reflection="Alertas proactivas desde entonces",
                       skills=["python", "airflow"])
    s = db.get_story(sid)
    assert s["title"].startswith("Pipeline") and s["skills"] == ["python", "airflow"]
    assert db.update_story(sid, {"result": "Recuperado en 35min", "skills": ["python", "sql"]}) is True
    s2 = db.get_story(sid)
    assert s2["result"] == "Recuperado en 35min" and s2["skills"] == ["python", "sql"]
    assert s2["updated_at"] >= s["updated_at"]
    assert len(db.list_stories()) == 1
    assert db.delete_story(sid) is True
    assert db.list_stories() == [] and db.get_story(sid) is None


def test_update_story_rejects_unknown_field(db: DB):
    sid = db.add_story(title="X")
    with pytest.raises(ValueError):
        db.update_story(sid, {"evil": "x"})


def test_delete_story_unknown_id_returns_false(db: DB):
    assert db.delete_story(99999) is False
