"""Profile expansion — apply the brain's ADDITIVE, source-annotated enrichment to the master
CV, one confirmed item at a time. Idempotent: an item already present is skipped, never
duplicated. Writes ONLY to paths.MASTER_CV_PATH (gitignored) — never anything committed.

$0 invariant: no LLM here. The GitHub/portfolio/syllabi SCAN is the brain executing
brain/prompts/profile_expand.md; this module is pure deterministic YAML mutation. It never
overwrites or deletes existing CV content — it only appends absent items the human confirmed.
"""

from __future__ import annotations

import yaml

import engine.paths as paths
from engine.db.models import DB

EXPAND_TARGETS = ("skills", "experience_highlight", "project", "certification")


def _load_cv() -> dict:
    path = paths.MASTER_CV_PATH
    if not path.exists():
        raise ValueError(f"master CV not found at {path}; run onboarding first")
    return yaml.safe_load(path.read_text()) or {}


def _dump_cv(cv: dict) -> None:
    paths.MASTER_CV_PATH.write_text(
        yaml.safe_dump(cv, allow_unicode=True, sort_keys=False, width=1000)
    )


def _apply_one(cv: dict, item: dict) -> bool:
    """Add `item` to `cv` if absent. Returns True if it was added, False if already present."""
    target, value = item.get("target"), item.get("value")
    if target == "skills":
        cv.setdefault("skills", [])
        if value in cv["skills"]:
            return False
        cv["skills"].append(value)
        return True
    if target == "experience_highlight":
        exps = cv.get("experience") or []
        if not exps:
            raise ValueError("no experience entry to attach a highlight to")
        # value: {company?, highlight}; attach to the named role or the most recent one.
        target_exp = next(
            (e for e in exps if e.get("company") == (value or {}).get("company")), exps[0]
        )
        hl = target_exp.setdefault("highlights", [])
        text = value["highlight"] if isinstance(value, dict) else value
        if text in hl:
            return False
        hl.append(text)
        return True
    if target == "project":
        cv.setdefault("projects", [])
        name = value.get("name") if isinstance(value, dict) else value
        if any((p.get("name") if isinstance(p, dict) else p) == name for p in cv["projects"]):
            return False
        cv["projects"].append(value)
        return True
    if target == "certification":
        cv.setdefault("certifications", [])
        name = value.get("name") if isinstance(value, dict) else value
        if any(c.get("name") == name for c in cv["certifications"]):
            return False
        cv["certifications"].append(value)
        return True
    raise ValueError(f"unknown target {target!r}; allowed: {EXPAND_TARGETS}")


def apply_items(exp_id: int, indices: list[int]) -> dict:
    """Apply only the confirmed items (by index) to the master CV. Additive + idempotent.

    Only the indices passed are considered; every other item is left untouched and still
    offer-able. An already-applied index is a no-op. Writes the file only when at least one
    new item landed, so a redundant apply never rewrites the YAML.
    """
    with DB() as db:
        exp = db.get_profile_expansion(exp_id)
        if not exp:
            raise ValueError(f"profile_expansion {exp_id} not found")
        items = exp["items"]
        cv = _load_cv()
        applied = skipped = 0
        for i in indices:
            if not 0 <= i < len(items):
                raise ValueError(f"item index {i} out of range")
            item = items[i]
            if item.get("applied"):
                skipped += 1
                continue
            if _apply_one(cv, item):
                item["applied"] = True
                applied += 1
            else:
                item["applied"] = True  # present already → treat as done, don't re-offer
                skipped += 1
        if applied:
            _dump_cv(cv)
        db.set_profile_expansion(exp_id, items)
    return {"ok": True, "applied": applied, "skipped_existing": skipped}
