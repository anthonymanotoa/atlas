"""Greenhouse public Job Board API (keyless).

  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  → one call returns every job with full (HTML-escaped) description.
"""
from __future__ import annotations

import httpx

from engine.config import CompanyTarget
from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import html_to_text

BASE = "https://boards-api.greenhouse.io/v1/boards"


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    url = f"{BASE}/{target.token}/jobs"
    data = get_json(client, url, params={"content": "true"})
    jobs: list[Job] = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name")
        jobs.append(Job(
            source="greenhouse",
            source_job_id=str(j.get("id")),
            title=j.get("title", "").strip(),
            company=target.company,
            location=loc,
            url=j.get("absolute_url"),
            apply_url=j.get("absolute_url"),
            description=html_to_text(j.get("content")),
            date_posted=(j.get("updated_at") or "")[:10] or None,
            raw={"departments": [d.get("name") for d in j.get("departments", [])]},
        ))
    return jobs
