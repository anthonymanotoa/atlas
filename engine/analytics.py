"""Analytics + the 'what to do next' layer that powers the dashboard."""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from typing import Any

from engine import heartbeat
from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import norm_company
from engine.referrals.connections import match_referrals

FUNNEL = [
    ("discovered", "discovered_at"),
    ("scored", "scored_at"),
    ("shortlisted", "shortlisted_at"),
    ("tailored", "tailored_at"),
    ("ready", "ready_at"),
    ("applied", "applied_at"),
    ("responded", "responded_at"),
    ("interview", "interview_at"),
    ("offer", "offer_at"),
]
STALE_APPLIED_DAYS = 7


def _days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        try:  # bare 'YYYY-MM-DD' (e.g. date_posted) — fromisoformat handles it on 3.11+, but be safe
            dt = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:  # naive (bare date) → assume UTC so the subtraction is aware-safe
        dt = dt.replace(tzinfo=UTC)
    return round((datetime.now(UTC) - dt).total_seconds() / 86400, 1)


def annotate(job: dict) -> dict:
    """Add UI-facing computed fields to a raw jobs row (mutates + returns it).

    `posted_days` is from the posting's own date_posted (how long the vacancy has been
    open); `age_days` is since we discovered it. `salary_visible` drives the
    'solo con salario' filter + the salary chip.
    """
    job["age_days"] = _days_since(job.get("discovered_at"))
    posted = _days_since(job.get("date_posted"))
    job["posted_days"] = posted if posted is not None else job["age_days"]
    job["salary_visible"] = bool(job.get("salary_min") or job.get("salary_max"))
    return job


def overview(db: DB) -> dict[str, Any]:
    # One aggregate pass for the whole funnel: COUNT(col) already skips NULLs. The FUNNEL
    # column names are module constants (not user input), so interpolation here is safe.
    cols = [col for _, col in FUNNEL]
    select = ", ".join([f"COUNT({c}) AS {c}" for c in cols] + ["COUNT(*) AS total"])
    row = db.conn.execute(f"SELECT {select} FROM jobs").fetchone()
    funnel = [{"stage": name, "count": row[col]} for name, col in FUNNEL]
    total = row["total"]
    applied = row["applied_at"]
    responded = row["responded_at"]
    interview = row["interview_at"]
    response_rate = round(responded / applied, 3) if applied else None
    interview_rate = round(interview / applied, 3) if applied else None
    counts = db.counts_by_state()  # one GROUP BY scan, reused for both `counts` and `ready`
    return {
        "total_jobs": total,
        "counts": counts,
        "funnel": funnel,
        "response_rate": response_rate,  # benchmark bands (frontend): 0.02–0.05 typical, 0.10–0.18 strong
        "interview_rate": interview_rate,
        "applied": applied,
        "ready": counts.get("ready", 0),
        "last_run": db.meta_get("last_run"),
        "last_success": db.meta_get("last_success_ts"),
        "downtime_hours": heartbeat.downtime_hours(db),
        "source_health": db.latest_source_health(),
    }


# ── F3 §6.2: analytics puro sobre SQLite (funnel real, score floor, conversiones) ──
# El funnel se calcula de las columnas timestamp por etapa de `jobs` (constante FUNNEL),
# que son la fuente canónica de transiciones — NO de la tabla `events`, cuyo `type` sólo
# distingue discovered/stage_change/... con el destino enterrado en `detail` JSON. Los
# positivos se complementan con `application_outcomes.final_state` (usa 'interviewed').
POSITIVE_OUTCOME_STATES = ("responded", "interviewed", "offer")
_ATS_SOURCES = frozenset({"greenhouse", "lever", "ashby", "smartrecruiters", "workday"})
_POSITIVE_JOBS_WHERE = (
    "(responded_at IS NOT NULL OR interview_at IS NOT NULL OR offer_at IS NOT NULL "
    "OR id IN (SELECT job_id FROM application_outcomes WHERE final_state IN "
    "('responded','interviewed','offer')))"
)


