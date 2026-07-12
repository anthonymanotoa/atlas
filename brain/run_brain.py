"""Atlas brain — the deterministic daily pipeline the Cowork scheduled task runs.

It does ALL the deterministic work (discover → score → tailor → draft → package) and
writes a Spanish 'morning brief'. It SENDS NOTHING. The Cowork session that invokes this
(see brain/SKILL.md) optionally sharpens wording and creates Gmail *drafts* via the Gmail
connector — the human is always the send step.

Idempotent: prepares only shortlisted jobs not yet prepared, and outreach/CV builders skip
work already done, so a catch-up run never duplicates drafts.

Run:  uv run atlas brain   (or)   uv run python brain/run_brain.py --limit 8
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

import engine.paths as paths
from engine import heartbeat
from engine import intents as intent_queue
from engine.config import load_criteria, load_cv_layout, load_master_cv
from engine.cv.build import build_for_job
from engine.cv.pdf_check import check_page_count
from engine.db.models import DB
from engine.discovery.health import classify_sources
from engine.discovery.runner import discover
from engine.learning.runner import auto_learn_all
from engine.normalize import norm_company, now_iso, parse_dt_utc
from engine.outreach.build import build_outreach, write_package
from engine.outreach.followups import followup_text
from engine.referrals.connections import match_referrals
from engine.scoring.dedupe import collapse_variants
from engine.scoring.run import score_jobs

# Task 18 — planner caps. Independent of `run()`'s own `--limit` (which bounds how many
# shortlisted jobs get a full CV/outreach prep pass this run); this bounds how many NEW
# research intents the planner enqueues per run so a big backlog doesn't flood the queue.
PLANNER_CAP = 5
PORTFOLIO_REVIEW_MAX_AGE_DAYS = 7


def _shortlisted_to_prepare(db: DB, limit: int) -> list[dict]:
    """Task 9 follow-up: the jobs the brain should actually prepare this run.

    Collapses near-identical shortlist variants (same norm_company + core_title — e.g. 7
    reposts of "Senior Data Scientist @ CVS Health") into one canonical per group BEFORE
    slicing to `limit`, so a repost cluster doesn't burn the whole prep budget on
    duplicates. Mirrors `atlas top` / `/api/board` (collapse the FULL shortlisted pool,
    THEN slice) — collapsing after truncating could hide other companies behind a cluster
    that already ate all `limit` slots. Used by both the real prep loop and the dry-run
    preview so they can never drift from each other.
    """
    pool = collapse_variants(db.list_jobs(state="shortlisted"))
    return pool[:limit]


def _dry_run_summary(db: DB, *, limit: int, do_discover: bool) -> dict:
    """Read-only preview of what a real `run()` would do — zero writes.

    Reuses the same selectors the real run does (counts_by_state for what discovery
    would hand to the scorer, `_shortlisted_to_prepare` for what prepare would pick up —
    variant-collapsed, same as the real prep loop), so this never drifts from reality
    without both being updated together.
    """
    would_prep = [
        {
            "id": j["id"],
            "title": j["title"],
            "company": j["company"],
            "already_prepared": bool(db.cv_versions_for(j["id"])),
            "variant_count": j.get("variant_count", 1),
        }
        for j in _shortlisted_to_prepare(db, limit)
    ]
    return {
        "dry_run": True,
        "would_discover": do_discover,
        "would_score": db.counts_by_state().get("discovered", 0),
        "would_prep": would_prep,
        "pending_intents": len(intent_queue.list_pending(db)),
    }


def plan_and_enqueue(db: DB, limit: int = PLANNER_CAP) -> dict:
    """Deterministic planner (F4/Task 18): decides what NEW research the brain should do
    and ENQUEUES it — the intent queue used to be purely reactive (web → brain), this makes
    the brain proactive about its own backlog. Idempotent: never enqueues a second pending
    intent of the same type+job/company when one is already pending, and skips work that's
    already on file. Returns ``{"company_research": n, "contact_discovery": m,
    "portfolio_research": k}`` — how many of each got enqueued THIS call.

    1. company_research — top `limit` shortlisted jobs (already ordered by fit_score DESC),
       one per distinct company, skipping companies with research on file or a pending intent.
    2. contact_discovery — up to `limit` `ready` jobs whose company has no brain-discovered
       contact yet (source == 'brain_research'), skipping jobs with a pending intent.
    3. portfolio_research — at most once a week: only if the last review is missing or older
       than PORTFOLIO_REVIEW_MAX_AGE_DAYS, and only if none is already pending.
    """
    enqueued = {"company_research": 0, "contact_discovery": 0, "portfolio_research": 0}
    pending = intent_queue.list_pending(db)
    pending_job_ids = {
        t: {p["job_id"] for p in pending if p["type"] == t}
        for t in ("company_research", "contact_discovery")
    }

    # 1. company_research — one per distinct company among the top shortlisted jobs.
    seen_companies: set[str] = set()
    for job in db.list_jobs(state="shortlisted", limit=limit):
        norm = norm_company(job.get("company") or "")
        if not norm or norm in seen_companies:
            continue
        seen_companies.add(norm)
        if job["id"] in pending_job_ids["company_research"]:
            continue
        if db.company_research_for(norm):
            continue
        intent_queue.enqueue(db, "company_research", job_id=job["id"])
        enqueued["company_research"] += 1

    # 2. contact_discovery — ready jobs with no brain-discovered contact yet.
    brain_contact_companies = {
        norm_company(c.get("company") or "")
        for c in db.all_contacts()
        if c.get("source") == "brain_research"
    }
    count = 0
    for job in db.list_jobs(state="ready", limit=limit):
        if count >= limit:
            break
        norm = norm_company(job.get("company") or "")
        if not norm:
            continue
        if job["id"] in pending_job_ids["contact_discovery"]:
            continue
        if norm in brain_contact_companies:
            continue
        intent_queue.enqueue(db, "contact_discovery", job_id=job["id"])
        enqueued["contact_discovery"] += 1
        count += 1

    # 3. portfolio_research — weekly cadence, never job-scoped (job_id is always None).
    already_pending = any(p["type"] == "portfolio_research" for p in pending)
    if not already_pending:
        last_review = parse_dt_utc(db.last_peer_review())
        stale = (
            last_review is None
            or (datetime.now(UTC) - last_review).days >= PORTFOLIO_REVIEW_MAX_AGE_DAYS
        )
        if stale:
            intent_queue.enqueue(db, "portfolio_research")
            enqueued["portfolio_research"] += 1

    return enqueued


def run(
    db: DB,
    *,
    limit: int = 8,
    language: str = "en",
    do_discover: bool = True,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return _dry_run_summary(db, limit=limit, do_discover=do_discover)

    summary: dict = {
        "discover": {},
        "scored": 0,
        "shortlisted": 0,
        "prepared": [],
        "prepare_errors": [],
        "pdf_checks": [],
        "followups": 0,
        "downtime_hours": None,
    }

    if do_discover:
        summary["discover"] = {k: v for k, v in discover(db).items() if k != "sources"}

    criteria = load_criteria()
    scored, shortlisted = score_jobs(db, criteria)
    summary["scored"], summary["shortlisted"] = scored, shortlisted

    # Prepare the top shortlisted jobs not yet prepared. Variant-collapsed (Task 9
    # follow-up): only the canonical of each near-identical repost cluster gets a CV/package
    # this run — the variants stay in the DB, just not re-prepared 5-7x in a row.
    for j in _shortlisted_to_prepare(db, limit):
        try:
            cv = build_for_job(db, j["id"], language=language)
            build_outreach(db, j["id"], language=language)
            write_package(db, j["id"], language=language)
            summary["prepared"].append(
                {
                    "id": j["id"],
                    "title": j["title"],
                    "company": j["company"],
                    "coverage": cv.coverage,
                }
            )
        except Exception as e:  # noqa: BLE001 — one job must not break the batch
            summary["prepare_errors"].append({"id": j["id"], "error": str(e)[:200]})
            db.log_event(j["id"], "error", {"stage": "prepare", "error": str(e)[:200]})

    # F4 §7.2 — deterministic half of the visual PDF check. Count pages for every CV we
    # prepared today so the brain (SKILL step 4) knows which PDFs to open and fix. The
    # non-deterministic half (orphaned headings, mixed fonts) is the brain reading the PDF.
    max_pages = int(load_cv_layout().get("max_pages") or 2)
    for prep in summary["prepared"]:
        versions = db.cv_versions_for(prep["id"])
        pdf = versions[0].get("path_pdf") if versions else None
        if not pdf:
            continue
        chk = check_page_count(pdf, max_pages=max_pages)
        summary["pdf_checks"].append({"job_id": prep["id"], "pdf_path": pdf, **chk})

    # Due follow-ups → draft (never send), then mark done.
    candidate = {"name": (load_master_cv().get("basics", {}) or {}).get("name", "")}
    for f in db.due_followups(now_iso()):
        if f.get("kind"):
            continue  # v2 (F3): los toques por estado se confirman a mano en /followups — nunca auto-draftar
        job = db.get_job(f["job_id"])
        if not job:
            db.mark_followup(f["id"], "cancelled")
            continue
        d = followup_text(job, candidate, f["touch_number"], language)
        # Dedup per (job, kind, variant): touches 1-3 share kind 'follow_up' but differ by
        # variant 'touchN', so guarding on kind alone would drop touches 2 and 3.
        if not db.has_message(f["job_id"], d.kind, variant=d.variant):
            db.add_message(
                f["job_id"],
                channel=d.channel,
                kind=d.kind,
                body=d.body,
                subject=d.subject,
                variant=d.variant,
                language=d.language,
                state="draft",
            )
        db.mark_followup(f["id"], "done")
        summary["followups"] += 1

    # Refresh per-company learnings from any HUMAN-confirmed outcomes (P2-D). The brain
    # never fabricates outcomes — it only rolls up what the user recorded via form/CLI.
    summary["learnings"] = auto_learn_all(db)

    # Task 18 — planner: enqueue new research intents (idempotent) so the brain drives its
    # own backlog instead of only reacting to web-queued work. NOT run in dry_run (early
    # return above skips this whole function body).
    summary["enqueued_intents"] = plan_and_enqueue(db)

    # F4 paso 0 (parte determinista): reportar la cola. El drenaje REAL lo hace la sesión
    # de Claude que invoca esto (SKILL.md paso 0) — aquí solo se hace visible lo pendiente.
    summary["intents_pending"] = [
        {"id": i["id"], "type": i["type"], "job_id": i["job_id"]}
        for i in intent_queue.list_pending(db)
    ]

    summary["downtime_hours"] = heartbeat.downtime_hours(db)
    heartbeat.beat(db)
    db.log_event(
        None,
        "note",
        {"brain_run": True, **{k: summary[k] for k in ("scored", "shortlisted", "followups")}},
    )
    write_morning_brief(db, summary, language=language)
    return summary


def write_morning_brief(db: DB, summary: dict, language: str = "en") -> None:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    ready = db.list_jobs(state="ready")
    lines = [f"# Atlas — Resumen del {today}", ""]
    dt = summary.get("downtime_hours")
    if dt:
        lines += [
            f"> ⚠️ **Estuve sin correr ~{dt:.0f}h.** Revisa que tu equipo esté despierto y "
            "Claude Desktop abierto.",
            "",
        ]
    disc = summary.get("discover", {})
    lines += [
        f"**Nuevos:** {disc.get('new', 0)} · **Shortlist nueva:** {summary['shortlisted']} · "
        f"**Preparados hoy:** {len(summary['prepared'])} · **Listos en total:** {len(ready)}",
        "",
        "## ✅ Listos para enviar (revisa y envía tú)",
    ]
    for j in ready[:15]:
        refs = match_referrals(db, j.get("company", ""))
        ref = f" · 🤝 referido: {refs[0]['name']}" if refs else ""
        link = j.get("apply_url") or j.get("url") or "—"
        lines.append(
            f"- **{j['title']}** @ {j['company']} (fit {j.get('fit_score')}){ref}\n"
            f"  - Postular: {link}\n  - Paquete: data/outbox/{j['id']}/package.md"
        )
    top_learnings = [
        learning_row for learning_row in db.all_learnings() if learning_row["confidence"] >= 0.6
    ][:8]
    if top_learnings:
        lines += ["", "## 🧠 Lo aprendido (empresas)"]
        lines += [
            f"- **{learning_row['company']}**: {learning_row['observation']} "
            f"(confianza {learning_row['confidence']:.0%})"
            for learning_row in top_learnings
        ]
    if summary.get("prepare_errors"):
        lines += ["", "## ⚠️ Errores al preparar"]
        lines += [f"- {e['id']}: {e['error']}" for e in summary["prepare_errors"]]
    bad_pdfs = [c for c in summary.get("pdf_checks", []) if not c["ok"]]
    if bad_pdfs:
        lines += ["", "## ⚠︎ CVs que exceden el límite de páginas (arréglalos antes de enviar)"]
        lines += [f"- {c['job_id']}: {c['reason']}" for c in bad_pdfs]
    health = [h for h in db.latest_source_health() if not h["ok"]]
    if health:
        lines += ["", "## ⚠️ Fuentes con problemas"]
        lines += [f"- {h['source']}: {(h['error'] or '')[:80]}" for h in health]
    pend = summary.get("intents_pending") or []
    if pend:
        lines += ["", "## 🤖 Tareas del Brain en cola (pídele a Claude: `corre atlas`)"]
        lines += [
            f"- `{p['id']}` · {p['type']}" + (f" · job {p['job_id']}" if p["job_id"] else "")
            for p in pend
        ]
    stale = intent_queue.stale_intents(db)
    if stale:
        lines += ["", "## 🧟 Intents atascados (>48h sin drenar)"]
        lines += [f"- `{i['id']}` · {i['type']} · {i['age_hours']:.0f}h" for i in stale]
    flaky_sources = [s for s in classify_sources(db) if s["state"] in ("ok_empty", "unconfigured")]
    if flaky_sources:
        lines += ["", "## 🔎 Fuentes sospechosas (revisa credenciales/filtros)"]
        lines += [f"- {s['source']} ({s['state']}): {s['hint']}" for s in flaky_sources]
    enq = summary.get("enqueued_intents") or {}
    if any(enq.values()):
        parts = ", ".join(f"{v} {k}" for k, v in enq.items() if v)
        lines += ["", "## 🔬 Research nuevo", f"Encolado hoy para el brain: {parts}."]
    (paths.OUTBOX_DIR / "MORNING_BRIEF.md").write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description="Atlas daily brain (deterministic, sends nothing).")
    ap.add_argument("--limit", type=int, default=8, help="Max jobs to prepare this run.")
    ap.add_argument("--language", default="en", help="CV/outreach language: en | es")
    ap.add_argument(
        "--no-discover", action="store_true", help="Skip discovery (score/prepare only)."
    )
    ap.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    ap.add_argument(
        "--dry-run", action="store_true", help="Preview the pipeline without any writes."
    )
    args = ap.parse_args()
    with DB() as db:
        summary = run(
            db,
            limit=args.limit,
            language=args.language,
            do_discover=not args.no_discover,
            dry_run=args.dry_run,
        )
    if args.dry_run:
        print(
            json.dumps(summary, indent=2)
            if args.json
            else f"DRY RUN — would discover: {summary['would_discover']}, "
            f"would score: {summary['would_score']}, "
            f"would prep: {len(summary['would_prep'])} job(s), "
            f"pending intents: {summary['pending_intents']}"
        )
        return
    print(
        json.dumps(summary, indent=2)
        if args.json
        else f"Brain done — {summary['shortlisted']} shortlisted, "
        f"{len(summary['prepared'])} prepared, {summary['followups']} follow-ups. "
        f"Brief: {paths.OUTBOX_DIR / 'MORNING_BRIEF.md'}"
    )


if __name__ == "__main__":
    main()
