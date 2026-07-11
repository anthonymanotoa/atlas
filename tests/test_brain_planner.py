"""Task 18 — deterministic planner: `brain.run_brain.plan_and_enqueue` enqueues the new
research intents (company_research, contact_discovery, portfolio_research) IDEMPOTENTLY, and
`write_morning_brief` gains sections for stale intents, unhealthy sources, and new research.

Extracted from `run()` per the Task 18 brief so it can be unit-tested without paying for the
full pipeline (scoring/prepare need profile config that a bare tmp DB doesn't have).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from engine import intents as intent_queue
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _shortlisted_job(db: DB, company: str = "Acme") -> str:
    db.upsert_job(Job(source="x", title="DS", company=company, location="Remote"))
    job_id = db.list_jobs()[0]["id"]
    db.set_state(job_id, "shortlisted")
    return job_id


def _ready_job(db: DB, company: str = "Acme") -> str:
    db.upsert_job(Job(source="x", title="DS", company=company, location="Remote"))
    job_id = db.list_jobs()[0]["id"]
    db.set_state(job_id, "ready")
    return job_id


# ── company_research ──────────────────────────────────────────────────────────
def test_plan_enqueues_company_research_for_shortlisted_job_without_research(db: DB):
    from brain.run_brain import plan_and_enqueue

    job_id = _shortlisted_job(db)

    result = plan_and_enqueue(db, limit=5)

    assert result["company_research"] == 1
    pending = intent_queue.list_pending(db)
    matches = [i for i in pending if i["type"] == "company_research" and i["job_id"] == job_id]
    assert len(matches) == 1


def test_plan_is_idempotent_for_company_research(db: DB):
    from brain.run_brain import plan_and_enqueue

    _shortlisted_job(db)
    plan_and_enqueue(db, limit=5)
    result_second = plan_and_enqueue(db, limit=5)

    assert result_second["company_research"] == 0
    pending = [i for i in intent_queue.list_pending(db) if i["type"] == "company_research"]
    assert len(pending) == 1


def test_plan_skips_company_research_when_research_already_exists(db: DB):
    from brain.run_brain import plan_and_enqueue
    from engine.normalize import norm_company

    job_id = _shortlisted_job(db, company="Beta Inc")
    db.add_company_research(
        norm_company("Beta Inc"), job_id=job_id, summary="Already researched."
    )

    result = plan_and_enqueue(db, limit=5)

    assert result["company_research"] == 0
    assert not [i for i in intent_queue.list_pending(db) if i["type"] == "company_research"]


# ── contact_discovery ─────────────────────────────────────────────────────────
def test_plan_enqueues_contact_discovery_for_ready_job_without_brain_contact(db: DB):
    from brain.run_brain import plan_and_enqueue

    job_id = _ready_job(db)

    result = plan_and_enqueue(db, limit=5)

    assert result["contact_discovery"] == 1
    pending = intent_queue.list_pending(db)
    matches = [i for i in pending if i["type"] == "contact_discovery" and i["job_id"] == job_id]
    assert len(matches) == 1


def test_plan_is_idempotent_for_contact_discovery(db: DB):
    from brain.run_brain import plan_and_enqueue

    _ready_job(db)
    plan_and_enqueue(db, limit=5)
    result_second = plan_and_enqueue(db, limit=5)

    assert result_second["contact_discovery"] == 0
    pending = [i for i in intent_queue.list_pending(db) if i["type"] == "contact_discovery"]
    assert len(pending) == 1


def test_plan_skips_contact_discovery_when_brain_contact_already_known(db: DB):
    from brain.run_brain import plan_and_enqueue

    _ready_job(db, company="Gamma Co")
    db.upsert_research_contact(
        name="Jane Doe", company="Gamma Co", notes="[brain_research] confidence=high"
    )

    result = plan_and_enqueue(db, limit=5)

    assert result["contact_discovery"] == 0
    assert not [i for i in intent_queue.list_pending(db) if i["type"] == "contact_discovery"]


# ── portfolio_research ────────────────────────────────────────────────────────
def test_plan_enqueues_portfolio_research_when_never_reviewed(db: DB):
    from brain.run_brain import plan_and_enqueue

    assert db.last_peer_review() is None

    result = plan_and_enqueue(db, limit=5)

    assert result["portfolio_research"] == 1
    pending = [i for i in intent_queue.list_pending(db) if i["type"] == "portfolio_research"]
    assert len(pending) == 1


def test_plan_does_not_reenqueue_portfolio_research_when_pending_exists(db: DB):
    from brain.run_brain import plan_and_enqueue

    plan_and_enqueue(db, limit=5)
    result_second = plan_and_enqueue(db, limit=5)

    assert result_second["portfolio_research"] == 0
    pending = [i for i in intent_queue.list_pending(db) if i["type"] == "portfolio_research"]
    assert len(pending) == 1


def test_plan_skips_portfolio_research_when_recently_reviewed(db: DB):
    from brain.run_brain import plan_and_enqueue

    db.add_peer_portfolio(peer_name="Someone", peer_portfolio_url="https://example.com/p")

    result = plan_and_enqueue(db, limit=5)

    assert result["portfolio_research"] == 0
    assert not intent_queue.list_pending(db)


def test_plan_reenqueues_portfolio_research_when_review_older_than_7_days(db: DB):
    from brain.run_brain import plan_and_enqueue

    pid = db.add_peer_portfolio(peer_name="Someone", peer_portfolio_url="https://example.com/p")
    stale = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    db.conn.execute("UPDATE peer_portfolios SET reviewed_at=? WHERE id=?", (stale, pid))
    db.conn.commit()

    result = plan_and_enqueue(db, limit=5)

    assert result["portfolio_research"] == 1


# ── run() integration ─────────────────────────────────────────────────────────
def test_run_calls_planner_and_reports_enqueued_intents(tmp_path, monkeypatch):
    import engine.paths as paths
    from brain.run_brain import run

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    with DB(tmp_path / "t.db") as db2:
        summary = run(db2, do_discover=False)

    assert "enqueued_intents" in summary
    # empty DB: nothing shortlisted/ready, but portfolio_research always fires once.
    assert summary["enqueued_intents"]["portfolio_research"] == 1


def test_dry_run_does_not_invoke_planner(tmp_path, monkeypatch):
    import engine.paths as paths
    from brain.run_brain import run

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    with DB(tmp_path / "t.db") as db2:
        summary = run(db2, do_discover=False, dry_run=True)
        assert not intent_queue.list_pending(db2)

    assert "enqueued_intents" not in summary


# ── morning brief sections ────────────────────────────────────────────────────
def test_brief_lists_stale_intents(tmp_path, monkeypatch):
    import engine.paths as paths
    from brain.run_brain import run

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    with DB(tmp_path / "t.db") as db2:
        iid = intent_queue.enqueue(db2, "upskill_report", {})
        old = (datetime.now(UTC) - timedelta(hours=72)).isoformat()
        db2.conn.execute("UPDATE intents SET created_at=? WHERE id=?", (old, iid))
        db2.conn.commit()
        run(db2, do_discover=False)

    brief = (tmp_path / "MORNING_BRIEF.md").read_text()
    assert "Intents atascados" in brief
    assert iid in brief


def test_brief_lists_unhealthy_sources(tmp_path, monkeypatch):
    import engine.paths as paths
    from brain.run_brain import run

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    with DB(tmp_path / "t.db") as db2:
        db2.conn.execute(
            "INSERT INTO source_health (source, ok, count, error, run_at) VALUES (?,?,?,?,?)",
            ("adzuna", 1, 0, None, datetime.now(UTC).isoformat()),
        )
        db2.conn.commit()
        run(db2, do_discover=False)

    brief = (tmp_path / "MORNING_BRIEF.md").read_text()
    assert "adzuna" in brief


def test_brief_summarizes_new_research(tmp_path, monkeypatch):
    import engine.paths as paths
    from brain.run_brain import run

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    with DB(tmp_path / "t.db") as db2:
        run(db2, do_discover=False)

    brief = (tmp_path / "MORNING_BRIEF.md").read_text()
    assert "Research nuevo" in brief
    assert "portfolio_research" in brief
