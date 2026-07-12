"""Cross-platform behavior of the CLI helpers added for Windows/WSL2 support.

`_open_local_file` must dispatch to the right opener per platform (macOS `open`,
WSL/Linux `wslview`/`xdg-open`) and degrade gracefully when none exists;
`_wsl_repo_warning` must only fire under WSL with the repo on a Windows drive.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import engine.cli as cli


@pytest.fixture
def record_run(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Capture argv passed to subprocess.run; never actually spawn anything."""
    calls: list[list[str]] = []

    def fake_run(argv, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        calls.append(list(argv))
        return None

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_open_local_file_darwin_uses_open(
    monkeypatch: pytest.MonkeyPatch, record_run: list[list[str]]
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cli._open_local_file("/tmp/x.html") is True
    assert record_run == [["open", "/tmp/x.html"]]


def test_open_local_file_wsl_uses_wslview(
    monkeypatch: pytest.MonkeyPatch, record_run: list[list[str]]
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    # Only wslview is on PATH; xdg-open is absent → wslview wins.
    monkeypatch.setattr(
        shutil, "which", lambda cmd: "/usr/bin/wslview" if cmd == "wslview" else None
    )
    assert cli._open_local_file("/tmp/x.html") is True
    assert record_run == [["wslview", "/tmp/x.html"]]


def test_open_local_file_prefers_wslview_when_both_present(
    monkeypatch: pytest.MonkeyPatch, record_run: list[list[str]]
) -> None:
    # A real WSL2 box commonly has BOTH xdg-open (xdg-utils) and wslview (wslu). The helper
    # must pick wslview — xdg-open on a headless WSL install can't reach the Windows browser.
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda cmd: f"/usr/bin/{cmd}")  # everything resolves
    assert cli._open_local_file("/tmp/x.html") is True
    assert record_run == [["wslview", "/tmp/x.html"]]


def test_open_local_file_linux_falls_back_to_xdg_open(
    monkeypatch: pytest.MonkeyPatch, record_run: list[list[str]]
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    # No wslview (plain Linux), but xdg-open exists.
    monkeypatch.setattr(
        shutil, "which", lambda cmd: "/usr/bin/xdg-open" if cmd == "xdg-open" else None
    )
    assert cli._open_local_file("/tmp/x.html") is True
    assert record_run == [["xdg-open", "/tmp/x.html"]]


def test_open_local_file_no_opener_returns_false(
    monkeypatch: pytest.MonkeyPatch, record_run: list[list[str]]
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    assert cli._open_local_file("/tmp/x.html") is False
    assert record_run == []  # nothing spawned


def test_wsl_repo_warning_flags_mnt_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "5.15.0-microsoft-standard-WSL2\n")
    monkeypatch.setattr(cli.paths, "REPO_ROOT", Path("/mnt/c/Users/x/atlas"))
    warn = cli._wsl_repo_warning()
    assert warn is not None
    assert "/mnt/c/Users/x/atlas" in warn


def test_wsl_repo_warning_silent_when_repo_in_linux_fs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "5.15.0-microsoft-standard-WSL2\n")
    monkeypatch.setattr(cli.paths, "REPO_ROOT", Path("/home/x/dev/atlas"))
    assert cli._wsl_repo_warning() is None


def test_wsl_repo_warning_none_when_not_wsl(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-WSL kernel string → no warning even if the path looks like /mnt.
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "6.8.0-generic\n")
    monkeypatch.setattr(cli.paths, "REPO_ROOT", Path("/mnt/data/atlas"))
    assert cli._wsl_repo_warning() is None


def test_wsl_repo_warning_none_when_osrelease_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # macOS / anywhere /proc is absent → read_text raises OSError → None.
    def boom(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
        raise OSError("no /proc")

    monkeypatch.setattr(Path, "read_text", boom)
    assert cli._wsl_repo_warning() is None


class _FakeDB:
    """Minimal stand-in for the DB context manager used by portfolio_open."""

    def __init__(self, portfolio: dict | None) -> None:
        self._p = portfolio

    def __enter__(self) -> _FakeDB:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def latest_portfolio(self) -> dict | None:
        return self._p


def test_portfolio_open_success_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Wiring: the right dict key flows to the opener and the success message prints.
    monkeypatch.setattr(cli, "_db", lambda: _FakeDB({"path_html": "/tmp/p.html"}))
    opened: list[str] = []
    monkeypatch.setattr(cli, "_open_local_file", lambda path: (opened.append(path), True)[1])
    printed: list[str] = []
    monkeypatch.setattr(
        cli.console, "print", lambda *a, **k: printed.append(" ".join(str(x) for x in a))
    )
    cli.portfolio_open()
    assert opened == ["/tmp/p.html"]  # p["path_html"], not some other key
    assert any("Abriendo" in p and "/tmp/p.html" in p for p in printed)


def test_portfolio_open_fallback_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    # No opener available → the manual-open fallback message prints (not the success one).
    monkeypatch.setattr(cli, "_db", lambda: _FakeDB({"path_html": "/tmp/p.html"}))
    monkeypatch.setattr(cli, "_open_local_file", lambda path: False)
    printed: list[str] = []
    monkeypatch.setattr(
        cli.console, "print", lambda *a, **k: printed.append(" ".join(str(x) for x in a))
    )
    cli.portfolio_open()
    assert any("manualmente" in p and "/tmp/p.html" in p for p in printed)
    assert not any("Abriendo" in p for p in printed)
