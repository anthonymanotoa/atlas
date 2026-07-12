"""Generate + persist outreach drafts and assemble the per-job 'ready to send' package.

Idempotent: re-runs skip message kinds already drafted, so a Cowork catch-up run never
creates duplicate Gmail drafts. Nothing is ever sent here — the package is the handoff.
"""

from __future__ import annotations

import json
from pathlib import Path

import engine.paths as paths
from engine.config import default_language, load_master_cv
from engine.cv.tailor import detect_ats
from engine.db.models import DB
from engine.normalize import norm_company
from engine.outreach.templates import Draft, build_package
from engine.referrals.connections import match_referrals


def _candidate(master: dict) -> dict:
    b = master.get("basics", {}) or {}
    return {
        "name": b.get("name", ""),
        "headline": b.get("label", ""),
        "linkedin": b.get("linkedin", ""),
        "one_liner": b.get("summary", ""),
        "pitch": b.get("pitch") or {},  # outreach voice (identity/role/impact/value); optional
    }


def _matched(db: DB, job_id: str) -> list[str]:
    versions = db.cv_versions_for(job_id)
    if versions:
        return json.loads(versions[0].get("matched_keywords") or "[]")
    return []


def _apply_method(job: dict) -> str:
    ats = detect_ats(job.get("apply_url") or job.get("url"))
    if ats in ("greenhouse", "lever", "ashby", "smartrecruiters", "workday", "taleo", "icims"):
        return "ats_form"
    if ats == "linkedin":
        return "linkedin"
    return "email"


def build_outreach(db: DB, job_id: str, language: str | None = None) -> list[Draft]:
    language = language or default_language()  # profile's own language unless caller overrides
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    candidate = _candidate(load_master_cv())
    matched = _matched(db, job_id)
    refs = match_referrals(db, job.get("company", ""))
    contact = refs[0] if refs else None

    drafts = build_package(job, candidate, matched, contact, language=language)
    contact_kinds = {"referral_ask", "recruiter", "hiring_manager"}
    for d in drafts:
        if db.has_message(job_id, d.kind):
            continue
        db.add_message(
            job_id,
            channel=d.channel,
            kind=d.kind,
            body=d.body,
            subject=d.subject,
            variant=d.variant,
            language=d.language,
            contact_id=(contact["id"] if contact and d.kind in contact_kinds else None),
        )
    db.set_state(job_id, "drafted", {"referral": bool(contact)})
    return drafts


def _write_review(job: dict, cv_version: dict) -> None:
    """Best-effort: run the deterministic CV review and write `review.md` next to the CV's
    DOCX — this used to only happen in `atlas tailor`/`atlas prep` (engine/cli.py), so the web
    `/api/jobs/{id}/prep` route and the daily brain (both of which prepare CVs by calling
    write_package directly) never produced a review_report for job detail. Wrapped in
    try/except: a review-write failure must never break packaging."""
    path_docx = cv_version.get("path_docx")
    if not path_docx:
        return
    try:
        from engine.cv.review_report import build_review

        master = load_master_cv()
        coverage = {
            "coverage": cv_version.get("keyword_coverage"),
            "matched": json.loads(cv_version.get("matched_keywords") or "[]"),
            "missing": json.loads(cv_version.get("missing_keywords") or "[]"),
        }
        docx_path = Path(path_docx)
        pdf_path = Path(cv_version["path_pdf"]) if cv_version.get("path_pdf") else None
        review = build_review(docx_path, pdf_path, master, job, coverage)
        (docx_path.parent / "review.md").write_text(review.markdown)
    except Exception:  # noqa: BLE001 — review.md is a nice-to-have, never break packaging
        pass


def write_package(db: DB, job_id: str, language: str = "en") -> Path:
    """Write the human-facing 'exactly what to send' package (Spanish) + mark ready."""
    job = db.get_job(job_id)
    method = _apply_method(job)
    versions = db.cv_versions_for(job_id)
    cv = versions[0] if versions else {}
    if cv:
        _write_review(job, cv)
    msgs = db.messages_for(job_id)
    refs = match_referrals(db, job.get("company", ""))

    db.add_application(
        job_id,
        method=method,
        apply_url=job.get("apply_url") or job.get("url"),
        cv_version_id=cv.get("id"),
        status="ready",
    )

    out = paths.OUTBOX_DIR / job_id
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {job.get('title', '')} — {job.get('company', '')}",
        "",
        "**Estado:** listo para enviar (revisa y envía tú).",
        f"**Fit score:** {job.get('fit_score')}   **Cobertura ATS:** "
        f"{(cv.get('keyword_coverage') or 0):.0%}",
        f"**Cómo aplicar:** {method}",
        f"**Link para postular:** {job.get('apply_url') or job.get('url') or '—'}",
        f"**CV (DOCX):** {cv.get('path_docx') or '—'}",
        f"**CV (PDF):** {cv.get('path_pdf') or '—'}",
        "",
    ]
    if job.get("knockout_flags") and json.loads(job["knockout_flags"]):
        lines.append(
            f"> ⚠️ **Revisa estos filtros del puesto:** "
            f"{', '.join(json.loads(job['knockout_flags']))}"
        )
        lines.append("")
    research = db.company_research_for(norm_company(job.get("company", "")))
    if research and research.get("summary"):
        lines.append("## 🏢 Sobre la empresa")
        lines.append(research["summary"])
        if research.get("signals"):
            lines.append("")
            lines.append("**Señales:**")
            for s in research["signals"]:
                lines.append(f"- {s}")
        if research.get("sources"):
            lines.append("")
            lines.append("**Fuentes:** " + ", ".join(research["sources"]))
        lines.append("")
    if refs:
        c = refs[0]
        lines += [
            "## 🤝 Referido disponible (prioriza esto sobre aplicar en frío)",
            f"- **{c['name']}** — {c.get('title') or ''} @ {c.get('company')}",
            f"  {c.get('linkedin_url') or ''}",
            "",
        ]
    suggested = [c for c in refs if c.get("source") == "brain_research"]
    if suggested:
        lines.append("## 🔍 Contactos sugeridos (candidatos — revisa antes de contactar)")
        for c in suggested:
            lines.append(f"- **{c['name']}** — {c.get('title') or ''} @ {c.get('company')}")
            if c.get("linkedin_url"):
                lines.append(f"  {c['linkedin_url']}")
            if c.get("notes"):
                lines.append(f"  _{c['notes']}_")
        lines.append("")
    insights = db.learnings_for_company(job.get("company", ""))
    if insights:
        lines.append("## 🧠 Lo aprendido de esta empresa")
        for learning in insights:
            lines.append(f"- {learning['observation']} (confianza {learning['confidence']:.0%})")
        lines.append("")
    lines.append("## Mensajes (borradores — edítalos a tu voz antes de enviar)")
    for m in msgs:
        lines += [
            f"\n### {m['kind']} · {m['channel']} · {m['language']}",
            f"**Asunto:** {m.get('subject') or '—'}",
            "",
            m["body"],
            "",
        ]
    path = out / "package.md"
    path.write_text("\n".join(lines))
    db.set_state(job_id, "ready", {"package": str(path), "method": method})
    return path
