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
    roles=["data scientist", "ai engineer"],
    role_aliases=["data specialist"],
    remote_required=True,
    salary_floor_usd=70000,
    salary_hard=False,
    must_haves=["sql", "python"],
    deal_breakers=["on-site only", "internship"],
    knockout_terms=["security clearance"],
    shortlist_threshold=62,
)


def test_natural_key_dedupe_across_company_suffix():
    a = compute_job_id("Acme Inc", "Senior Data Scientist", "Remote")
    b = compute_job_id("Acme", "senior data scientist", "remote")
    assert a == b


def test_upsert_idempotent_and_gapfills(db: DB):
    j1 = Job(source="greenhouse", title="Data Scientist", company="Acme Inc", location="Remote")
    assert db.upsert_job(j1) is True
    j2 = Job(
        source="indeed",
        title="Data Scientist",
        company="Acme",
        location="Remote",
        description="Full description here",
    )
    assert db.upsert_job(j2) is False  # same natural key → not created
    row = db.get_job(j1.finalize().id)
    assert row["description"] == "Full description here"  # gap-filled
    assert len(db.list_jobs()) == 1  # no duplicate


def test_scoring_disqualifies_onsite():
    from engine.scoring.fit import score_job

    job = {
        "title": "Senior Data Scientist",
        "is_remote": 0,
        "workplace_type": "onsite",
        "description": "on-site only role",
    }
    res = score_job(job, CRITERIA)
    assert res.disqualified and res.score <= 12


def test_scoring_shortlists_remote_senior_ds():
    from engine.scoring.fit import score_job

    job = {
        "title": "Senior Data Scientist",
        "is_remote": 1,
        "workplace_type": "remote",
        "description": "We use python and sql for ML.",
        "salary_min": 90000,
        "salary_max": 120000,
        "salary_interval": "yearly",
    }
    res = score_job(job, CRITERIA)
    assert not res.disqualified and res.score >= CRITERIA.shortlist_threshold


def test_scoring_flags_knockout_without_rejecting():
    from engine.scoring.fit import score_job

    job = {
        "title": "Data Scientist",
        "is_remote": 1,
        "description": "Requires an active Security Clearance. python sql",
    }
    res = score_job(job, CRITERIA)
    assert "security clearance" in res.knockouts


def test_tailor_never_fabricates_and_reports_coverage():
    from engine.config import load_ontology
    from engine.cv.tailor import tailor

    master = {
        "basics": {"name": "X", "summary": "ds"},
        "skills": ["Python", "SQL"],
        "experience": [
            {
                "title": "DS",
                "company": "Y",
                "highlights": ["Built models in Python", "Wrote SQL"],
                "skills": ["Python", "SQL"],
            }
        ],
    }
    job = {
        "title": "Data Scientist",
        "description": "Need Python, SQL and Tableau.",
        "apply_url": "https://boards.greenhouse.io/x",
    }
    res = tailor(master, job, load_ontology())
    skills_lower = " ".join(res.cv["skills"]).lower()
    assert "tableau" not in skills_lower  # not fabricated into the CV
    assert "tableau" in [m.lower() for m in res.missing]
    assert res.ats_target == "greenhouse"
    assert 0.0 <= res.coverage <= 1.0


def test_parse_check_passes_for_rendered_cv(tmp_path: Path):
    from engine.cv import parse_check, render

    cv = {
        "basics": {
            "name": "Ana Tester",
            "email": "a@b.com",
            "label": "Data Scientist",
            "summary": "Senior DS.",
        },
        "skills": ["Python", "SQL"],
        "experience": [
            {
                "title": "DS",
                "company": "Acme",
                "start": "Jan 2022",
                "end": "Present",
                "highlights": ["Did things with Python."],
            }
        ],
    }
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
    csv.write_text(
        "Notes:\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
        "Jane,Doe,http://x,,GitLab Inc,Engineer,01 Jan 2024\n"
    )
    assert import_connections_csv(db, csv) == 1
    assert match_referrals(db, "GitLab")[0]["name"] == "Jane Doe"
    assert match_referrals(db, "Totally Different Co") == []


