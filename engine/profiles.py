"""Profile registry + lifecycle for Atlas multi-profile support.

A profile is a self-contained mini-Atlas root under ``profiles/<id>/{config,profile,data}``.
The registry (``profiles/registry.json``) lists the profiles and records the active one.

There is NO authentication here — this is profile *selection* and data *isolation*, not
security. Atlas binds to 127.0.0.1 and is meant for a few trusted users on one Mac.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml

from engine.paths import PROFILES_DIR, REGISTRY_PATH, REPO_ROOT

OWNER_ID = "owner"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# Legacy/placeholder owner labels we auto-replace with the real name from the CV, so nobody
# is ever shown the cryptic "Dueño". (The owner used to be hardcoded as "Dueño".)
_PLACEHOLDER_LABELS = {"", "dueño", "dueno", "owner", "mi perfil", "owner profile"}

# (destination relative to a profile root, seed relative to the repo root). Seeds let a
# brand-new profile boot on the committed examples, ready to edit.
_SEEDS: list[tuple[str, str]] = [
    ("config/criteria.md", "config/criteria.example.md"),
    ("config/companies.yaml", "config/companies.example.yaml"),
    ("config/sources.yaml", "config/sources.yaml"),
    ("config/ontology.yaml", "config/ontology.yaml"),
    ("profile/master_cv.yaml", "profile/master_cv.example.yaml"),
]


# ── id validation (paths are built from the id → guard against traversal) ─────
def valid_id(profile_id: str) -> bool:
    return bool(profile_id and _ID_RE.match(profile_id))


def _require_valid(profile_id: str) -> str:
    if not valid_id(profile_id):
        raise ValueError(
            f"invalid profile id {profile_id!r}: use lowercase letters, digits, '-' or '_'"
        )
    return profile_id


# ── registry I/O ──────────────────────────────────────────────────────────────
def _read_registry() -> dict:
    try:
        return json.loads(REGISTRY_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"active": OWNER_ID, "profiles": []}


def _write_registry(reg: dict) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


def list_profiles() -> list[dict]:
    return _read_registry().get("profiles", [])


def get_active() -> str:
    return _read_registry().get("active", OWNER_ID)


def exists(profile_id: str) -> bool:
    return any(p["id"] == profile_id for p in list_profiles())


def is_owner(profile_id: str | None) -> bool:
    """True for the owner profile — and for the legacy/pre-migration single user (None)."""
    if profile_id is None:
        return True
    for p in list_profiles():
        if p["id"] == profile_id:
            return bool(p.get("is_owner"))
    return False


def set_active(profile_id: str) -> None:
    _require_valid(profile_id)
    reg = _read_registry()
    if not any(p["id"] == profile_id for p in reg.get("profiles", [])):
        raise ValueError(f"unknown profile {profile_id!r}")
    reg["active"] = profile_id
    _write_registry(reg)


# ── labels (display name) ─────────────────────────────────────────────────────
def cv_name_of(profile_id: str) -> str | None:
    """The `basics.name` from a profile's own master_cv.yaml, if present and non-empty."""
    cv_path = _profile_root(profile_id) / "profile" / "master_cv.yaml"
    if not cv_path.exists():
        return None
    try:
        data = yaml.safe_load(cv_path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return None
    return ((data.get("basics") or {}).get("name") or "").strip() or None


def set_label(profile_id: str, label: str) -> str:
    """Rename a profile (its display label in the selector). Returns the saved label."""
    _require_valid(profile_id)
    label = (label or "").strip()[:60]
    if not label:
        raise ValueError("label must not be empty")
    reg = _read_registry()
    for p in reg.get("profiles", []):
        if p["id"] == profile_id:
            p["label"] = label
            _write_registry(reg)
            return label
    raise ValueError(f"unknown profile {profile_id!r}")


def reconcile_labels() -> bool:
    """Self-heal placeholder labels (e.g. the legacy "Dueño") to the profile's real CV name.

    Idempotent and safe to call on every startup: only rewrites the registry when a profile
    still carries a placeholder label AND its CV provides a name. No-op in legacy mode (no
    registry). Returns True if anything changed."""
    reg = _read_registry()
    changed = False
    for p in reg.get("profiles", []):
        if (p.get("label") or "").strip().lower() in _PLACEHOLDER_LABELS:
            name = cv_name_of(p["id"])
            if name and name != p.get("label"):
                p["label"] = name
                changed = True
    if changed:
        _write_registry(reg)
    return changed


def _register(profile_id: str, label: str, *, owner: bool = False, domain: str = "data") -> None:
    reg = _read_registry()
    profiles = reg.setdefault("profiles", [])
    if not any(p["id"] == profile_id for p in profiles):
        entry: dict = {"id": profile_id, "label": label, "domain": domain}
        if owner:
            entry["is_owner"] = True
        profiles.append(entry)
    reg.setdefault("active", profile_id)
    _write_registry(reg)


def domain_of(profile_id: str | None) -> str:
    """The industry/domain of a profile (selects its seed pack & content vocabulary).

    Defaults to ``"data"`` for legacy profiles created before the domain concept and for
    unknown ids — so existing single-domain installs behave exactly as before."""
    for p in list_profiles():
        if p["id"] == profile_id:
            return p.get("domain") or "data"
    return "data"


# ── lifecycle ───────────────────────────────────────────────────────────────
def _profile_root(profile_id: str) -> Path:
    return PROFILES_DIR / profile_id


def _seed_missing(root: Path) -> None:
    """Copy committed seeds into the profile for any files it doesn't have yet."""
    for dest_rel, seed_rel in _SEEDS:
        dest = root / dest_rel
        if dest.exists():
            continue
        seed = REPO_ROOT / seed_rel
        if seed.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(seed), str(dest))


