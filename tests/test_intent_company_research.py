"""company_research intent (Task 14): the brain researches the company behind a job posting
and the writer validates + persists {summary, signals?, sources?} into `company_research`, keyed
by normalized company name so the outreach package can surface it across jobs at the same
company. Malformed results (missing/non-str summary) raise and leave the intent `running`."""

from __future__ import annotations

import pytest

from engine import intents
from engine.db.models import DB
from engine.normalize import Job, norm_company


@pytest.fixture
def db(tmp_path):
    with DB(tmp_path / "t.db") as d:
        yield d


def _job(db, source_job_id="1", company="Acme Robotics", title="Data Scientist"):
    db.upsert_job(
        Job(
            source="lever",
            source_job_id=source_job_id,
            title=title,
            company=company,
            url=f"https://x/{source_job_id}",
            description="Build cool things.",
        )
    )
    return [j for j in db.list_jobs() if j["company"] == company][0]["id"]


def test_company_research_is_a_registered_intent_type():
    assert "company_research" in intents.INTENT_TYPES
    assert intents.PROMPT_FILES["company_research"] == "company_research.md"


def test_context_includes_job_brief_and_no_existing_research(db):
    jid = _job(db)
    iid = intents.enqueue(db, "company_research", {}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["company"] == "Acme Robotics"
    assert ctx["job_brief"]["id"] == jid
    assert ctx["existing_research"] is None


def test_context_surfaces_prior_research_for_the_same_company(db):
    jid = _job(db)
    db.add_company_research(
        norm_company("Acme Robotics"),
        job_id=None,
        summary="Series B robotics startup, ~120 employees.",
        signals=["hiring surge on LinkedIn"],
        sources=["https://acme.example/about"],
    )
    iid = intents.enqueue(db, "company_research", {}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["existing_research"]["summary"].startswith("Series B")
    assert ctx["existing_research"]["signals"] == ["hiring surge on LinkedIn"]


def test_apply_result_creates_row_and_marks_done(db):
    jid = _job(db)
    iid = intents.enqueue(db, "company_research", {}, job_id=jid)
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {
            "summary": "Series B robotics startup, ~120 employees, hiring fast.",
            "signals": ["3 open roles on the careers page", "raised $40M in 2026"],
            "sources": ["https://acme.example/careers", "https://acme.example/press"],
        },
    )
    assert ref.startswith("company_research:")
    rid = int(ref.split(":")[1])
    row = db.company_research_for(norm_company("Acme Robotics"))
    assert row is not None
    assert row["id"] == rid
    assert row["summary"].startswith("Series B")
    assert row["signals"] == ["3 open roles on the careers page", "raised $40M in 2026"]
    assert row["sources"] == ["https://acme.example/careers", "https://acme.example/press"]
    assert row["job_id"] == jid
    assert intents.get_intent(db, iid)["status"] == "done"


def test_apply_result_defaults_signals_and_sources_to_empty(db):
    jid = _job(db, source_job_id="2", company="Beta Co")
    iid = intents.enqueue(db, "company_research", {}, job_id=jid)
    intents.mark_running(db, iid)
    intents.apply_result(db, iid, {"summary": "Small consultancy, ~10 people."})
    row = db.company_research_for(norm_company("Beta Co"))
    assert row["signals"] == []
    assert row["sources"] == []


def test_apply_result_missing_summary_raises_and_stays_running(db):
    jid = _job(db, source_job_id="3", company="Gamma Inc")
    iid = intents.enqueue(db, "company_research", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"signals": ["x"]})
    assert intents.get_intent(db, iid)["status"] == "running"
    assert db.company_research_for(norm_company("Gamma Inc")) is None


def test_apply_result_non_str_summary_raises(db):
    jid = _job(db, source_job_id="4", company="Delta LLC")
    iid = intents.enqueue(db, "company_research", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"summary": {"not": "a string"}})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_company_research_for_returns_most_recent(db):
    norm = norm_company("Epsilon")
    db.add_company_research(norm, job_id=None, summary="old", signals=[], sources=[])
    db.add_company_research(norm, job_id=None, summary="new", signals=[], sources=[])
    row = db.company_research_for(norm)
    assert row["summary"] == "new"


def test_write_package_includes_company_research_section(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.outreach.build import write_package

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    jid = _job(db, source_job_id="5", company="Zeta Robotics")
    db.add_company_research(
        norm_company("Zeta Robotics"),
        job_id=jid,
        summary="Seed-stage robotics company building warehouse arms.",
        signals=["3 open eng roles"],
        sources=["https://zeta.example"],
    )
    path = write_package(db, jid, language="es")
    text = path.read_text()
    assert "Sobre la empresa" in text
    assert "Seed-stage robotics company" in text


def test_write_package_omits_company_research_section_when_absent(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.outreach.build import write_package

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    jid = _job(db, source_job_id="6", company="Eta NoResearch")
    path = write_package(db, jid, language="es")
    text = path.read_text()
    assert "Sobre la empresa" not in text
