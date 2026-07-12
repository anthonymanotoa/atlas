from typer.testing import CliRunner

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
    db = DB(":memory:")
    db.init_schema()
    _seed(db, "adzuna", [(1, 0, None)] * 3)
    (row,) = [r for r in classify_sources(db) if r["source"] == "adzuna"]
    assert row["state"] == "ok_empty"
    assert "credencial" in row["hint"].lower() or "0 resultados" in row["hint"]


def test_unconfigured_error_marker():
    db = DB(":memory:")
    db.init_schema()
    _seed(db, "adzuna", [(0, 0, "unconfigured: missing ADZUNA_APP_ID")])
    (row,) = [r for r in classify_sources(db) if r["source"] == "adzuna"]
    assert row["state"] == "unconfigured"


def test_ok_with_data():
    db = DB(":memory:")
    db.init_schema()
    _seed(db, "greenhouse", [(1, 12, None)] * 3)
    (row,) = [r for r in classify_sources(db) if r["source"] == "greenhouse"]
    assert row["state"] == "ok"


def test_atlas_status_cli_colorizes_all_source_health_states(tmp_path, monkeypatch):
    """CLI-layer regression for Task 8: `atlas status` renders a health row for each of
    the four `classify_sources()` states (ok, ok_empty, unconfigured, error) through the
    `_STATE_STYLE` map without crashing, and surfaces each source's hint/error text.

    Redirects the CLI's `_db()` helper (see `engine.cli._db`) at a throwaway on-disk DB —
    the same monkeypatch approach `tests/test_cv_placeholder_cli.py` uses for
    `load_master_cv`, chosen over the `ATLAS_DATA_DIR` + module-reload dance in
    `tests/conftest.py` because `status` needs one specific seeded DB, not a reloaded
    app. A wide, colorless Rich console is swapped in too, so CliRunner's non-tty output
    doesn't wrap/truncate the hint column and break substring assertions.
    """
    from rich.console import Console

    import engine.cli as cli

    db_path = tmp_path / "status_test.db"
    db = DB(str(db_path))
    db.log_source_health("greenhouse", True, 12, None, 100)  # ok
    for _ in range(3):
        db.log_source_health("lever", True, 0, None, 50)  # ok_empty (3x zero-count streak)
    db.log_source_health("adzuna", False, 0, "unconfigured: sin credenciales", 5)  # unconfigured
    db.log_source_health("workday", False, 0, "timeout contactando workday", 500)  # error
    db.close()

    monkeypatch.setattr(cli, "_db", lambda: DB(str(db_path)))
    monkeypatch.setattr(cli, "console", Console(width=200, no_color=True))

    result = CliRunner().invoke(cli.app, ["status"])

    assert result.exit_code == 0, result.output

    def row_for(source: str) -> str:
        matches = [ln for ln in result.output.splitlines() if source in ln]
        assert matches, f"no output line mentions {source!r}:\n{result.output}"
        return matches[0]

    ok_row = row_for("greenhouse")
    assert "ok" in ok_row and "ok_empty" not in ok_row

    ok_empty_row = row_for("lever")
    assert "ok_empty" in ok_empty_row

    unconfigured_row = row_for("adzuna")
    assert "unconfigured" in unconfigured_row
    assert "sin credenciales" in unconfigured_row

    error_row = row_for("workday")
    assert "error" in error_row
    assert "timeout contactando workday" in error_row
