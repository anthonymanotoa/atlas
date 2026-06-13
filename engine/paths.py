"""Filesystem layout for Atlas. Single source of truth for every path.

Multi-profile: each profile is a self-contained mini-Atlas root under
``profiles/<id>/{config,profile,data}``. The active profile is a process-global
pointer recorded in ``profiles/registry.json``; the dashboard flips it in-process via
:func:`set_profile`, while the CLI/brain pin it once via ``--profile`` / ``$ATLAS_PROFILE``.

Consumers MUST read these paths *late* (``import engine.paths as paths`` then
``paths.OUTBOX_DIR``), never ``from engine.paths import OUTBOX_DIR`` — a value import
freezes the path at import time and would not follow a profile switch.

Pre-migration / legacy: if no registry exists yet, paths resolve to the original
repo-root ``config/``, ``profile/``, ``data/`` so Atlas behaves exactly as before until
``atlas profiles init`` runs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROFILES_DIR = REPO_ROOT / "profiles"
REGISTRY_PATH = PROFILES_DIR / "registry.json"

# These are (re)assigned by `_apply()` below; declared here for clarity / tooling.
PROFILE_ID: str | None = None
PROFILE_ROOT: Path = REPO_ROOT
DATA_DIR: Path = REPO_ROOT / "data"
DB_PATH: Path = DATA_DIR / "atlas.db"
INBOX_DIR: Path = DATA_DIR / "inbox"
OUTBOX_DIR: Path = DATA_DIR / "outbox"
CONFIG_DIR: Path = REPO_ROOT / "config"
PROFILE_DIR: Path = REPO_ROOT / "profile"
CRITERIA_PATH: Path = CONFIG_DIR / "criteria.md"
COMPANIES_PATH: Path = CONFIG_DIR / "companies.yaml"
SOURCES_PATH: Path = CONFIG_DIR / "sources.yaml"
ONTOLOGY_PATH: Path = CONFIG_DIR / "ontology.yaml"
MASTER_CV_PATH: Path = PROFILE_DIR / "master_cv.yaml"


def _resolve_active() -> str | None:
    """The profile to use, or ``None`` to use the legacy (pre-migration) layout.

    Precedence: explicit ``$ATLAS_PROFILE`` (CLI/brain --profile) > registry "active" > legacy.
    """
    env = os.environ.get("ATLAS_PROFILE")
    if env:
        return env
    try:
        return json.loads(REGISTRY_PATH.read_text()).get("active")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _apply(profile_id: str | None) -> None:
    """Recompute every path global for ``profile_id`` (or the legacy layout if None)."""
    global PROFILE_ID, PROFILE_ROOT, DATA_DIR, DB_PATH, INBOX_DIR, OUTBOX_DIR
    global CONFIG_DIR, PROFILE_DIR, CRITERIA_PATH, COMPANIES_PATH, SOURCES_PATH
    global ONTOLOGY_PATH, MASTER_CV_PATH

    PROFILE_ID = profile_id
    if profile_id is None:
        # Legacy / pre-migration: identical to Atlas's original single-user behavior.
        PROFILE_ROOT = REPO_ROOT
        CONFIG_DIR = REPO_ROOT / "config"
        PROFILE_DIR = REPO_ROOT / "profile"
        # $ATLAS_DATA_DIR override is honored ONLY in legacy mode; in profile mode the
        # data dir is always profile-relative so isolation can't be silently broken.
        DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", REPO_ROOT / "data")).resolve()
    else:
        PROFILE_ROOT = PROFILES_DIR / profile_id
        CONFIG_DIR = PROFILE_ROOT / "config"
        PROFILE_DIR = PROFILE_ROOT / "profile"
        DATA_DIR = (PROFILE_ROOT / "data").resolve()

    DB_PATH = DATA_DIR / "atlas.db"
    INBOX_DIR = DATA_DIR / "inbox"
    OUTBOX_DIR = DATA_DIR / "outbox"
    CRITERIA_PATH = CONFIG_DIR / "criteria.md"
    COMPANIES_PATH = CONFIG_DIR / "companies.yaml"
    SOURCES_PATH = CONFIG_DIR / "sources.yaml"
    ONTOLOGY_PATH = CONFIG_DIR / "ontology.yaml"
    MASTER_CV_PATH = PROFILE_DIR / "master_cv.yaml"


def set_profile(profile_id: str) -> None:
    """Point all paths at a specific profile. Used by the dashboard switch and CLI/brain.

    Re-points the module globals in-process; the next short-lived ``DB()`` opens the new
    profile's database. Single uvicorn worker only — the pointer is process-global state.
    """
    _apply(profile_id)


# Resolve once at import so the globals exist exactly as before.
_apply(_resolve_active())


def ensure_dirs() -> None:
    """Create the runtime data directories for the active profile if they don't exist."""
    for d in (DATA_DIR, INBOX_DIR, OUTBOX_DIR):
        d.mkdir(parents=True, exist_ok=True)


def example_fallback(path: Path) -> Path:
    """Return `path` if it exists, else its committed `.example` sibling.

    Lets the engine run out-of-the-box on the example config before the user
    has created their private versions (criteria.md, companies.yaml, ...).
    """
    if path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    example = path.with_name(f"{stem}.example{suffix}")
    return example if example.exists() else path
