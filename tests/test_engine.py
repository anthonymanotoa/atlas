"""Unit tests locking the engine's load-bearing guarantees.

These are network-free: dedupe/idempotency, scoring rules, no-fabrication tailoring,
parse-safety, reply-aware follow-ups, and referral matching.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job, compute_job_id


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


CRITERIA = Criteria(
    roles=["data scientist", "ai engineer"], role_aliases=["data specialist"],
    remote_required=True, salary_floor_usd=70000, salary_hard=False,
    must_haves=["sql", "python"], deal_breakers=["on-site only", "internship"],
    knockout_terms=["security clearance"], shortlist_threshold=62,
)


def test_natural_key_dedupe_across_company_suffix():
    a = compute_job_id("Acme Inc", "Senior Data Scientist", "Remote")
    b = compute_job_id("Acme", "senior data scientist", "remote")
    assert a == b


def test_upsert_idempotent_and_gapfills(db: DB):
    j1 = Job(source="greenhouse", title="Data Scientist", company="Acme Inc", location="Remote")
    assert db.upsert_job(j1) is True
    j2 = Job(source="indeed", title="Data Scientist", company="Acme",
             location="Remote", description="Full description here")
    assert db.upsert_job(j2) is False                      # same natural key → not created
    row = db.get_job(j1.finalize().id)
    assert row["description"] == "Full description here"   # gap-filled
    assert len(db.list_jobs()) == 1                        # no duplicate


def test_scoring_disqualifies_onsite():
    from engine.scoring.fit import score_job
    job = {"title": "Senior Data Scientist", "is_remote": 0, "workplace_type": "onsite",
           "description": "on-site only role"}
    res = score_job(job, CRITERIA)
    assert res.disqualified and res.score <= 12


def test_scoring_shortlists_remote_senior_ds():
    from engine.scoring.fit import score_job
    job = {"title": "Senior Data Scientist", "is_remote": 1, "workplace_type": "remote",
           "description": "We use python and sql for ML.", "salary_min": 90000,
           "salary_max": 120000, "salary_interval": "yearly"}
    res = score_job(job, CRITERIA)
    assert not res.disqualified and res.score >= CRITERIA.shortlist_threshold


def test_scoring_flags_knockout_without_rejecting():
    from engine.scoring.fit import score_job
    job = {"title": "Data Scientist", "is_remote": 1,
           "description": "Requires an active Security Clearance. python sql"}
    res = score_job(job, CRITERIA)
    assert "security clearance" in res.knockouts


def test_tailor_never_fabricates_and_reports_coverage():
    from engine.config import load_ontology
    from engine.cv.tailor import tailor
    master = {"basics": {"name": "X", "summary": "ds"}, "skills": ["Python", "SQL"],
              "experience": [{"title": "DS", "company": "Y",
                              "highlights": ["Built models in Python", "Wrote SQL"],
                              "skills": ["Python", "SQL"]}]}
    job = {"title": "Data Scientist", "description": "Need Python, SQL and Tableau.",
           "apply_url": "https://boards.greenhouse.io/x"}
    res = tailor(master, job, load_ontology())
    skills_lower = " ".join(res.cv["skills"]).lower()
    assert "tableau" not in skills_lower            # not fabricated into the CV
    assert "tableau" in [m.lower() for m in res.missing]
    assert res.ats_target == "greenhouse"
    assert 0.0 <= res.coverage <= 1.0


def test_parse_check_passes_for_rendered_cv(tmp_path: Path):
    from engine.cv import parse_check, render
    cv = {"basics": {"name": "Ana Tester", "email": "a@b.com", "label": "Data Scientist",
                     "summary": "Senior DS."},
          "skills": ["Python", "SQL"],
          "experience": [{"title": "DS", "company": "Acme", "start": "Jan 2022",
                          "end": "Present", "highlights": ["Did things with Python."]}]}
    out = tmp_path / "cv.docx"
    render.render_docx(cv, out)
    ok, issues = parse_check.check(out, cv)
    assert ok, issues


def test_followups_halt_on_reply(db: DB):
    from engine.outreach import followups
    db.upsert_job(Job(source="x", title="DS", company="Acme", location="Remote"))
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, "applied")
    followups.schedule(db, jid, channel="email")
    assert len(db.due_followups("9999")) == 4
    followups.register_reply(db, jid)
    assert len(db.due_followups("9999")) == 0
    assert db.get_job(jid)["state"] == "responded"


def test_connections_import_and_referral_match(db: DB, tmp_path: Path):
    from engine.referrals.connections import import_connections_csv, match_referrals
    csv = tmp_path / "Connections.csv"
    csv.write_text("Notes:\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
                   "Jane,Doe,http://x,,GitLab Inc,Engineer,01 Jan 2024\n")
    assert import_connections_csv(db, csv) == 1
    assert match_referrals(db, "GitLab")[0]["name"] == "Jane Doe"
    assert match_referrals(db, "Totally Different Co") == []
