"""Freshness heartbeat — the mitigation for the Cowork 'only runs while awake' gap.

Every successful brain run stamps `last_success_ts`. If the gap since the last success
exceeds the threshold, the dashboard shows an 'I was down' banner so a silently-skipped
schedule (sleeping machine / closed app) never goes unnoticed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from engine.db.models import DB
from engine.normalize import now_iso

STALE_HOURS = 26.0  # a daily task should run within ~26h; longer = something's wrong


def beat(db: DB) -> None:
    db.meta_set("last_success_ts", now_iso())


def last_success(db: DB) -> datetime | None:
    raw = db.meta_get("last_success_ts")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    # Assume UTC for any naive value so the downtime subtraction below never raises TypeError.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def downtime_hours(db: DB) -> float | None:
    """Hours since last success if it exceeds STALE_HOURS, else None."""
    ls = last_success(db)
    if not ls:
        return None
    gap = (datetime.now(UTC) - ls).total_seconds() / 3600
    return round(gap, 1) if gap > STALE_HOURS else None