def create_profile(profile_id: str, label: str | None = None, domain: str = "data") -> dict:
    """Create a new, ready-to-edit profile seeded from the committed templates for ``domain``."""
    _require_valid(profile_id)
    root = _profile_root(profile_id)
    created = not root.exists()
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "profile").mkdir(parents=True, exist_ok=True)
    (root / "data" / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "data" / "outbox").mkdir(parents=True, exist_ok=True)
    _seed_missing(root)
    _register(profile_id, label or profile_id.capitalize(), domain=domain)
    return {"profile": profile_id, "created": created, "root": str(root), "domain": domain}


def init_owner() -> dict:
    """One-time migration of the legacy single-user layout into ``profiles/owner/``.

    Idempotent (no-op once ``profiles/owner/`` exists). Moves the personal files
    (criteria.md, companies.yaml, master_cv.yaml) and the whole ``data/`` dir — preserving
    atlas.db intact — then seeds anything still missing from the committed templates.
    """
    root = _profile_root(OWNER_ID)
    migrated = not root.exists()
    if migrated:
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "profile").mkdir(parents=True, exist_ok=True)

        # Personal files: MOVE out of the legacy repo-root location if present.
        for name in ("criteria.md", "companies.yaml"):
            src = REPO_ROOT / "config" / name
            if src.exists():
                shutil.move(str(src), str(root / "config" / name))
        mcv = REPO_ROOT / "profile" / "master_cv.yaml"
        if mcv.exists():
            shutil.move(str(mcv), str(root / "profile" / "master_cv.yaml"))

        # Data: MOVE the whole dir (keeps atlas.db + WAL together), then restore the
        # tracked placeholder so git stays clean. Data now lives per profile.
        legacy_data = REPO_ROOT / "data"
        if legacy_data.exists():
            shutil.move(str(legacy_data), str(root / "data"))
            (REPO_ROOT / "data").mkdir(exist_ok=True)
            (REPO_ROOT / "data" / ".gitkeep").touch()
        (root / "data" / "inbox").mkdir(parents=True, exist_ok=True)
        (root / "data" / "outbox").mkdir(parents=True, exist_ok=True)

        # Fill the rest (sources.yaml, ontology.yaml, and any personal file the user
        # never created) from the committed seeds so the profile boots out-of-the-box.
        _seed_missing(root)

    # Label the owner with the real name from their CV (falls back to a neutral default,
    # never the cryptic "Dueño"). reconcile_labels() keeps existing registries in sync too.
    _register(OWNER_ID, cv_name_of(OWNER_ID) or "Mi perfil", owner=True)
    reconcile_labels()
    return {"profile": OWNER_ID, "migrated": migrated, "root": str(root)}
