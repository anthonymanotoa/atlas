"""F3 §6.4: pre-scan determinista de knock-outs (visa, años, grado, idioma) con evidencia."""

from __future__ import annotations

from pathlib import Path

from engine.config import Criteria
from engine.knockouts import prescan

CRIT = Criteria(roles=["data scientist"], candidate_years=5, languages=["en", "es"])
CV = {
    "basics": {"name": "Jane Doe"},
    "education": [{"degree": "BSc Computer Science", "school": "UTPL"}],
}


def _job(desc: str, title: str = "Data Scientist") -> dict:
    return {"title": title, "description": desc}


def test_detects_work_authorization():
    w = prescan(_job("Applicants must be authorized to work in the United States."), CRIT, CV)
    assert any(x["code"] == "work_authorization" for x in w)
    assert (
        "authorized to work" in [x for x in w if x["code"] == "work_authorization"][0]["evidence"]
    )


def test_detects_no_sponsorship_and_clearance_once():
    w = prescan(
        _job("Visa sponsorship is not available. Active security clearance preferred."), CRIT, CV
    )
    codes = [x["code"] for x in w]
    assert codes.count("work_authorization") == 1  # un solo warning de visa, no spam


def test_detects_residency_knockout():
    # Real residency knock-outs (a country/place) MUST still fire.
    for desc in (
        "Applicants must be located in the United States.",
        "You must reside in Germany.",
        "You must live in Canada to be eligible.",
    ):
        assert any(x["code"] == "work_authorization" for x in prescan(_job(desc), CRIT, CV)), desc


def test_timezone_overlap_is_not_residency_knockout():
    # A timezone / working-hours overlap is a benign remote-friendly constraint, NOT a
    # hard residency knock-out — must NOT fire a work_authorization warning (FP guard).
    for desc in (
        "You must be located in a timezone with US overlap.",
        "Must be located in a time zone that overlaps EST.",
        "Must be located in a time-zone within GMT+/-3.",
        "You must be available during core hours (9-5 PST).",
    ):
        assert not any(x["code"] == "work_authorization" for x in prescan(_job(desc), CRIT, CV)), (
            desc
        )


def test_detects_years_gap_beyond_plus2():
    assert any(
        x["code"] == "years_gap"
        for x in prescan(_job("Requires 8+ years of experience."), CRIT, CV)
    )
    assert not any(
        x["code"] == "years_gap"
        for x in prescan(_job("Requires 6+ years of experience."), CRIT, CV)
    )


def test_detects_missing_degree_level():
    w = prescan(_job("A Master's degree in CS is required."), CRIT, CV)  # CV solo tiene BSc
    assert any(x["code"] == "degree" for x in w)
    # bachelor pedido + bachelor en CV → sin warning
    assert not any(
        x["code"] == "degree" for x in prescan(_job("Bachelor's degree required."), CRIT, CV)
    )


def test_degree_not_required_is_benign():
    # "preferred but not required" is a nice-to-have, not a knock-out — must NOT fire (FP guard).
    assert not any(
        x["code"] == "degree"
        for x in prescan(_job("PhD preferred but not required if you have experience."), CRIT, CV)
    )


def test_detects_required_language_outside_profile():
    w = prescan(_job("Fluency in German is a must."), CRIT, CV)
    assert any(x["code"] == "language" for x in w)
    assert not prescan(_job("Fluent in English required."), CRIT, CV)  # en ∈ languages


def test_clean_jd_yields_no_warnings():
    assert (
        prescan(_job("Great remote role building dashboards with Python and SQL."), CRIT, CV) == []
    )


def test_prescan_persisted_by_score_jobs(tmp_path: Path, monkeypatch):
    import json

    from engine.db.models import DB
    from engine.normalize import Job
    from engine.scoring.run import score_jobs

    monkeypatch.setattr("engine.scoring.run.load_master_cv", lambda: CV)
    monkeypatch.setattr("engine.scoring.run.load_ontology", lambda: {"python": []})
    db = DB(tmp_path / "t.db")
    db.upsert_job(
        Job(
            source="greenhouse",
            title="Data Scientist",
            company="Acme",
            location="Remote",
            is_remote=True,
            description="Must be authorized to work in the US. Python required.",
        )
    )
    score_jobs(db, CRIT)
    row = db.list_jobs()[0]
    warnings = json.loads(row["knockout_warnings"])
    assert warnings and warnings[0]["code"] == "work_authorization"
