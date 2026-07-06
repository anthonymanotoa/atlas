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
    out = _dump_path(job_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(result.cv, allow_unicode=True, sort_keys=False, width=1000))
    return out


# ── mechanical apply of the reviewer's edits/flags (Task 7) ────────────────────
# The LLM proposes strings; NOTHING here calls an LLM. apply_edit is a deterministic
# old_string→new_string replace + re-render; resolve_flag mutates the parsed YAML and
# re-renders. Both fail gracefully (ValueError, no partial write) rather than 500.
EDIT_FILES = ("cv", "cover_letter", "recruiter", "hiring_manager")


def _dump_path(job_id: str) -> Path:
    return paths.OUTBOX_DIR / job_id / "cv_for_review.yaml"


def _rerender(db: DB, job_id: str, cv: dict) -> int:
    """Re-render DOCX/PDF desde el dict editado; devuelve el cv_version_id nuevo."""
    from engine.config import default_language
    from engine.cv.build import build_for_job

    latest = db.cv_versions_for(job_id)
    language = (latest[0].get("language") if latest else None) or default_language()
    return build_for_job(db, job_id, language=language, cv_override=cv).cv_version_id


def apply_edit(db: DB, review_id: int, index: int) -> dict:
    """Apply ONE structured edit mechanically. For a `cv` edit, `old_string` must appear
    EXACTLY once in cv_for_review.yaml; the replace runs, the YAML is re-parsed (a replace
    that breaks the document is refused) and the CV is re-rendered into a new cv_version.
    For a message edit, the replace lands on that kind's latest message body.

    A non-matching / non-unique old_string raises ValueError WITHOUT applying anything —
    a careful, refused edit, never a 500."""
    review = db.get_cv_review(review_id)
    if not review:
        raise ValueError(f"cv_review {review_id} not found")
    edits = review["edits"]
    if not 0 <= index < len(edits):
        raise ValueError(f"edit index {index} out of range")
    edit = edits[index]
    if edit.get("applied"):
        return {"ok": True, "applied_ref": edit.get("applied_ref"), "already": True}
    target = edit.get("file")
    if target == "cv":
        path = _dump_path(review["job_id"])
        if not path.exists():
            dump_tailored_cv(db, review["job_id"])
        text = path.read_text()
        if text.count(edit["old_string"]) != 1:
            raise ValueError("old_string must appear exactly once in cv_for_review.yaml")
        new_text = text.replace(edit["old_string"], edit["new_string"])
        cv = yaml.safe_load(new_text)  # el replace no puede romper el YAML
        if not isinstance(cv, dict):
            raise ValueError("edit would corrupt the CV YAML — rejected")
        path.write_text(new_text)
        applied_ref = f"cv_version:{_rerender(db, review['job_id'], cv)}"
    elif target in EDIT_FILES:
        msgs = [m for m in db.messages_for(review["job_id"]) if m["kind"] == target]
        if not msgs:
            raise ValueError(f"no {target} message drafted for this job")
        msg = msgs[-1]
        body = msg.get("body") or ""
        if edit["old_string"] not in body:
            raise ValueError("old_string not found in the message body")
        db.conn.execute(
            "UPDATE messages SET body=? WHERE id=?",
            (body.replace(edit["old_string"], edit["new_string"], 1), msg["id"]),
        )
        db.conn.commit()
        applied_ref = f"message:{msg['id']}"
    else:
        raise ValueError(f"unknown edit file {target!r}; allowed: {EDIT_FILES}")
    edit["applied"] = True
    edit["applied_ref"] = applied_ref
    db.set_cv_review_edits(review_id, edits)
    return {"ok": True, "applied_ref": applied_ref}


def resolve_flag(db: DB, review_id: int, index: int, action: str) -> dict:
    """Resolve a backtrack-test flag. `keep` only annotates. `soften` replaces the flagged
    bullet with its `softened` alternative and re-renders; `drop` removes the bullet and
    re-renders. Both structural actions operate on the PARSED YAML (not a string replace)
    and fail gracefully if the bullet is no longer present."""
    if action not in ("keep", "soften", "drop"):
        raise ValueError("action must be keep|soften|drop")
    review = db.get_cv_review(review_id)
    if not review:
        raise ValueError(f"cv_review {review_id} not found")
    flags = review["flags"]
    if not 0 <= index < len(flags):
        raise ValueError(f"flag index {index} out of range")
    flag = flags[index]
    if action in ("soften", "drop"):
        if action == "soften" and not flag.get("softened"):
            raise ValueError("flag has no softened alternative")
        path = _dump_path(review["job_id"])
        if not path.exists():
            dump_tailored_cv(db, review["job_id"])
        cv = yaml.safe_load(path.read_text())
        found = False
        for exp in cv.get("experience", []):
            hl = exp.get("highlights") or []
            if flag["bullet"] in hl:
                i = hl.index(flag["bullet"])
                if action == "drop":
                    hl.pop(i)
                else:
                    hl[i] = flag["softened"]
                found = True
                break
        if not found:
            raise ValueError("bullet not found in the tailored CV")
        path.write_text(yaml.safe_dump(cv, allow_unicode=True, sort_keys=False, width=1000))
        _rerender(db, review["job_id"], cv)
    flag["resolution"] = action
    db.set_cv_review_flags(review_id, flags)
    return {"ok": True, "resolution": action}
