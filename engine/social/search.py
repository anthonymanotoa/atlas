"""Supervised social search (P2-C).

The system only QUEUES intent + prepares search queries; a human runs the actual
LinkedIn/X lookup in a Claude-in-Chrome session (their own, slow, human-confirmed) and
saves what they verify. Nothing here browses, scrapes, or contacts anyone — that keeps
us account/IP-safe and within the never-auto-send invariant.

See brain/SKILL_social_search.md (the supervised flow) and docs/RATE_LIMITING.md
(the Chrome-session guardrails).
"""

from __future__ import annotations

import json

from engine.db.models import DB
from engine.normalize import now_iso

_KEY = "pending_searches"


def _load(db: DB) -> list[dict]:
    try:
        return json.loads(db.meta_get(_KEY) or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def queue_search(db: DB, job_id: str, company: str, title: str) -> list[dict]:
    """Mark a job as wanting a (human-run) social search. Idempotent per job_id."""
    items = [x for x in _load(db) if x.get("job_id") != job_id]
    items.append({"job_id": job_id, "company": company, "title": title, "queued_at": now_iso()})
    db.meta_set(_KEY, json.dumps(items))
    return items


def pending_searches(db: DB) -> list[dict]:
    return _load(db)


def clear_search(db: DB, job_id: str) -> list[dict]:
    items = [x for x in _load(db) if x.get("job_id") != job_id]
    db.meta_set(_KEY, json.dumps(items))
    return items


def search_queries(company: str, title: str) -> dict[str, str]:
    """Ready-to-paste queries for the supervised Chrome session (no requests made here)."""
    company = (company or "").strip()
    title = (title or "").strip()
    return {
        "linkedin_recruiters": f'site:linkedin.com/in {company} (recruiter OR "talent acquisition")',
        "linkedin_posts": f"{company} {title} (hiring OR contratando)",
        "x": f"{company} {title} (hiring OR contratando OR vacante)",
    }
