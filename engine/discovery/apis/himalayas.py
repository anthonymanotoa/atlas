"""Himalayas — free, no-auth, remote-first jobs API. Every listing is remote.

GET https://himalayas.app/jobs/api?limit=20&offset=0   (20/page; page via offset)
"""

from __future__ import annotations

import httpx

from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import first, html_to_text, to_float

URL = "https://himalayas.app/jobs/api"
PAGE = 20


def fetch(cfg: dict, search_terms: list[str], client: httpx.Client) -> list[Job]:
    limit = int(cfg.get("limit", 50))
    out: list[Job] = []
    offset = 0
    while len(out) < limit:
        data = get_json(client, URL, params={"limit": PAGE, "offset": offset})
        rows = first(data.get("jobs"), data.get("data"), data.get("results"), []) or []
        if not rows:
            break
        for j in rows:
            locs = j.get("locationRestrictions") or j.get("locations") or []
            company = first(j.get("companyName"), (j.get("company") or {}).get("name"), "")
            out.append(
                Job(
                    source="himalayas",
                    source_job_id=str(first(j.get("guid"), j.get("id"), "")),
                    title=(j.get("title") or "").strip(),
                    company=company or "Unknown",
                    location=", ".join(locs) if isinstance(locs, list) else (locs or "Remote"),
                    is_remote=True,
                    workplace_type="remote",
                    url=first(j.get("applicationLink"), j.get("url"), j.get("guid")),
                    apply_url=first(j.get("applicationLink"), j.get("url")),
                    description=html_to_text(first(j.get("description"), j.get("excerpt"), "")),
                    salary_min=to_float(j.get("minSalary")),
                    salary_max=to_float(j.get("maxSalary")),
                    salary_currency="USD",
                    salary_interval="yearly",
                    date_posted=str(first(j.get("pubDate"), j.get("publishedDate"), ""))[:10]
                    or None,
                    raw={"seniority": j.get("seniority"), "categories": j.get("categories")},
                )
            )
        offset += PAGE
        if len(rows) < PAGE:
            break
    return out[:limit]
