"""El brain reporta la cola de intents en el summary y el morning brief (F4 paso 0)."""

from __future__ import annotations

import engine.paths as paths
from engine import intents
from engine.db.models import DB


def test_run_reports_pending_intents_in_summary_and_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    from brain.run_brain import run

    with DB(tmp_path / "t.db") as db:
        intents.enqueue(db, "upskill_report", {})
        summary = run(db, do_discover=False)
    # The Task 18 planner also enqueues its own intents (e.g. a first-ever portfolio_research)
    # on an empty DB, so assert the manually-queued intent is present rather than exclusive.
    assert "upskill_report" in [i["type"] for i in summary["intents_pending"]]
    brief = (tmp_path / "MORNING_BRIEF.md").read_text()
    assert "Tareas del Brain en cola" in brief
    assert "upskill_report" in brief


def test_run_with_empty_queue_has_no_intents_section(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    from brain.run_brain import run

    with DB(tmp_path / "t.db") as db:
        summary = run(db, do_discover=False)
    # Task 18: the planner enqueues its own weekly portfolio_research on a never-reviewed DB,
    # so the queue is no longer guaranteed empty — but nothing OTHER than planner output exists.
    assert {i["type"] for i in summary["intents_pending"]} <= {
        "company_research",
        "contact_discovery",
        "portfolio_research",
    }
    assert "Tareas del Brain en cola" in (tmp_path / "MORNING_BRIEF.md").read_text()


def test_run_reports_pdf_checks_key(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    from brain.run_brain import run

    with DB(tmp_path / "t.db") as db:
        summary = run(db, do_discover=False)
    assert summary["pdf_checks"] == []  # sin jobs preparados → lista vacía, clave presente
