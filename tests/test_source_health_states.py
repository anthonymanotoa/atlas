from engine.db.models import DB
from engine.discovery.health import classify_sources


def _seed(db, source, runs):  # runs: list[(ok, count, error)]
    for i, (ok, count, error) in enumerate(runs):
        db.conn.execute(
            "INSERT INTO source_health (source, run_at, ok, count, error) VALUES (?,?,?,?,?)",
            (source, f"2026-07-{8 + i:02d}T08:00:00Z", ok, count, error),
        )
    db.conn.commit()


def test_ok_empty_streak_is_flagged():
    db = DB(":memory:"); db.init_schema()
    _seed(db, "adzuna", [(1, 0, None)] * 3)
    (row,) = [r for r in classify_sources(db) if r["source"] == "adzuna"]
    assert row["state"] == "ok_empty"
    assert "credencial" in row["hint"].lower() or "0 resultados" in row["hint"]


def test_unconfigured_error_marker():
    db = DB(":memory:"); db.init_schema()
    _seed(db, "adzuna", [(0, 0, "unconfigured: missing ADZUNA_APP_ID")])
    (row,) = [r for r in classify_sources(db) if r["source"] == "adzuna"]
    assert row["state"] == "unconfigured"


def test_ok_with_data():
    db = DB(":memory:"); db.init_schema()
    _seed(db, "greenhouse", [(1, 12, None)] * 3)
    (row,) = [r for r in classify_sources(db) if r["source"] == "greenhouse"]
    assert row["state"] == "ok"
