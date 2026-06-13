"""Adzuna — free official jobs API (needs ADZUNA_APP_ID / ADZUNA_APP_KEY).

  GET https://api.adzuna.com/v1/api/jobs/{country}/search/1?app_id=..&app_key=..
      &results_per_page=20&what=<term>&content-type=application/json
Skips silently if no keys are configured (stays $0).
"""

from __future__ import annotations

import os

import httpx

from engine.discovery.http import get_json
from engine.normalize import Job
from engine.util import html_to_text, to_float

BASE = "https://api.adzuna.com/v1/api/jobs"
CURRENCY = {
    "us": "USD",
    "gb": "GBP",
    "de": "EUR",
    "ca": "CAD",
    "au": "AUD",
    "fr": "EUR",
    "es": "EUR",
    "nl": "EUR",
    "it": "EUR",
}


def configured() -> bool:
    return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))


def fetch(cfg: dict, search_terms: list[str], client: httpx.Client) -> list[Job]:
    if not configured():
        return []
    app_id = os.environ["ADZUNA_APP_ID"]
    app_key = os.environ["ADZUNA_APP_KEY"]
    countries = cfg.get("countries", ["us"])
    per = int(cfg.get("results_per_country", 20))
    terms = search_terms[:2]  # keep request volume modest
    out: list[Job] = []
    for country in countries:
        for term in terms:
            data = get_json(
                client,
                f"{BASE}/{country}/search/1",
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": per,
                    "what": term,
                    "content-type": "application/json",
                },
            )
            for r in data.get("results", []):
                loc = (r.get("location") or {}).get("display_name")
                out.append(
                    Job(
                        source="adzuna",
                        source_job_id=str(r.get("id")),
                        title=(r.get("title") or "").strip(),
                        company=(r.get("company") or {}).get("display_name") or "Unknown",
                        location=loc,
                        url=r.get("redirect_url"),
                        apply_url=r.get("redirect_url"),
                        description=html_to_text(r.get("description")),
                        employment_type=r.get("contract_time"),
                        salary_min=to_float(r.get("salary_min")),
                        salary_max=to_float(r.get("salary_max")),
                        salary_currency=CURRENCY.get(country, "USD"),
                        salary_interval="yearly",
                        date_posted=(r.get("created") or "")[:10] or None,
                        raw={
                            "country": country,
                            "category": (r.get("category") or {}).get("label"),
                        },
                    )
                )
    return out