# ── Plan 003: Lever salary interval canonicalization feeds fit scoring ───────────
def test_canonical_salary_interval_maps_lever_and_others():
    from engine.util import canonical_salary_interval

    assert canonical_salary_interval("per-month-salary") == "monthly"  # Lever form
    assert canonical_salary_interval("per-hour-wage") == "hourly"
    assert canonical_salary_interval("per-year-salary") == "yearly"
    assert canonical_salary_interval("annually") == "yearly"
    assert canonical_salary_interval("per-day-wage") == "daily"
    assert canonical_salary_interval("daily") == "daily"  # bare token round-trips too
    assert canonical_salary_interval("") is None
    assert canonical_salary_interval(None) is None


def test_monthly_salary_annualized_meets_floor():
    from engine.scoring.fit import score_job

    job = {
        "title": "Senior Data Scientist",
        "is_remote": 1,
        "workplace_type": "remote",
        "description": "python and sql",
        "salary_max": 10000,
        "salary_interval": "monthly",
    }
    res = score_job(job, CRITERIA)  # 10000/mo → 120k/yr ≥ 70k floor
    assert "salary meets floor" in res.reasons
    assert "salary below floor" not in res.reasons


# ── Plan 005: list_jobs tolerates a generator for `states` ───────────────────────
def test_list_jobs_accepts_generator(db: DB):
    db.upsert_job(Job(source="x", title="DS", company="Acme", location="Remote"))
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, "shortlisted")
    rows = db.list_jobs(
        states=(s for s in ["shortlisted", "ready"])
    )  # generator, consumed once internally
    assert len(rows) == 1 and rows[0]["state"] == "shortlisted"


# ── Plan 002: --only honors per-site selectors (indeed/linkedin) ─────────────────
def test_discover_only_indeed_filters_jobspy_sites(db: DB, monkeypatch):
    from engine.discovery import jobspy_source, runner

    captured = {}

    def _fetch(cfg, terms):
        captured["sites"] = cfg.get("sites")
        return {"indeed": []}

    monkeypatch.setattr(jobspy_source, "fetch", _fetch)
    runner.discover(
        db,
        sources_cfg={"jobspy": {"enabled": True, "sites": ["indeed", "linkedin"]}},
        companies=[],
        terms=["data scientist"],
        only={"indeed"},
    )
    assert captured["sites"] == ["indeed"]


def test_discover_only_ats_skips_jobspy(db: DB, monkeypatch):
    from engine.discovery import jobspy_source, runner

    calls = {"n": 0}

    def _fetch(cfg, terms):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(jobspy_source, "fetch", _fetch)
    runner.discover(
        db,
        sources_cfg={"jobspy": {"enabled": True, "sites": ["indeed", "linkedin"]}},
        companies=[],
        terms=["x"],
        only={"ats"},
    )
    assert calls["n"] == 0


# ── Plan 004: language is validated before it reaches the CV output path ─────────
def test_build_for_job_rejects_traversal_language(db: DB):
    from engine.cv.build import build_for_job

    db.upsert_job(Job(source="x", title="DS", company="Acme", location="Remote"))
    jid = db.list_jobs()[0]["id"]
    with pytest.raises(ValueError):
        build_for_job(db, jid, language="../../../etc/evil")


# ── Plan 006: the reply-aware follow-up cadence drafts every touch, idempotently ─
def _drain_followups(db: DB):
    """Mimic the brain's due-follow-up loop (variant-aware dedup)."""
    from engine.outreach import followups

    candidate = {"name": "Me"}
    drafted = set()
    for f in db.due_followups("9999"):
        d = followups.followup_text(db.get_job(f["job_id"]), candidate, f["touch_number"])
        if not db.has_message(f["job_id"], d.kind, variant=d.variant):
            db.add_message(
                f["job_id"],
                channel=d.channel,
                kind=d.kind,
                body=d.body,
                subject=d.subject,
                variant=d.variant,
                language=d.language,
                state="draft",
            )
            drafted.add(d.variant)
        db.mark_followup(f["id"], "done")
    return drafted


