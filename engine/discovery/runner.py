"""Discovery orchestrator.

Runs each source in isolation (try/except + timing + health log) so one broken
source (a stale ATS token, a LinkedIn 429, a Google outage) never empties the whole
run. Everything is upserted, so re-runs/catch-ups never duplicate.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from engine.config import CompanyTarget, load_companies, load_sources
from engine.db.models import DB
from engine.discovery import jobspy_source
from engine.discovery.apis import adzuna, himalayas
from engine.discovery.ats import ashby, greenhouse, lever, smartrecruiters, workday
from engine.discovery.http import make_client
from engine.normalize import Job, now_iso

ATS_DISPATCH: dict[str, Callable] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
}


def partition_demo(
    companies: list[CompanyTarget], include_demo: bool
) -> tuple[list[CompanyTarget], list[str]]:
    """Split into (active, skipped_names). Demo companies are dropped unless include_demo."""
    if include_demo:
        return list(companies), []
    active = [c for c in companies if not getattr(c, "demo", False)]
    skipped = [c.company for c in companies if getattr(c, "demo", False)]
    return active, skipped


def discover(
    db: DB,
    *,
    sources_cfg: dict | None = None,
    companies: list[CompanyTarget] | None = None,
    terms: list[str] | None = None,
    only: set[str] | None = None,
) -> dict:
    cfg = sources_cfg or load_sources()
    companies = companies if companies is not None else load_companies()
    include_demo = bool(cfg.get("include_demo"))
    companies, skipped_demo = partition_demo(companies, include_demo)
    terms = terms or cfg.get("search_terms", [])
    limits = cfg.get("limits", {})
    cap = int(limits.get("max_jobs_per_run", 400))
    client = make_client(timeout=float(limits.get("per_source_timeout_s", 45)))

    summary: dict = {
        "sources": {},
        "new": 0,
        "seen": 0,
        "fetched": 0,
        "errors": [],
        "skipped_demo": skipped_demo,
    }
    stored_total = 0

    def store(label: str, fetch_fn: Callable[[], list[Job]]) -> None:
        nonlocal stored_total
        start = time.monotonic()
        jobs: list[Job] = []
        ok, err = True, None
        try:
            jobs = fetch_fn() or []
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"{type(e).__name__}: {e}"[:300]
        dur_ms = int((time.monotonic() - start) * 1000)
        new = seen = 0
        for j in jobs:
            if stored_total >= cap:
                break
            created = db.upsert_job(j)
            stored_total += 1
            new += int(created)
            seen += int(not created)
        db.log_source_health(label, ok, len(jobs), err, dur_ms)
        summary["sources"][label] = {
            "ok": ok,
            "fetched": len(jobs),
            "new": new,
            "seen": seen,
            "ms": dur_ms,
            "error": err,
        }
        summary["new"] += new
        summary["seen"] += seen
        summary["fetched"] += len(jobs)
        if err:
            summary["errors"].append(f"{label}: {err}")

    want = lambda name: (only is None) or (name in only)  # noqa: E731

    # 1. Direct ATS feeds (the reliable spine).
    if want("ats") and cfg.get("ats", {}).get("enabled", True):
        for t in companies:
            fn = ATS_DISPATCH.get(t.ats)
            if not fn:
                continue
            store(f"{t.ats}:{t.company}", lambda t=t, fn=fn: fn(t, client))

    # 2. JobSpy — Indeed + LinkedIn guest (health-logged per site).
    # `--only` accepts the umbrella `jobspy` OR the per-site labels `indeed`/`linkedin`
    # (both advertised in the CLI help); honor either, narrowing the sites when a specific
    # one is requested without the umbrella.
    jobspy_cfg = dict(cfg.get("jobspy", {}))
    if only is not None and "jobspy" not in only:
        jobspy_cfg["sites"] = [
            s for s in jobspy_cfg.get("sites", ["indeed", "linkedin"]) if s in only
        ]
    jobspy_selected = want("jobspy") or want("indeed") or want("linkedin")
    if (
        jobspy_selected
        and jobspy_cfg.get("enabled", True)
        and jobspy_cfg.get("sites", ["indeed", "linkedin"])
    ):
        try:
            per_site = jobspy_source.fetch(jobspy_cfg, terms)
        except Exception as e:  # noqa: BLE001
            per_site = {}
            db.log_source_health("jobspy", False, 0, str(e)[:300], 0)
            summary["errors"].append(f"jobspy: {e}")
        for site, jobs in per_site.items():
            store(site, lambda jobs=jobs: jobs)

    # 3. Himalayas (remote-first, free).
    if want("himalayas") and cfg.get("himalayas", {}).get("enabled", True):
        store("himalayas", lambda: himalayas.fetch(cfg["himalayas"], terms, client))

    # 4. Adzuna (free, optional keys; reports "unconfigured" instead of a silent
    # empty fetch when ADZUNA_APP_ID/ADZUNA_APP_KEY are missing — see health.py).
    if want("adzuna") and cfg.get("adzuna", {}).get("enabled", True):
        if not adzuna.configured():
            db.log_source_health(
                "adzuna", False, 0, "unconfigured: missing ADZUNA_APP_ID/ADZUNA_APP_KEY", 0
            )
        else:
            store("adzuna", lambda: adzuna.fetch(cfg["adzuna"], terms, client))

    # F2 hygiene (opt-in via sources.yaml): expire dead postings at the end of a discover.
    # Off by default — it adds N paced HTTP calls per run; always available on demand from
    # the web UI via POST /api/liveness/sweep. Reuses the run's shared client.
    lv = cfg.get("liveness", {})
    if want("liveness") and lv.get("enabled", False):
        from engine.discovery.liveness import sweep_liveness

        summary["liveness"] = sweep_liveness(db, limit=int(lv.get("limit", 40)), client=client)

    # F2 hygiene: recount repost/ghost evidence over the fresh inventory (no network).
    from engine.reposts import sweep_reposts

    summary["reposts_flagged"] = sweep_reposts(db)

    client.close()
    db.meta_set("last_run", now_iso())
    db.meta_set("last_discover", str(summary["new"]))
    if summary["fetched"] > 0 and summary["new"] + summary["seen"] >= 0:
        db.meta_set("last_success_ts", now_iso())
    db.log_event(None, "source_run", {k: v for k, v in summary.items() if k != "sources"})
    return summary
