"""Filesystem layout for Atlas. Single source of truth for every path."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", REPO_ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "atlas.db"
INBOX_DIR = DATA_DIR / "inbox"
OUTBOX_DIR = DATA_DIR / "outbox"

CONFIG_DIR = REPO_ROOT / "config"
PROFILE_DIR = REPO_ROOT / "profile"

CRITERIA_PATH = CONFIG_DIR / "criteria.md"
COMPANIES_PATH = CONFIG_DIR / "companies.yaml"
SOURCES_PATH = CONFIG_DIR / "sources.yaml"
ONTOLOGY_PATH = CONFIG_DIR / "ontology.yaml"
MASTER_CV_PATH = PROFILE_DIR / "master_cv.yaml"


def ensure_dirs() -> None:
    """Create the runtime data directories if they do not exist."""
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
