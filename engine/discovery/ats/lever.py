"""Lever public Postings API (keyless).

  GET https://api.lever.co/v0/postings/{site}?mode=json        (EU: api.eu.lever.co)
"""
from __future__ import annotations

import httpx

from engine.config import CompanyTarget
from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import first, to_float


def _base(eu: bool) -> str:
    host = "api.eu.lever.co" if eu else "api.lever.co"
    return f"https://{host}/v0/postings"


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    url = f"{_base(target.eu)}/{target.token}"
    data = get_json(client, url, params={"mode": "json", "limit": 100})
    jobs: list[Job] = []
    for p in data if isinstance(data, list) else []:
        cats = p.get("categories") or {}
        sal = p.get("salaryRange") or {}
        wt = (p.get("workplaceType") or "").lower()  # remote | on-site | hybrid
        location = first(cats.get("location"), cats.get("allLocations"))
        if isinstance(location, list):
            location = ", ".join(location)
        jobs.append(Job(
            source="lever",
            source_job_id=p.get("id"),
            title=(p.get("text") or "").strip(),
            company=target.company,
            location=location,
            workplace_type=wt or "unknown",
            is_remote=True if wt == "remote" else (False if wt in ("on-site", "hybrid") else None),
            url=p.get("hostedUrl"),
            apply_url=first(p.get("applyUrl"), p.get("hostedUrl")),
            description=p.get("descriptionPlain") or "",
            employment_type=cats.get("commitment"),
            salary_min=to_float(sal.get("min")),
            salary_max=to_float(sal.get("max")),
            salary_currency=sal.get("currency"),
            salary_interval=(sal.get("interval") or "").replace("per-", "") or None,
            date_posted=None,
            raw={"team": cats.get("team"), "country": p.get("country")},
        ))
    return jobs
