"""F2 jobs columns: guarded migration + geo persistence through upsert_job."""

from __future__ import annotations

from engine.db.models import DB
from engine.normalize import Job


def test_migration_adds_f2_columns(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(jobs)")}
    assert {"geo_restriction", "geo_scope", "repost_count", "liveness_checked_at"} <= cols


def test_upsert_persists_geo_fields(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(
                source="himalayas",
                title="Data Engineer",
                company="Acme",
                location="Remote — US only",
                is_remote=True,
            )
        )
        row = db.list_jobs()[0]
    assert row["geo_scope"] == "us"
    assert row["geo_restriction"] == "Remote — US only"


def test_enrichment_upgrades_unknown_scope(tmp_path):
    """A richer source that reveals a restriction upgrades a previously-unknown scope."""
    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(source="linkedin", title="DE", company="Acme", location="Remote", is_remote=True)
        )
        assert db.list_jobs()[0]["geo_scope"] == "unknown"
        db.upsert_job(
            Job(
                source="greenhouse",
                title="DE",
                company="Acme",
                location="Remote",
                is_remote=True,
                description="You must reside in the United States.",
            )
        )
        row = db.list_jobs()[0]
    assert row["geo_scope"] == "us"


def test_migration_is_idempotent(tmp_path):
    """Running _migrate twice on the same DB must not raise (guarded ADD COLUMN)."""
    with DB(tmp_path / "atlas.db") as db:
        db._migrate()  # second run — must be a no-op, not a duplicate-column error
        cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(jobs)")}
    assert {"geo_restriction", "geo_scope", "repost_count", "liveness_checked_at"} <= cols
