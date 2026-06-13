"""Ashby public Job Posting API (keyless).

GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true
Note: {name} is CASE-SENSITIVE (match the jobs.ashbyhq.com/<name> URL exactly).
"""

from __future__ import annotations

import re

import httpx

from engine.config import CompanyTarget
from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import canonical_salary_interval, first, to_float

BASE = "https://api.ashbyhq.com/posting-api/job-board"

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
_NUM = re.compile(r"([\d][\d.,]*)\s*([kKmM])?")


def _parse_salary_string(s: str) -> tuple[float | None, float | None, str | None, str | None]:
    """Best-effort parse of Ashby's `compensationTierSummary` (e.g. '$120K – $160K • Equity').

    Conservative: only returns numbers when a currency symbol is present, to avoid
    mistaking benefit text ('401k') or year counts for salary.
    """
    if not s or not any(sym in s for sym in _CURRENCY_SYMBOLS):
        return None, None, None, None
    currency = next((v for sym, v in _CURRENCY_SYMBOLS.items() if sym in s), None)
    interval = canonical_salary_interval(s)
    nums: list[float] = []
    for m in _NUM.finditer(s):
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        suffix = (m.group(2) or "").lower()
        if suffix == "k":
            val *= 1_000
        elif suffix == "m":
            val *= 1_000_000
        # Drop bare small numbers for annual/unknown intervals (junk like "2024"); keep
        # genuine hourly/weekly figures.
        if interval in (None, "yearly") and val < 1_000:
            continue
        nums.append(val)
    if not nums:
        return None, None, currency, interval
    return min(nums), (max(nums) if len(nums) > 1 else None), currency, interval


def _salary_from_comp(comp: dict) -> tuple[float | None, float | None, str | None, str | None]:
    """Prefer Ashby's structured `summaryComponents`; fall back to the summary string."""
    for c in comp.get("summaryComponents") or []:
        kind = (c.get("componentType") or c.get("compensationType") or "").lower()
        if "salary" in kind:
            mn, mx = to_float(c.get("minValue")), to_float(c.get("maxValue"))
            if mn or mx:
                return (
                    mn,
                    mx,
                    c.get("currencyCode"),
                    canonical_salary_interval(c.get("interval")),
                )
    return _parse_salary_string(
        comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary") or ""
    )


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    url = f"{BASE}/{target.token}"
    data = get_json(client, url, params={"includeCompensation": "true"})
    jobs: list[Job] = []
    for j in data.get("jobs", []):
        comp = j.get("compensation") or {}
        sal_min, sal_max, sal_cur, sal_interval = _salary_from_comp(comp)
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
                salary_min=sal_min,
                salary_max=sal_max,
                salary_currency=sal_cur,
                salary_interval=sal_interval,
                date_posted=(j.get("publishedAt") or "")[:10] or None,
                raw={
                    "department": j.get("department"),
                    "team": j.get("team"),
                    "compensation": comp.get("compensationTierSummary"),
                },
            )
        )
    return jobs
