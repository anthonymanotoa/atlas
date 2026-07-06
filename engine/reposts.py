"""Repost / ghost-job detection (F2 hygiene, imported from career-ops).

A company that re-posts the SAME role (fuzzy-equal title: normalized, seniority and
modality words stripped) under new ids/URLs ≥2 times in 90 days smells like a ghost
posting or a perpetually-open req. We count the evidence into ``jobs.repost_count``;
the scorer applies a light −4 and the UI shows a badge. Deterministic, no network.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from engine.db.models import DB
from engine.normalize import norm_company, norm_text

# Seniority + modality + level-numbering tokens that vary across reposts of the same role.
_STRIP = re.compile(
    r"\b(senior|sr|junior|jr|lead|staff|principal|remote|remoto|hybrid|h[ií]brido|"
    r"on[- ]?site|onsite|presencial|ii|iii|iv)\b"
)
_WS = re.compile(r"\s+")


def core_title(title: str) -> str:
    """The role identity of a title: normalized, minus seniority/modality/level tokens."""
    base = norm_text(title)
    base = _STRIP.sub(" ", base)
    return _WS.sub(" ", base).strip()


def sweep_reposts(db: DB, *, window_days: int = 90) -> int:
    """Recount reposts over the window and persist ``repost_count`` per job.

    repost_count = (# distinct postings of the same company+core_title in the window) − 1,
    so 0 means unique and ≥1 means "seen re-posted". Idempotent: recomputed from scratch
    for every job discovered inside the window (stale rows outside it are left alone).
    Returns how many rows carry a flag (repost_count ≥ 1) after the sweep.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
    rows = db.conn.execute(
        "SELECT id, company, title FROM jobs WHERE discovered_at >= ?", (cutoff,)
    ).fetchall()
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        key = (norm_company(r["company"]), core_title(r["title"]))
        if key[1]:  # a title made only of stripped tokens has no identity — skip
            groups[key].add(r["id"])
    flagged = 0
    for ids in groups.values():
        repost = len(ids) - 1 if len(ids) >= 2 else 0
        for jid in ids:
            db.conn.execute("UPDATE jobs SET repost_count=? WHERE id=?", (repost, jid))
        flagged += len(ids) if repost else 0
    db.conn.commit()
    return flagged
