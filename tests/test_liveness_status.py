"""Task 11: liveness activado por defecto y visible en `atlas status`.

`sweep_liveness()` (engine/discovery/liveness.py) already expires dead postings and
stamps `liveness_checked_at` — it was just gated behind `liveness.enabled: false` in
every sources.yaml, so nobody saw its effect. This locks two things:

1. The `status` CLI command surfaces the expired count and the last-sweep timestamp,
   so the sweep isn't silently invisible.
2. `liveness.enabled` defaults to `true` in the shipped config (repo + seeds), so the
   gate actually runs without the user having to discover and flip a YAML flag.
"""

from __future__ import annotations

import yaml
from typer.testing import CliRunner

from engine.db.models import DB
from engine.normalize import Job
from engine.paths import REPO_ROOT


def test_status_reports_expired_count_and_last_sweep(tmp_path, monkeypatch):
    """Seeds one `expired` job with a stamped `liveness_checked_at` and asserts
    `atlas status` mentions both the expired count and the sweep timestamp.

    Follows the same CLI-isolation approach as
    `tests/test_source_health_states.py::test_atlas_status_cli_colorizes_all_source_health_states`:
    monkeypatch `engine.cli._db` at a throwaway on-disk DB, and swap in a wide,
    colorless Rich console so CliRunner's non-tty output doesn't wrap/truncate.
    """
    import engine.cli as cli
    from rich.console import Console

    db_path = tmp_path / "liveness_status.db"
    db = DB(str(db_path))
    db.upsert_job(Job(source="lever", title="DS", company="Acme", url="https://x.co/jobs/1"))
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, "expired", {"reason": "http 404", "via": "liveness"})
    swept_at = "2026-07-10T09:00:00Z"
    db.conn.execute("UPDATE jobs SET liveness_checked_at=? WHERE id=?", (swept_at, jid))
    db.conn.commit()
    db.close()

    monkeypatch.setattr(cli, "_db", lambda: DB(str(db_path)))
    monkeypatch.setattr(cli, "console", Console(width=200, no_color=True))

    result = CliRunner().invoke(cli.app, ["status"])

    assert result.exit_code == 0, result.output
    liveness_lines = [ln for ln in result.output.splitlines() if "Liveness" in ln]
    assert liveness_lines, f"no output line mentions Liveness:\n{result.output}"
    liveness_line = liveness_lines[0]
    assert "1" in liveness_line and "expirados" in liveness_line
    assert swept_at[:19] in liveness_line


def test_status_reports_never_swept_when_no_liveness_checks(tmp_path, monkeypatch):
    """No job has ever been liveness-checked → status says so instead of a blank/None."""
    import engine.cli as cli
    from rich.console import Console

    db_path = tmp_path / "liveness_status_never.db"
    db = DB(str(db_path))
    db.upsert_job(Job(source="lever", title="DS", company="Acme", url="https://x.co/jobs/2"))
    db.close()

    monkeypatch.setattr(cli, "_db", lambda: DB(str(db_path)))
    monkeypatch.setattr(cli, "console", Console(width=200, no_color=True))

    result = CliRunner().invoke(cli.app, ["status"])

    assert result.exit_code == 0, result.output
    liveness_lines = [ln for ln in result.output.splitlines() if "Liveness" in ln]
    assert liveness_lines, f"no output line mentions Liveness:\n{result.output}"
    assert "nunca" in liveness_lines[0]
    assert "0 expirados" in liveness_lines[0]


def test_last_liveness_sweep_db_helper(tmp_path):
    """`DB.last_liveness_sweep()` returns None until a sweep stamps a job, then the max ts."""
    db = DB(str(tmp_path / "sweep_helper.db"))
    assert db.last_liveness_sweep() is None

    db.upsert_job(Job(source="lever", title="DS", company="Acme", url="https://x.co/jobs/3"))
    jid = db.list_jobs()[0]["id"]
    db.conn.execute(
        "UPDATE jobs SET liveness_checked_at=? WHERE id=?", ("2026-07-10T09:00:00Z", jid)
    )
    db.conn.commit()

    assert db.last_liveness_sweep() == "2026-07-10T09:00:00Z"


def test_liveness_enabled_by_default_in_shipped_configs():
    """`liveness.enabled` must be `true` out of the box — repo config and every seed pack."""
    for rel in (
        "config/sources.yaml",
        "config/seeds/data/sources.yaml",
        "config/seeds/architecture/sources.yaml",
        "config/seeds/default/sources.yaml",
    ):
        path = REPO_ROOT / rel
        data = yaml.safe_load(path.read_text())
        assert data["liveness"]["enabled"] is True, f"{rel}: liveness.enabled must default true"
        assert data["liveness"]["limit"] == 40, f"{rel}: liveness.limit should stay 40"
