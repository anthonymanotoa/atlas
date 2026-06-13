"""Workday public CXS API (keyless).

  POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
  body {"limit": 20, "offset": 0, "searchText": "", "appliedFacets": {}}
  → {"total": N, "jobPostings": [{title, externalPath, locationsText, bulletFields, postedOn}]}

Contract (uses the fields CompanyTarget already reserves):
  target.instance = the Workday tenant (subdomain, e.g. "nvidia")
  target.token    = the careers-site slug (e.g. "NVIDIAExternalCareerSite")
  target.careers_url carries the full host incl. the wd-cluster (wd1/wd5/…); we
  read the cluster from it since CompanyTarget has no separate field for it.

List rows carry NO description (Workday puts it behind a per-posting detail fetch);
we leave description="" rather than fabricate. A detail fetch is a documented
open question (see plans/018), deferred to keep the spike account-safe.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from engine.config import CompanyTarget
from engine.discovery.http import post_json
from engine.normalize import Job

PAGE = 20
MAX_JOBS = 100  # bound the run: a giant enterprise board (e.g. total=2000) can't blow up a $0/account-safe pull


def _host(target: CompanyTarget) -> str:
    """The full Workday host incl. wd-cluster, taken from careers_url; default wd1."""
    if target.careers_url:
        netloc = urlsplit(target.careers_url).netloc
        if netloc:
            return netloc
    return f"{target.instance}.wd1.myworkdayjobs.com"


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    host = _host(target)
    tenant, site = target.instance, target.token
    cxs = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    jobs: list[Job] = []
    offset = 0
    while len(jobs) < MAX_JOBS:
        body = {"limit": PAGE, "offset": offset, "searchText": "", "appliedFacets": {}}
        data = post_json(client, cxs, json=body)
        postings = data.get("jobPostings") or []
        if not postings:
            break
        for p in postings:
            path = p.get("externalPath") or ""
            bullets = p.get("bulletFields") or []
            jobs.append(
                Job(
                    source="workday",
                    source_job_id=(bullets[0] if bullets else path) or None,
                    title=(p.get("title") or "").strip(),
                    company=target.company,
                    location=p.get("locationsText"),
                    url=f"https://{host}/{site}{path}",
                    apply_url=f"https://{host}/{site}{path}",
                    description="",  # not in the list payload; never fabricated
                    date_posted=None,  # "postedOn" is relative text ("Posted 30+ Days Ago"), not a date
                    raw={"posted_on": p.get("postedOn")},
                )
            )
            if len(jobs) >= MAX_JOBS:
                break
        total = int(data.get("total") or 0)
        offset += PAGE
        if offset >= total:
            break
    return jobs