def funnel(db: DB) -> list[dict]:
    """Funnel por transiciones reales (columnas timestamp por etapa de jobs) + tasa vs etapa previa.

    `rate` es la conversión respecto a la etapa inmediatamente anterior (None en discovered).
    COUNT(col) ya ignora NULLs; los nombres de columna vienen de FUNNEL (constantes del
    módulo, no input del usuario) → la interpolación es segura.
    """
    cols = [col for _, col in FUNNEL]
    select = ", ".join(f"COUNT({c}) AS {c}" for c in cols)
    row = db.conn.execute(f"SELECT {select} FROM jobs").fetchone()
    out: list[dict] = []
    prev: int | None = None
    for name, col in FUNNEL:
        count = row[col]
        rate = round(count / prev, 3) if prev else None
        out.append({"stage": name, "count": count, "rate": rate})
        prev = count
    return out


def score_floor(db: DB) -> float | None:
    """Score mínimo con outcome positivo — el 'piso' empírico: 'ningún positivo bajo X' (§6.2).

    Positivo = el job alcanzó responded/interview/offer (timestamp) o tiene un
    application_outcome confirmado en POSITIVE_OUTCOME_STATES. None si no hay ninguno.
    """
    row = db.conn.execute(
        f"SELECT MIN(fit_score) AS floor, COUNT(*) AS n FROM jobs "
        f"WHERE fit_score IS NOT NULL AND {_POSITIVE_JOBS_WHERE}"
    ).fetchone()
    return float(row["floor"]) if row and row["n"] else None


def conversion_by(db: DB, dim: str, criteria: Criteria | None = None) -> list[dict]:
    """Conversión de jobs APLICADOS agrupados por dimensión (§6.2).

    dim ∈ {source, ats, remote_policy, role_term}. Cada fila:
    {key, applied, responded, interviews, offers, response_rate}, ordenada por applied desc.
    Sólo se consideran jobs con applied_at (llegaron a postulación).
    """
    if dim not in ("source", "ats", "remote_policy", "role_term"):
        raise ValueError(f"unknown dim: {dim}")
    jobs = [j for j in db.list_jobs() if j.get("applied_at")]

    def key_of(j: dict) -> str:
        if dim == "source":
            return j.get("source") or "unknown"
        if dim == "ats":
            s = j.get("source") or "unknown"
            return s if s in _ATS_SOURCES else "non-ats"
        if dim == "remote_policy":
            return (j.get("workplace_type") or "unknown").lower()
        title = (j.get("title") or "").lower()
        for t in criteria.all_role_terms if criteria else []:
            if t in title:
                return t
        return "otro"

    groups: dict[str, dict] = {}
    for j in jobs:
        k = key_of(j)
        g = groups.setdefault(
            k, {"key": k, "applied": 0, "responded": 0, "interviews": 0, "offers": 0}
        )
        positive = bool(j.get("responded_at") or j.get("interview_at") or j.get("offer_at"))
        g["applied"] += 1
        g["responded"] += 1 if positive else 0
        g["interviews"] += 1 if (j.get("interview_at") or j.get("offer_at")) else 0
        g["offers"] += 1 if j.get("offer_at") else 0
    for g in groups.values():
        g["response_rate"] = round(g["responded"] / g["applied"], 3) if g["applied"] else None
    return sorted(groups.values(), key=lambda g: -g["applied"])


