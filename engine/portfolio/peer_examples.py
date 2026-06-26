"""Domain-scoped reference portfolios + the cross-cutting patterns that make them good.

Each industry/domain ships its OWN curated, quality-vetted set under
``config/seeds/<domain>/portfolio_references.yaml`` (``examples`` + ``patterns``). The portfolio
research endpoint loads the set for the ACTIVE profile's domain, so an architect sees
architecture references and a data scientist sees data references — never each other's. Atlas
never clones a peer's site; it only points at the live link + an honest read of what to learn.

A domain with no references file gets an EMPTY set, so a brand-new domain starts blank instead
of inheriting another field's portfolios. The data/AI set lives in the committed ``data`` pack.

Field names are the API/UI contract: each example is ``peer_name · url · role_match ·
key_strengths[] · what_to_steal[]``; ``patterns`` is a dict of named bullet lists.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from engine.paths import REPO_ROOT

_SEEDS_DIR = REPO_ROOT / "config" / "seeds"
_REFERENCES_FILE = "portfolio_references.yaml"
_EMPTY: dict = {"examples": [], "patterns": {}}


def _references_path(domain: str) -> Path | None:
    """The references file for ``domain``, or ``None`` if that domain ships none."""
    cand = _SEEDS_DIR / domain / _REFERENCES_FILE
    return cand if cand.exists() else None


def load_references(domain: str | None) -> dict:
    """Return ``{"examples": [...], "patterns": {...}}`` for ``domain`` (empty if none exists)."""
    path = _references_path(domain or "data")
    if path is None:
        return {"examples": [], "patterns": {}}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return {"examples": [], "patterns": {}}
    return {
        "examples": data.get("examples") or [],
        "patterns": data.get("patterns") or {},
    }


def peer_examples_for(domain: str | None) -> list[dict]:
    """Curated reference portfolios for ``domain`` (empty list if the domain has none)."""
    return load_references(domain)["examples"]


def portfolio_patterns_for(domain: str | None) -> dict:
    """Cross-cutting portfolio patterns for ``domain`` (empty dict if the domain has none)."""
    return load_references(domain)["patterns"]
