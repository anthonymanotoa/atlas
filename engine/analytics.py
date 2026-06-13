"""Analytics + the 'what to do next' layer that powers the dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from engine import heartbeat
from engine.db.models import DB
from engine.referrals.connections import match_referrals

FUNNEL = [
    ("discovered", "discovered_at"), ("scored", "scored_at"),
    ("shortlisted", "shortlisted_at"), ("tailored", "tailored_at"),
    ("ready", "ready_at"), ("applied", "applied_at"),
    ("responded", "responded_at"), ("interview", "interview_at"), ("offer", "offer_at"),
]
STALE_APPLIED_DAYS = 7


def _count_notnull(db: DB, col: str) -> int:
    return db.conn.execute(f"SELECT COUNT(*) n FROM jobs WHERE {col} IS NOT NULL").fetchone()["n"]


def _days_since(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        return round((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400, 1)
    except ValueError:
        return None


def overview(db: DB) -> dict[str, Any]:
    funnel = [{"stage": name, "count": _count_notnull(db, col)} for name, col in FUNNEL]
    total = db.conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
    applied = _count_notnull(db, "applied_at")
    responded = _count_notnull(db, "responded_at")
    interview = _count_notnull(db, "interview_at")
    response_rate = round(responded / applied, 3) if applied else None
    interview_rate = round(interview / applied, 3) if applied else None
    return {
        "total_jobs": total,
        "counts": db.counts_by_state(),
        "funnel": funnel,
        "response_rate": response_rate,        # benchmark bands (frontend): 0.02–0.05 typical, 0.10–0.18 strong
        "interview_rate": interview_rate,
        "applied": applied,
        "ready": db.counts_by_state().get("ready", 0),
        "last_run": db.meta_get("last_run"),
        "last_success": db.meta_get("last_success_ts"),
        "downtime_hours": heartbeat.downtime_hours(db),
        "source_health": db.latest_source_health(),
    }


def needs_action(db: DB) -> list[dict]:
    """The action-first rail: concrete next steps, highest-leverage first."""
    actions: list[dict] = []

    # 1. Ready to send (referrals first — highest conversion).
    ready = db.list_jobs(state="ready")
    ready_ref, ready_cold = [], []
    for j in ready:
        refs = match_referrals(db, j.get("company", ""))
        (ready_ref if refs else ready_cold).append((j, refs))
    for j, refs in ready_ref:
        actions.append({"type": "ask_referral", "priority": 1, "job_id": j["id"],
                        "title": j["title"], "company": j["company"],
                        "label": f"Pide referido a {refs[0]['name']}",
                        "link": j.get("apply_url") or j.get("url"),
                        "contact": refs[0]["name"]})
    for j, _ in ready_cold:
        actions.append({"type": "send_application", "priority": 2, "job_id": j["id"],
                        "title": j["title"], "company": j["company"],
                        "label": "Enviar postulación", "link": j.get("apply_url") or j.get("url")})

    # 2. Replies to act on.
    for j in db.list_jobs(state="responded"):
        actions.append({"type": "reply", "priority": 0, "job_id": j["id"], "title": j["title"],
                        "company": j["company"], "label": "Respondieron — avanza el proceso",
                        "link": j.get("apply_url") or j.get("url")})

    # 3. Stale applications → follow up.
    for j in db.list_jobs(state="applied"):
        days = _days_since(j.get("applied_at"))
        if days and days >= STALE_APPLIED_DAYS:
            actions.append({"type": "follow_up", "priority": 3, "job_id": j["id"],
                            "title": j["title"], "company": j["company"],
                            "label": f"Sin respuesta hace {days:.0f}d — haz follow-up",
                            "link": j.get("apply_url") or j.get("url")})

    actions.sort(key=lambda a: a["priority"])
    return actions


def job_detail(db: DB, job_id: str) -> Optional[dict]:
    job = db.get_job(job_id)
    if not job:
        return None
    job["fit_reasons"] = json.loads(job.get("fit_reasons") or "[]")
    job["knockout_flags"] = json.loads(job.get("knockout_flags") or "[]")
    job["sources"] = json.loads(job.get("sources_json") or "[]")
    job["age_days"] = _days_since(job.get("discovered_at"))
    job["applied_days"] = _days_since(job.get("applied_at"))
    return {
        "job": job,
        "cv_versions": db.cv_versions_for(job_id),
        "messages": db.messages_for(job_id),
        "referrals": match_referrals(db, job.get("company", "")),
        "timeline": _timeline(job),
    }


def _timeline(job: dict) -> list[dict]:
    out = []
    for name, col in FUNNEL:
        ts = job.get(col)
        if ts:
            out.append({"stage": name, "at": ts})
    return out