def response_times(db: DB) -> dict:
    """Días applied→responded (timestamps de jobs) + response_days confirmados (outcomes).

    Devuelve {n, avg_days, median_days, p90_days}; todos None cuando no hay datos.
    """
    days: list[float] = []
    for j in db.list_jobs():
        a, r = j.get("applied_at"), j.get("responded_at")
        if not (a and r):
            continue
        try:
            delta = (datetime.fromisoformat(r) - datetime.fromisoformat(a)).total_seconds() / 86400
        except (ValueError, TypeError):
            continue
        if delta >= 0:
            days.append(round(delta, 1))
    rows = db.conn.execute(
        "SELECT response_days FROM application_outcomes WHERE response_days IS NOT NULL"
    ).fetchall()
    days.extend(float(r["response_days"]) for r in rows)
    if not days:
        return {"n": 0, "avg_days": None, "median_days": None, "p90_days": None}
    days.sort()
    return {
        "n": len(days),
        "avg_days": round(statistics.fmean(days), 1),
        "median_days": round(statistics.median(days), 1),
        "p90_days": round(days[int(0.9 * (len(days) - 1))], 1),
    }


def recommendations(db: DB, criteria: Criteria) -> list[dict]:
    """Recomendaciones deterministas accionables (§6.2). Umbrales fijos y explicables.

    Rec = {"id", "text", "action_type": "set_criteria"|"block_company"|"none", "payload"}.
    Conservadora por diseño: nada dispara con muestra pequeña (nunca bloquea por 1 rechazo,
    nunca sube el threshold con <3 positivos). Sin red, sin LLM — sólo conteos/umbrales.
    """
    recs: list[dict] = []
    # 1. Score floor empírico → subir shortlist_threshold.
    floor = score_floor(db)
    positives = db.conn.execute(
        f"SELECT COUNT(*) AS n FROM jobs WHERE fit_score IS NOT NULL AND {_POSITIVE_JOBS_WHERE}"
    ).fetchone()["n"]
    if floor is not None and positives >= 3 and floor > criteria.shortlist_threshold + 2:
        value = float(int(floor))
        recs.append(
            {
                "id": f"threshold-{int(value)}",
                "text": (
                    f"Ningún resultado positivo bajo score {floor:.0f} ({positives} positivos): "
                    f"sube shortlist_threshold de {criteria.shortlist_threshold:.0f} a {value:.0f}."
                ),
                "action_type": "set_criteria",
                "payload": {"field": "shortlist_threshold", "value": value},
            }
        )
    # 2. Empresas que nunca responden → blocklist (≥3 aplicaciones, 0 respuestas, no bloqueada aún).
    blocked = {norm_company(c) for c in criteria.company_blocklist}
    rows = db.conn.execute(
        """SELECT company, COUNT(*) AS n FROM jobs
           WHERE applied_at IS NOT NULL AND responded_at IS NULL
             AND interview_at IS NULL AND offer_at IS NULL
           GROUP BY company HAVING n >= 3"""
    ).fetchall()
    for r in rows:
        if norm_company(r["company"]) in blocked:
            continue
        recs.append(
            {
                "id": f"block-{norm_company(r['company'])}",
                "text": f"{r['n']} aplicaciones a {r['company']} sin ninguna respuesta: bloquéala.",
                "action_type": "block_company",
                "payload": {"company": r["company"]},
            }
        )
    # 3. Role-terms que no convierten (informativa — quitar un término es decisión del usuario).
    for row in conversion_by(db, "role_term", criteria):
        if row["key"] != "otro" and row["applied"] >= 5 and row["responded"] == 0:
            recs.append(
                {
                    "id": f"term-{row['key'].replace(' ', '-')}",
                    "text": (
                        f"El término '{row['key']}' lleva {row['applied']} aplicaciones sin "
                        f"respuesta — considera quitarlo de roles en Ajustes."
                    ),
                    "action_type": "none",
                    "payload": {"term": row["key"]},
                }
            )
    return recs


def analytics_payload(db: DB, criteria: Criteria) -> dict:
    """Composición completa para GET /api/analytics (§6.2)."""
    return {
        "funnel": funnel(db),
        "score_floor": score_floor(db),
        "by_source": conversion_by(db, "source"),
        "by_ats": conversion_by(db, "ats"),
        "by_remote_policy": conversion_by(db, "remote_policy"),
        "by_role_term": conversion_by(db, "role_term", criteria),
        "response_times": response_times(db),
        "recommendations": recommendations(db, criteria),
    }