def test_followup_cadence_drafts_all_four_touches(db: DB):
    from engine.outreach import followups

    db.upsert_job(Job(source="x", title="DS", company="Acme", location="Remote"))
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, "applied")
    followups.schedule(db, jid, channel="email")
    assert len(db.followups_for_job(jid)) == 4
    assert _drain_followups(db) == {"touch1", "touch2", "touch3", "touch4"}
    msgs = db.messages_for(jid)
    assert sum(1 for m in msgs if m["kind"] == "follow_up") == 3  # was 1 before the dedup fix
    assert sum(1 for m in msgs if m["kind"] == "breakup") == 1


def test_followup_schedule_does_not_resurrect_done_touch(db: DB):
    from engine.outreach import followups

    db.upsert_job(Job(source="x", title="DS", company="Acme", location="Remote"))
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, "applied")
    followups.schedule(db, jid, channel="email")
    f1 = next(f for f in db.followups_for_job(jid) if f["touch_number"] == 1)
    db.mark_followup(f1["id"], "done")
    followups.schedule(db, jid, channel="email")  # catch-up re-run
    rows = db.followups_for_job(jid)
    assert len(rows) == 4
    assert sum(1 for r in rows if r["touch_number"] == 1) == 1  # not resurrected


# ── Plan 011: overview aggregates correctly; needs_action prioritizes replies ────
def test_overview_and_needs_action(db: DB):
    from engine import analytics

    for i in range(3):
        db.upsert_job(Job(source="x", title=f"DS{i}", company=f"Co{i}", location="Remote"))
    ids = [j["id"] for j in db.list_jobs()]
    db.set_state(ids[0], "ready")
    db.set_state(ids[1], "applied")
    db.set_state(ids[2], "responded")
    ov = analytics.overview(db)
    assert ov["total_jobs"] == 3
    assert ov["applied"] == 1
    assert ov["counts"].get("ready") == 1
    acts = analytics.needs_action(db)
    assert acts and acts[0]["priority"] == 0  # the reply sorts first


# ── Plan 018: Workday CXS parser + resolver host pattern (keyless path) ──────────
def test_workday_parses_fixture_payload(monkeypatch):
    from engine.config import CompanyTarget
    from engine.discovery.ats import workday

    payload = {
        "total": 1,
        "jobPostings": [
            {
                "title": "Senior Data Scientist",
                "externalPath": "/job/US-CA/Senior-DS_JR1",
                "locationsText": "Remote, US",
                "bulletFields": ["JR1"],
                "postedOn": "Posted Today",
            }
        ],
    }
    monkeypatch.setattr(workday, "post_json", lambda client, url, json=None: payload)
    t = CompanyTarget(
        company="Acme",
        ats="workday",
        instance="acme",
        token="AcmeCareers",
        careers_url="https://acme.wd5.myworkdayjobs.com/AcmeCareers",
    )
    jobs = workday.fetch(t, client=None)  # client unused (post_json is stubbed) — no network
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "workday"
    assert j.title == "Senior Data Scientist"
    assert j.source_job_id == "JR1"  # bulletFields[0]
    assert "acme.wd5.myworkdayjobs.com" in j.url and "/job/US-CA/Senior-DS_JR1" in j.url


def test_resolve_ats_detects_workday_host():
    from engine.discovery.registry import PATTERNS, _workday_site

    host = "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers"
    m = next((rx.search(host) for ats, rx in PATTERNS if ats == "workday"), None)
    assert m and m.group(1) == "acme"  # the gap this closes: no longer "No known ATS detected"
    assert _workday_site(host) == "AcmeCareers"  # locale segment skipped


# ── Plan 012: PDF parity — project descriptions are rendered (were dropped) ──────
def test_pdf_renders_project_description(tmp_path: Path):
    from engine.cv import render

    base = {"basics": {"name": "A"}, "projects": [{"name": "P1", "highlights": ["did x"]}]}
    desc = {
        "basics": {"name": "A"},
        "projects": [
            {
                "name": "P1",
                "highlights": ["did x"],
                "description": "An intentionally long project description repeated for size. " * 6,
            }
        ],
    }
    a = render.render_pdf(base, tmp_path / "a.pdf")
    b = render.render_pdf(desc, tmp_path / "b.pdf")
    assert a and b
    # The description flows into the PDF, so the with-description output is larger.
    assert (tmp_path / "b.pdf").stat().st_size > (tmp_path / "a.pdf").stat().st_size
