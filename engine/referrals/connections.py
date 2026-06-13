"""Referral detection via the user's LinkedIn data export (Connections.csv).

This is the account-SAFE way to get the 1st-degree graph: the user downloads their own
data from LinkedIn (Settings → Data privacy → Get a copy of your data → Connections),
drops Connections.csv into data/inbox/, and Atlas matches connections' companies to job
companies. No scraping, no login, zero account risk. 2nd-degree is handled separately
via Claude-in-Chrome on the user's own session, on demand.
"""

from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz

from engine.db.models import DB
from engine.normalize import norm_company

MATCH_THRESHOLD = 88  # token_sort_ratio on normalized company names


def import_connections_csv(db: DB, csv_path: Path) -> int:
    """Import a LinkedIn Connections.csv into contacts (degree=1). Returns count imported."""
    text = csv_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    # LinkedIn prepends a few "Notes:" lines before the real header row.
    start = next((i for i, line in enumerate(text) if line.lower().startswith("first name")), 0)
    reader = csv.DictReader(text[start:])
    imported = 0
    for row in reader:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        name = f"{first} {last}".strip()
        company = (row.get("Company") or "").strip()
        if not name or not company:
            continue
        db.add_contact(
            name=name,
            company=company,
            title=(row.get("Position") or "").strip() or None,
            linkedin_url=(row.get("URL") or "").strip() or None,
            email=(row.get("Email Address") or "").strip() or None,
            degree=1,
            role="connection",
            source="connections_csv",
        )
        imported += 1
    db.log_event(None, "note", {"connections_imported": imported, "file": str(csv_path)})
    return imported


def match_referrals(
    db: DB, company: str, threshold: int = MATCH_THRESHOLD, contacts: list[dict] | None = None
) -> list[dict]:
    """Return 1st-degree contacts whose company fuzzy-matches `company`, best first.

    Pass a preloaded `contacts` list (from db.all_contacts()) when matching many jobs in a
    loop, so the full contacts table is read once instead of once per job."""
    target = norm_company(company)
    if not target:
        return []
    rows = contacts if contacts is not None else db.all_contacts()
    out = []
    for c in rows:
        score = fuzz.token_sort_ratio(target, norm_company(c.get("company") or ""))
        if score >= threshold:
            out.append({**c, "_match": score})
    return sorted(out, key=lambda c: c["_match"], reverse=True)


def referrals_for_jobs(db: DB, jobs: list[dict]) -> dict[str, list[dict]]:
    """Map job_id -> matching 1st-degree contacts (for the dashboard/brain)."""
    return {j["id"]: match_referrals(db, j.get("company", "")) for j in jobs}
