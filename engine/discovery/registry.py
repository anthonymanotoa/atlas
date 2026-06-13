"""Resolve which ATS a company uses (and its token) from a careers URL.

Follows redirects and pattern-matches the final host/path + page body for the
known board patterns. Companies migrate ATS over time, so re-run this periodically.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit

import httpx

from engine.discovery.http import make_client

# host/path patterns → (ats, regex capturing the token)
PATTERNS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([a-z0-9_-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)", re.I)),
    # Workday: capture the tenant (subdomain) from {tenant}.{wdN}.myworkdayjobs.com.
    ("workday", re.compile(r"https?://([a-z0-9-]+)\.[a-z0-9]+\.myworkdayjobs\.com", re.I)),
]

_LOCALE = re.compile(r"[a-z]{2}(-[A-Za-z]{2})?$")


def _workday_site(url: str) -> Optional[str]:
    """The careers-site slug = first non-locale path segment of a Workday URL."""
    segs = [s for s in urlsplit(url).path.split("/") if s and not _LOCALE.fullmatch(s)]
    return segs[0] if segs else None


def resolve_ats(careers_url: str, client: Optional[httpx.Client] = None) -> Optional[dict]:
    """Return the ATS contract for a careers URL, or None if no known ATS detected.

    Most boards: {'ats', 'token', 'eu'}. Workday additionally carries 'instance'
    (the tenant) and uses 'token' for the site slug — mirroring CompanyTarget.
    """
    owns_client = client is None
    client = client or make_client(timeout=20)
    try:
        try:
            resp = client.get(careers_url)
            haystacks = [str(resp.url), resp.text[:200_000]]
        except httpx.HTTPError:
            haystacks = [careers_url]
        for hay in haystacks:
            for ats, rx in PATTERNS:
                m = rx.search(hay)
                if m:
                    token = m.group(1)
                    if token.lower() in ("embed", "job_board"):
                        continue
                    if ats == "workday":
                        # group(1) is the tenant → instance; the site comes from the path.
                        return {"ats": "workday", "instance": token,
                                "token": _workday_site(careers_url), "eu": False,
                                "careers_url": careers_url}
                    eu = ats == "lever" and "eu.lever.co" in hay
                    return {"ats": ats, "token": token, "eu": eu}
        return None
    finally:
        if owns_client:
            client.close()
