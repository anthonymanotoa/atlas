"""CV/carta review (F4 §7.2) — dump del CV tailoreado para el reviewer del brain,
y aplicación mecánica de sus edits/flags (Task 7). El LLM nunca escribe archivos:
propone strings; aquí se validan y aplican deterministamente."""

from __future__ import annotations

from pathlib import Path

import yaml

import engine.paths as paths
from engine.config import load_master_cv, load_ontology
from engine.cv import tailor as tailor_mod
from engine.db.models import DB


def dump_tailored_cv(db: DB, job_id: str, language: str | None = None) -> Path:
    """Escribe el CV tailoreado (dict → YAML) a data/outbox/<job_id>/cv_for_review.yaml.

    width=1000 mantiene cada bullet en UNA línea: los old_string del reviewer se copian
    verbatim de este texto y el apply hace replace exacto (Task 7).
    `language` no cambia el dump (el tailor es agnóstico); se acepta para simetría de API.
    """
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    result = tailor_mod.tailor(load_master_cv(), job, load_ontology())
    out = paths.OUTBOX_DIR / job_id / "cv_for_review.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(result.cv, allow_unicode=True, sort_keys=False, width=1000))
    return out
