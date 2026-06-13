"""JobSpy aggregator: Indeed (reliable, no rate-limit) + LinkedIn guest (account-safe,
IP-throttle only, hard-capped). Google/ZipRecruiter intentionally excluded (broken in 2026).

LinkedIn is scraped as a logged-OUT guest — JobSpy never receives credentials — so the
worst case is a temporary IP 429, never a LinkedIn *account* ban.
"""

from __future__ import annotations

import math
import random
import time

from engine.normalize import Job
from engine.util import to_float


def _df_records(df) -> list[dict]:
    if df is None or len(df) == 0:
        return []
    import pandas as pd

    return df.astype(object).where(pd.notnull(df), None).to_dict("records")


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _to_job(r: dict, site: str) -> Job | None:
    title = _clean(r.get("title"))
    company = _clean(r.get("company"))
    if not title or not company:
        return None
    interval = _clean(r.get("interval"))
    return Job(
        source=site,
        source_job_id=str(_clean(r.get("id")) or ""),
        title=str(title).strip(),
        company=str(company).strip(),
        location=_clean(r.get("location")),
        is_remote=bool(r["is_remote"]) if _clean(r.get("is_remote")) is not None else None,
        url=_clean(r.get("job_url")),
        apply_url=_clean(r.get("job_url_direct")) or _clean(r.get("job_url")),
        description=_clean(r.get("description")) or "",
        employment_type=_clean(r.get("job_type")),
        salary_min=to_float(_clean(r.get("min_amount"))),
        salary_max=to_float(_clean(r.get("max_amount"))),
        salary_currency=_clean(r.get("currency")),
        salary_interval={
            "yearly": "yearly",
            "annually": "yearly",
            "monthly": "monthly",
            "hourly": "hourly",
        }.get(str(interval).lower())
        if interval
        else None,
        date_posted=str(_clean(r.get("date_posted")) or "")[:10] or None,
        raw={"company_url": _clean(r.get("company_url"))},
    )


def _scrape(
    site: str,
    term: str,
    *,
    results_wanted: int,
    is_remote: bool,
    hours_old: int,
    country_indeed: str,
    fetch_desc: bool,
) -> list[dict]:
    from jobspy import scrape_jobs

    kwargs = dict(  # noqa: C408
        site_name=[site],
        search_term=term,
        results_wanted=results_wanted,
        is_remote=is_remote,
        hours_old=hours_old,
    )
    if site == "indeed":
        kwargs["country_indeed"] = country_indeed
    if site == "linkedin":
        kwargs["linkedin_fetch_description"] = fetch_desc
    df = scrape_jobs(**kwargs)
    return _df_records(df)


def fetch(cfg: dict, search_terms: list[str]) -> dict[str, list[Job]]:
    """Returns {site_name: [Job]} so the runner can health-log each site separately."""
    sites = cfg.get("sites", ["indeed", "linkedin"])
    results_wanted = int(cfg.get("results_wanted", 25))
    hours_old = int(cfg.get("hours_old", 168))
    is_remote = bool(cfg.get("is_remote", True))
    country_indeed = cfg.get("country_indeed", "USA")
    linkedin_cap = int(cfg.get("linkedin_cap", 200))
    fetch_desc = bool(cfg.get("linkedin_fetch_description", False))

    # LinkedIn guest pacing: space out scrape calls (with jitter) so a multi-term run
    # never hammers LinkedIn into an IP throttle. Slower is fine — account-safe by design.
    linkedin_delay_ms = int(cfg.get("linkedin_delay_ms", 2500))

    out: dict[str, list[Job]] = {}
    for site in sites:
        jobs: list[Job] = []
        for i, term in enumerate(search_terms):
            if site == "linkedin" and len(jobs) >= linkedin_cap:
                break
            if site == "linkedin" and linkedin_delay_ms and i > 0:
                time.sleep(linkedin_delay_ms / 1000 * (0.8 + 0.4 * random.random()))
            try:
                records = _scrape(
                    site,
                    term,
                    results_wanted=results_wanted,
                    is_remote=is_remote,
                    hours_old=hours_old,
                    country_indeed=country_indeed,
                    fetch_desc=fetch_desc,
                )
            except Exception:  # noqa: BLE001 — one bad term must not kill the site
                records = []
            for r in records:
                j = _to_job(r, site)
                if j:
                    jobs.append(j)
            if site == "linkedin" and len(jobs) >= linkedin_cap:
                jobs = jobs[:linkedin_cap]
                break
        out[site] = jobs
    return out
