"""Ashby public Job Posting API (keyless).

GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true
Note: {name} is CASE-SENSITIVE (match the jobs.ashbyhq.com/<name> URL exactly).
"""

from __future__ import annotations

import httpx

from engine.config import CompanyTarget
from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import first

BASE = "https://api.ashbyhq.com/posting-api/job-board"


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    url = f"{BASE}/{target.token}"
    data = get_json(client, url, params={"includeCompensation": "true"})
    jobs: list[Job] = []
    for j in data.get("jobs", []):
        comp = j.get("compensation") or {}
        is_remote = j.get("isRemote")
        jobs.append(
            Job(
                source="ashby",
                source_job_id=j.get("id"),
                title=(j.get("title") or "").strip(),
                company=target.company,
                location=first(j.get("location"), j.get("secondaryLocations")),
                is_remote=bool(is_remote) if is_remote is not None else None,
                workplace_type="remote" if is_remote else (j.get("workplaceType") or "unknown"),
                url=j.get("jobUrl"),
                apply_url=first(j.get("applyUrl"), j.get("jobUrl")),
                description=j.get("descriptionPlain") or "",
                employment_type=j.get("employmentType"),
                salary_currency=None,
                date_posted=(j.get("publishedAt") or "")[:10] or None,
                raw={
                    "department": j.get("department"),
                    "team": j.get("team"),
                    "compensation": comp.get("compensationTierSummary"),
                },
            )
        )
    return jobs
