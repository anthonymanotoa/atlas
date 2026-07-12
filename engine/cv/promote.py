"""Promote profile/master_cv.draft.yaml → profile/master_cv.yaml (validated, with backup)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from engine.cv.placeholder import find_placeholders


class PromoteError(RuntimeError):
    pass


REQUIRED_BASICS = ("name", "email")


def promote_draft(profile_root: Path) -> Path:
    prof = profile_root / "profile"
    draft_path = prof / "master_cv.draft.yaml"
    master_path = prof / "master_cv.yaml"
    if not draft_path.exists():
        raise PromoteError(f"No existe el draft: {draft_path}")
    draft = yaml.safe_load(draft_path.read_text()) or {}
    if "_source_text" in draft:
        raise PromoteError(
            "El draft aún contiene _source_text (texto crudo del PDF sin mapear). "
            "Mapea los campos y borra _source_text antes de promover."
        )
    basics = draft.get("basics") or {}
    missing = [k for k in REQUIRED_BASICS if not (basics.get(k) or "").strip()]
    if missing:
        raise PromoteError(f"Faltan campos obligatorios en basics: {', '.join(missing)}")
    findings = find_placeholders(draft)
    if findings:
        raise PromoteError("El draft sigue con identidad de plantilla: " + "; ".join(findings))
    if not draft.get("experience"):
        raise PromoteError("El draft no tiene experiencia (experience) — mapéala primero.")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if master_path.exists():
        backup_path = prof / f"master_cv.backup-{ts}.yaml"
        suffix = 2
        while backup_path.exists():
            backup_path = prof / f"master_cv.backup-{ts}-{suffix}.yaml"
            suffix += 1
        master_path.rename(backup_path)
    master_path.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True))
    return master_path
