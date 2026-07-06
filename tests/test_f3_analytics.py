"""F3 §6.2: funnel con tasas, score floor empírico, conversión por dimensión, tiempos de respuesta."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine import analytics
from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _mk(db: DB, n: int, *, source="greenhouse", title="Data Scientist", wt="remote") -> str:
    db.upsert_job(Job(source=source, source_job_id=str(n), title=title,
                      company=f"Acme{n}", location="Remote", workplace_type=wt,
                      url=f"https://x/{n}"))
    return [j for j in db.list_jobs() if j["company"] == f"Acme{n}"][0]["id"]


def test_funnel_counts_and_rates(db: DB):
    a, b = _mk(db, 1), _mk(db, 2)
    for jid in (a, b):
        db.set_state(jid, "scored")
        db.set_state(jid, "shortlisted")
        db.set_state(jid, "applied")
    db.set_state(a, "responded")
    stages = {s["stage"]: s for s in analytics.funnel(db)}
    assert stages["discovered"]["count"] == 2 and stages["discovered"]["rate"] is None
    assert stages["applied"]["count"] == 2
    assert stages["responded"]["count"] == 1 and stages["responded"]["rate"] == 0.5


def test_score_floor_empirical(db: DB):
    a, b, c = _mk(db, 1), _mk(db, 2), _mk(db, 3)
    db.set_fit(a, 71.0, [], [])
    db.set_fit(b, 64.0, [], [])
    db.set_fit(c, 40.0, [], [])
    db.set_state(a, "applied")
    db.set_state(a, "responded")
    db.record_outcome(b, "Acme2", final_state="interviewed")
    # c (score 40) no tiene outcome positivo → el floor es 64, no 40
    assert analytics.score_floor(db) == 64.0


def test_score_floor_none_without_positives(db: DB):
    _mk(db, 1)
    assert analytics.score_floor(db) is None


def test_conversion_by_source_and_role_term(db: DB):
    crit = Criteria(roles=["data scientist", "ml engineer"])
    a = _mk(db, 1, source="greenhouse", title="Data Scientist")
    b = _mk(db, 2, source="lever", title="ML Engineer")
    for jid in (a, b):
        db.set_state(jid, "applied")
    db.set_state(a, "responded")
    by_src = {r["key"]: r for r in analytics.conversion_by(db, "source")}
    assert by_src["greenhouse"]["applied"] == 1 and by_src["greenhouse"]["response_rate"] == 1.0
    assert by_src["lever"]["response_rate"] == 0.0
    by_term = {r["key"]: r for r in analytics.conversion_by(db, "role_term", crit)}
    assert by_term["data scientist"]["responded"] == 1
    assert by_term["ml engineer"]["responded"] == 0


def test_conversion_by_unknown_dim_raises(db: DB):
    with pytest.raises(ValueError):
        analytics.conversion_by(db, "astrology")


def test_response_times_from_timestamps_and_outcomes(db: DB):
    a = _mk(db, 1)
    db.set_state(a, "applied")
    db.conn.execute("UPDATE jobs SET applied_at='2026-06-01T00:00:00+00:00', "
                    "responded_at='2026-06-08T00:00:00+00:00' WHERE id=?", (a,))
    db.conn.commit()
    db.record_outcome(None, "Beta Corp", final_state="responded", response_days=3)
    rt = analytics.response_times(db)
    assert rt["n"] == 2 and rt["avg_days"] == 5.0 and rt["median_days"] == 5.0
