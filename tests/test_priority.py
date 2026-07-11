"""Task 10: blended priority (fit vs CV-match legibility) — pure function + wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from engine.scoring.priority import priority


def test_priority_blends_fit_and_match():
    assert priority(100, 20) == 76.0


def test_priority_falls_back_to_fit_when_no_match():
    assert priority(80, None) == 80.0


def test_priority_treats_missing_fit_as_zero():
    assert priority(None, 50) == 15.0


def test_priority_both_missing_is_zero():
    assert priority(None, None) == 0.0


def test_top_sorts_by_priority_not_raw_fit(atlas_app, monkeypatch):
    """A lower-fit job with a strong CV match should outrank a higher-fit job with a weak
    match once `top` sorts by blended priority — the whole point of Task 10."""
    from typer.testing import CliRunner

    from engine.cli import app
    from engine.db.models import DB
    from engine.normalize import Job

    # Wide terminal so rich doesn't wrap the table and split the company names we grep for.
    monkeypatch.setenv("COLUMNS", "220")

    with DB() as db:
        low_fit_high_match = Job(
            source="greenhouse", title="Data Analyst", company="Acme", location="Remote"
        ).finalize()
        db.upsert_job(low_fit_high_match)
        db.set_fit(low_fit_high_match.id, 60, [], [])
        db.set_match(low_fit_high_match.id, 95, [])
        db.set_state(low_fit_high_match.id, "shortlisted", {"via": "test"})

        high_fit_no_match = Job(
            source="greenhouse", title="Data Scientist", company="Beta", location="Remote"
        ).finalize()
        db.upsert_job(high_fit_no_match)
        db.set_fit(high_fit_no_match.id, 70, [], [])
        db.set_state(high_fit_no_match.id, "shortlisted", {"via": "test"})

    # priority(60, 95) = 60*.7 + 95*.3 = 42 + 28.5 = 70.5 > priority(70, None) = 70.0
    runner = CliRunner()
    result = runner.invoke(app, ["top"])
    assert result.exit_code == 0
    first_row_idx = result.stdout.index("Acme")
    second_row_idx = result.stdout.index("Beta")
    assert first_row_idx < second_row_idx


def test_board_shortlisted_jobs_expose_priority(atlas_app):
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        job = Job(
            source="greenhouse", title="Data Analyst", company="Acme", location="Remote"
        ).finalize()
        db.upsert_job(job)
        db.set_fit(job.id, 100, [], [])
        db.set_match(job.id, 20, [])
        db.set_state(job.id, "shortlisted", {"via": "test"})

    with TestClient(atlas_app) as client:
        board = client.get("/api/board").json()
    shortlisted = board["jobs"]["shortlisted"]
    assert len(shortlisted) == 1
    assert shortlisted[0]["priority"] == 76.0