def needs_action(db: DB) -> list[dict]:
    """The action-first rail: concrete next steps, highest-leverage first."""
    actions: list[dict] = []

    # 1. Ready to send (referrals first — highest conversion).
    contacts = db.all_contacts()  # load once; match_referrals would otherwise full-scan per job
    ready = db.list_jobs(state="ready")
    ready_ref, ready_cold = [], []
    for j in ready:
        refs = match_referrals(db, j.get("company", ""), contacts=contacts)
        (ready_ref if refs else ready_cold).append((j, refs))
    for j, refs in ready_ref:
        actions.append(
            {
                "type": "ask_referral",
                "priority": 1,
                "job_id": j["id"],
                "title": j["title"],
                "company": j["company"],
                "label": f"Pide referido a {refs[0]['name']}",
                "link": j.get("apply_url") or j.get("url"),
                "contact": refs[0]["name"],
            }
        )
    for j, _ in ready_cold:
        actions.append(
            {
                "type": "send_application",
                "priority": 2,
                "job_id": j["id"],
                "title": j["title"],
                "company": j["company"],
                "label": "Enviar postulación",
                "link": j.get("apply_url") or j.get("url"),
            }
        )

    # 2. Replies to act on.
    for j in db.list_jobs(state="responded"):
        actions.append(
            {
                "type": "reply",
                "priority": 0,
                "job_id": j["id"],
                "title": j["title"],
                "company": j["company"],
                "label": "Respondieron — avanza el proceso",
                "link": j.get("apply_url") or j.get("url"),
            }
        )

    # 3. Stale applications → follow up.
    for j in db.list_jobs(state="applied"):
        days = _days_since(j.get("applied_at"))
        if days and days >= STALE_APPLIED_DAYS:
            actions.append(
                {
                    "type": "follow_up",
                    "priority": 3,
                    "job_id": j["id"],
                    "title": j["title"],
                    "company": j["company"],
                    "label": f"Sin respuesta hace {days:.0f}d — haz follow-up",
                    "link": j.get("apply_url") or j.get("url"),
                }
            )

    actions.sort(key=lambda a: a["priority"])
    return actions


def job_detail(db: DB, job_id: str) -> dict | None:
    job = db.get_job(job_id)
    if not job:
        return None
    job["fit_reasons"] = json.loads(job.get("fit_reasons") or "[]")
    job["knockout_flags"] = json.loads(job.get("knockout_flags") or "[]")
    job["sources"] = json.loads(job.get("sources_json") or "[]")
    job["missing_keywords"] = json.loads(job.get("match_missing") or "[]")  # CV↔JD gaps
    job["jd_skills"] = _jd_skills(job)  # skills the posting itself asks for (detail view)
    annotate(job)  # age_days, posted_days, salary_visible
    job["applied_days"] = _days_since(job.get("applied_at"))
    return {
        "job": job,
        "cv_versions": db.cv_versions_for(job_id),
        "messages": db.messages_for(job_id),
        "referrals": match_referrals(db, job.get("company", "")),
        "social_mentions": db.social_mentions_for(job_id),
        "learnings": db.learnings_for_company(job.get("company", "")),
        "timeline": _timeline(job),
    }


def _jd_skills(job: dict, *, limit: int = 16) -> list[str]:
    """Skills the posting itself asks for, extracted from title+description via the ontology
    (importance-ranked, deduped). Empty when the source gave us no description to read."""
    desc = job.get("description") or ""
    if not desc:
        return []
    from engine.config import load_ontology
    from engine.cv.keywords import extract_jd_keywords

    hits = extract_jd_keywords(job.get("title") or "", desc, load_ontology())
    out: list[str] = []
    for h in hits:
        if h.canonical not in out:
            out.append(h.canonical)
        if len(out) >= limit:
            break
    return out


def _timeline(job: dict) -> list[dict]:
    out = []
    for name, col in FUNNEL:
        ts = job.get(col)
        if ts:
            out.append({"stage": name, "at": ts})
    return out
