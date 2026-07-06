"""Liveness gate (F2 hygiene, imported from career-ops): is a stored posting still live?

Deterministic HTTP checks only — 404/410, tombstone phrases (multi-language) and a
redirect back to a careers root all mean the vacancy is gone → state ``expired``.
Anything ambiguous (5xx, timeouts, transport errors) is 'unknown' and NEVER expires
a job: false-expiring a live posting costs an application; a dead one lingering costs
nothing. $0 and keyless, like the rest of the engine.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

import httpx

from engine.db.models import DB
from engine.discovery.http import make_client
from engine.normalize import now_iso

DEAD_STATUSES = frozenset({404, 410})

_DEAD_PHRASES = re.compile(
    r"(job (?:posting |opening )?(?:is )?no longer (?:available|active|open)"
    r"|no longer accepting applications"
    r"|position has been filled"
    r"|job (?:posting )?not found"
    r"|posting (?:has )?expired"
    r"|this job is (?:closed|expired)"
    r"|esta (?:oferta|vacante|posici[oó]n) ya no est[aá] disponible"
    r"|la vacante (?:fue cerrada|ya no existe)"
    r"|oferta caducada"
    r"|cette offre n(?:'|’)est plus disponible"
    r"|stelle ist nicht mehr verf[uü]gbar"
    r"|vaga (?:encerrada|expirada))",
    re.I,
)

# Only pre-application states are expirable: later stages carry human work we never discard.
SWEEP_STATES: tuple[str, ...] = (
    "discovered",
    "scored",
    "shortlisted",
    "tailored",
    "drafted",
    "ready",
)


def check_url(client: httpx.Client, url: str) -> tuple[str, str]:
    """('alive' | 'dead' | 'unknown', reason). GET, not HEAD — many ATSes reject HEAD."""
    try:
        resp = client.get(url)
    except httpx.HTTPError as e:
        return "unknown", type(e).__name__
    if resp.status_code in DEAD_STATUSES:
        return "dead", f"http {resp.status_code}"
    if resp.status_code >= 400:
        return "unknown", f"http {resp.status_code}"
    if resp.history:  # redirected — a bounce to the careers root is a tombstone
        final_segments = [s for s in urlsplit(str(resp.url)).path.split("/") if s]
        if len(final_segments) <= 1:
            return "dead", f"redirected to careers root ({resp.url})"
    m = _DEAD_PHRASES.search(resp.text[:200_000])
    if m:
        return "dead", f'tombstone phrase: "{m.group(0)}"'
    return "alive", "ok"


def sweep_liveness(
    db: DB, *, limit: int = 40, client: httpx.Client | None = None, delay_s: float = 0.5
) -> dict:
    """Check the least-recently-checked active jobs with a URL; expire the dead ones.

    Rate-limited (``delay_s`` between requests — never hammer an ATS). Every checked job
    gets ``liveness_checked_at`` stamped so successive sweeps rotate through the inventory.
    """
    owns_client = client is None
    client = client or make_client(timeout=10)
    placeholders = ",".join("?" * len(SWEEP_STATES))
    rows = db.conn.execute(
        f"SELECT id, url FROM jobs WHERE state IN ({placeholders}) AND url IS NOT NULL "
        "ORDER BY COALESCE(liveness_checked_at, '') ASC, discovered_at ASC LIMIT ?",
        (*SWEEP_STATES, int(limit)),
    ).fetchall()
    out = {"checked": 0, "expired": 0, "unknown": 0}
    try:
        for i, r in enumerate(rows):
            if i and delay_s:
                time.sleep(delay_s)
            verdict, reason = check_url(client, r["url"])
            db.conn.execute(
                "UPDATE jobs SET liveness_checked_at=? WHERE id=?", (now_iso(), r["id"])
            )
            db.conn.commit()
            out["checked"] += 1
            if verdict == "dead":
                db.set_state(r["id"], "expired", {"reason": reason, "via": "liveness"})
                out["expired"] += 1
            elif verdict == "unknown":
                out["unknown"] += 1
    finally:
        if owns_client:
            client.close()
    return out
