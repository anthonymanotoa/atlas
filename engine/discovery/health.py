"""Honest per-source health classification.

`source_health` logs one row per source per discovery run. Read in isolation,
`ok=1, count=0` is ambiguous — it means "ran fine, found nothing" for a source
that legitimately has no matches this run, but it ALSO means "silently skipped
because credentials are missing" for a source like Adzuna that used to return
[] without saying why. This module turns the raw rows into one of four honest
states so `atlas status` and the dashboard can tell those apart:

* ``unconfigured`` — the source can't run at all (missing credentials/config).
* ``error``        — the most recent run failed for some other reason.
* ``ok_empty``      — the source ran fine but has returned 0 results for a
  streak of runs (a real signal worth a human glance: dead filters? expired
  creds that don't hard-fail? overly narrow search terms?).
* ``ok``           — business as usual.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.db.models import DB

UNCONFIGURED_PREFIX = "unconfigured:"


def classify_sources(db: "DB", empty_streak: int = 3) -> list[dict]:
    """Return one classification dict per known source.

    Each dict: ``{"source", "state", "hint", "last_run", "last_count"}`` with
    ``state`` in ``{"ok", "ok_empty", "unconfigured", "error"}``.
    """
    sources = [
        r["source"] for r in db.conn.execute("SELECT DISTINCT source FROM source_health")
    ]
    out = []
    for source in sources:
        rows = [
            dict(r)
            for r in db.conn.execute(
                "SELECT * FROM source_health WHERE source=? ORDER BY run_at DESC LIMIT ?",
                (source, empty_streak),
            )
        ]
        out.append(_classify_one(source, rows))
    return out


def _classify_one(source: str, rows: list[dict]) -> dict:
    if not rows:
        return {"source": source, "state": "ok", "hint": "", "last_run": None, "last_count": None}

    latest = rows[0]
    last_run = latest.get("run_at")
    last_count = latest.get("count")

    if not latest.get("ok"):
        error = latest.get("error") or ""
        if error.startswith(UNCONFIGURED_PREFIX):
            hint = error[len(UNCONFIGURED_PREFIX) :].strip() or "faltan credenciales"
            return {
                "source": source,
                "state": "unconfigured",
                "hint": hint,
                "last_run": last_run,
                "last_count": last_count,
            }
        return {
            "source": source,
            "state": "error",
            "hint": error,
            "last_run": last_run,
            "last_count": last_count,
        }

    if rows and all(r.get("ok") and (r.get("count") or 0) == 0 for r in rows):
        n = len(rows)
        hint = f"0 resultados en las últimas {n} corridas — ¿credenciales o filtros?"
        return {
            "source": source,
            "state": "ok_empty",
            "hint": hint,
            "last_run": last_run,
            "last_count": last_count,
        }

    return {
        "source": source,
        "state": "ok",
        "hint": "",
        "last_run": last_run,
        "last_count": last_count,
    }
