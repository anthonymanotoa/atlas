"""Tests for multi-profile support: path re-pointing, registry, seeding, owner pin.

Network-free and side-effect-free: profile-tree tests run against a tmp dir, and the
process-global path state is snapshotted/restored so nothing leaks into other tests.
"""

from __future__ import annotations

import pytest

import engine.paths as paths
from engine import profiles


@pytest.fixture
def restore_paths():
    """Snapshot & restore the process-global active profile around a test."""
    saved = paths.PROFILE_ID
    yield
    paths._apply(saved)


@pytest.fixture
def tmp_registry(tmp_path, monkeypatch):
    """Point the profiles module's repo root + registry at a tmp tree with seeds."""
    (tmp_path / "config").mkdir()
    (tmp_path / "profile").mkdir()
    (tmp_path / "config" / "criteria.example.md").write_text("---\nroles: []\n---\n# crit")
    (tmp_path / "config" / "companies.example.yaml").write_text("companies: []\n")
    (tmp_path / "config" / "sources.yaml").write_text("sources: {}\n")
    (tmp_path / "config" / "ontology.yaml").write_text("skills: {}\n")
    (tmp_path / "profile" / "master_cv.example.yaml").write_text("basics: {}\n")
    profiles_dir = tmp_path / "profiles"
    monkeypatch.setattr(profiles, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(profiles, "PROFILES_DIR", profiles_dir)
    monkeypatch.setattr(profiles, "REGISTRY_PATH", profiles_dir / "registry.json")
    return tmp_path


# ── path re-pointing ──────────────────────────────────────────────────────────
def test_set_profile_repoints_every_path(restore_paths):
    paths.set_profile("alpha")
    assert paths.PROFILE_ID == "alpha"
    assert paths.DB_PATH == paths.PROFILES_DIR / "alpha" / "data" / "atlas.db"
    assert paths.OUTBOX_DIR == paths.PROFILES_DIR / "alpha" / "data" / "outbox"
    assert paths.CRITERIA_PATH == paths.PROFILES_DIR / "alpha" / "config" / "criteria.md"
    assert paths.MASTER_CV_PATH == paths.PROFILES_DIR / "alpha" / "profile" / "master_cv.yaml"

    paths.set_profile("beta")
    assert paths.DB_PATH == paths.PROFILES_DIR / "beta" / "data" / "atlas.db"
    assert paths.DB_PATH != paths.PROFILES_DIR / "alpha" / "data" / "atlas.db"


def test_db_without_arg_follows_active_profile(tmp_path, monkeypatch, restore_paths):
    monkeypatch.setattr(paths, "PROFILES_DIR", tmp_path / "profiles")
    paths.set_profile("tester")
    from engine.db.models import DB

    with DB() as db:  # no explicit path → must follow the active profile
        db.conn.execute("SELECT 1")
    assert paths.DB_PATH.exists()
    assert "tester" in str(paths.DB_PATH)


def test_explicit_db_path_still_wins(tmp_path, restore_paths):
    """The tests/app contract: DB(path) ignores the active profile."""
    from engine.db.models import DB

    paths.set_profile("whatever")
    target = tmp_path / "explicit.db"
    with DB(target) as db:
        db.conn.execute("SELECT 1")
    assert target.exists()


# ── registry + lifecycle ──────────────────────────────────────────────────────
def test_create_profile_seeds_and_registers(tmp_registry):
    res = profiles.create_profile("alex", "Alex")
    assert res["created"]
    root = profiles.PROFILES_DIR / "alex"
    assert (root / "config" / "criteria.md").read_text().endswith("# crit")
    assert (root / "config" / "sources.yaml").exists()
    assert (root / "profile" / "master_cv.yaml").exists()
    assert (root / "data" / "inbox").is_dir() and (root / "data" / "outbox").is_dir()
    assert profiles.exists("alex")
    assert any(p["id"] == "alex" and p["label"] == "Alex" for p in profiles.list_profiles())
    # idempotent
    assert profiles.create_profile("alex")["created"] is False


def test_init_owner_is_idempotent_and_marks_owner(tmp_registry):
    res = profiles.init_owner()
    assert res["migrated"] is True
    assert profiles.get_active() == "owner"
    assert profiles.is_owner("owner") is True
    assert profiles.is_owner("alex") is False
    assert profiles.is_owner(None) is True  # legacy single user
    assert profiles.init_owner()["migrated"] is False  # re-run is a no-op


def test_set_label_renames_profile(tmp_registry):
    profiles.create_profile("alex", "Alex")
    assert profiles.set_label("alex", "Alejandra") == "Alejandra"
    assert any(p["id"] == "alex" and p["label"] == "Alejandra" for p in profiles.list_profiles())
    with pytest.raises(ValueError):
        profiles.set_label("alex", "   ")  # empty label rejected
    with pytest.raises(ValueError):
        profiles.set_label("ghost", "X")  # unknown profile rejected


def test_reconcile_labels_heals_legacy_dueno_from_cv(tmp_registry):
    profiles.init_owner()
    cv = profiles.PROFILES_DIR / "owner" / "profile" / "master_cv.yaml"
    cv.write_text("basics:\n  name: Ada Lovelace\n")
    profiles.set_label("owner", "Dueño")  # the legacy placeholder label
    assert profiles.reconcile_labels() is True
    assert any(
        p["id"] == "owner" and p["label"] == "Ada Lovelace" for p in profiles.list_profiles()
    )
    assert profiles.reconcile_labels() is False  # idempotent once healed


def test_set_active_rejects_unknown(tmp_registry):
    profiles.create_profile("alex", "Alex")
    profiles.set_active("alex")
    assert profiles.get_active() == "alex"
    with pytest.raises(ValueError):
        profiles.set_active("ghost")


@pytest.mark.parametrize("bad", ["", "../etc", "Has Space", "/abs", "a/b", "UP", "weird*"])
def test_valid_id_rejects_dangerous(bad):
    assert profiles.valid_id(bad) is False


@pytest.mark.parametrize("good", ["owner", "alex", "alex-2", "a_b", "x1"])
def test_valid_id_accepts_safe(good):
    assert profiles.valid_id(good) is True


# ── domain concept (P-domain-agnostic) ────────────────────────────────────────
def test_create_profile_persists_domain(tmp_registry):
    profiles.create_profile("lucy", "Lucy", domain="architecture")
    assert profiles.domain_of("lucy") == "architecture"
    assert any(
        p["id"] == "lucy" and p.get("domain") == "architecture"
        for p in profiles.list_profiles()
    )


def test_domain_defaults_to_data_when_missing(tmp_registry):
    profiles.create_profile("bob", "Bob")  # no domain arg
    assert profiles.domain_of("bob") == "data"
    assert profiles.domain_of("ghost") == "data"  # unknown profile → safe default


def test_cli_create_accepts_domain(tmp_registry):
    from typer.testing import CliRunner

    from engine.cli import app

    result = CliRunner().invoke(
        app, ["profiles", "create", "lucy", "--label", "Lucy", "--domain", "architecture"]
    )
    assert result.exit_code == 0, result.output
    assert profiles.domain_of("lucy") == "architecture"
