"""SmartRecruiters public Posting API (keyless, two-tier list + detail).

  list:   GET https://api.smartrecruiters.com/v1/companies/{id}/postings?limit=100
  detail: GET https://api.smartrecruiters.com/v1/companies/{id}/postings/{postingId}
"""
from __future__ import annotations

import httpx

from engine.config import CompanyTarget
from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import html_to_text

BASE = "https://api.smartrecruiters.com/v1/companies"
DETAIL_CAP = 40  # bound the N+1 detail fetches per company per run


def _location_str(loc: dict) -> str:
    parts = [loc.get("city"), loc.get("region"), loc.get("country")]
    s = ", ".join(p for p in parts if p)
    if loc.get("remote"):
        s = (s + " (Remote)").strip()
    return s


def _description(detail: dict) -> str:
    sections = ((detail.get("jobAd") or {}).get("sections")) or {}
    chunks = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(key) or {}).get("text")
        if text:
            chunks.append(html_to_text(text))
    return "\n\n".join(chunks)


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    listing = get_json(client, f"{BASE}/{target.token}/postings", params={"limit": 100})
    jobs: list[Job] = []
    for i, p in enumerate(listing.get("content", [])):
        loc = p.get("location") or {}
        pid = p.get("id")
        description = ""
        if i < DETAIL_CAP and pid:
            try:
                detail = get_json(client, f"{BASE}/{target.token}/postings/{pid}")
                description = _description(detail)
            except httpx.HTTPError:
                description = ""
        jobs.append(Job(
            source="smartrecruiters",
            source_job_id=pid,
            title=(p.get("name") or "").strip(),
            company=target.company,
            location=_location_str(loc),
            is_remote=bool(loc.get("remote")) if "remote" in loc else None,
            url=f"https://jobs.smartrecruiters.com/{target.token}/{pid}",
            apply_url=f"https://jobs.smartrecruiters.com/{target.token}/{pid}",
            description=description,
            employment_type=(p.get("typeOfEmployment") or {}).get("label"),
            date_posted=(p.get("releasedDate") or "")[:10] or None,
            raw={"department": (p.get("department") or {}).get("label")},
        ))
    return jobs
