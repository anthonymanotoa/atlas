"""CLI-layer template-CV warning (Task 2): `doctor` (and, by the same helper,
`tailor` / `prep` / `portfolio generate`) must WARN loudly — never block — when
the active master CV is still the seed template.

`load_master_cv` is imported at module scope in `engine.cli` specifically so it
can be monkeypatched as `engine.cli.load_master_cv` here, without touching the
real profile/master_cv.yaml or the example fallback on disk.
"""

from __future__ import annotations

from typer.testing import CliRunner

from engine.cli import app

runner = CliRunner()

TEMPLATE_CV = {"basics": {"name": "Ada Lovelace", "email": "ada@example.com"}}
REAL_CV = {"basics": {"name": "Jane Roe", "email": "jane@gmail.com"}}


def test_doctor_flags_template_cv(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("engine.cli.load_master_cv", lambda: TEMPLATE_CV)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "plantilla" in result.output.lower() or "Ada Lovelace" in result.output


def test_doctor_does_not_flag_real_cv(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("engine.cli.load_master_cv", lambda: REAL_CV)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "plantilla" not in result.output.lower()
    assert "Ada Lovelace" not in result.output
