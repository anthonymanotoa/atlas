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
from datetime import datetime, timezone

from engine import heartbeat
from engine.config import load_criteria, load_master_cv
from engine.cv.build import build_for_job
from engine.db.models import DB
from engine.discovery.runner import discover
from engine.normalize import now_iso
from engine.outreach.build import build_outreach, write_package
from engine.outreach.followups import followup_text
from engine.paths import OUTBOX_DIR
from engine.referrals.connections import match_referrals
from engine.scoring.run import score_jobs


def run(db: DB, *, limit: int = 8, language: str = "en", do_discover: bool = True) -> dict:
    summary: dict = {"discover": {}, "scored": 0, "shortlisted": 0,
                     "prepared": [], "prepare_errors": [], "followups": 0,
                     "downtime_hours": None}

    if do_discover:
        summary["discover"] = {k: v for k, v in discover(db).items() if k != "sources"}

    criteria = load_criteria()
    scored, shortlisted = score_jobs(db, criteria)
    summary["scored"], summary["shortlisted"] = scored, shortlisted

    # Prepare the top shortlisted jobs not yet prepared.
    for j in db.list_jobs(state="shortlisted", limit=limit):
        try:
            cv = build_for_job(db, j["id"], language=language)
            build_outreach(db, j["id"], language=language)
            write_package(db, j["id"], language=language)
            summary["prepared"].append({"id": j["id"], "title": j["title"],
                                        "company": j["company"], "coverage": cv.coverage})
        except Exception as e:  # noqa: BLE001 — one job must not break the batch
            summary["prepare_errors"].append({"id": j["id"], "error": str(e)[:200]})
            db.log_event(j["id"], "error", {"stage": "prepare", "error": str(e)[:200]})

    # Due follow-ups → draft (never send), then mark done.
    candidate = {"name": (load_master_cv().get("basics", {}) or {}).get("name", "")}
    for f in db.due_followups(now_iso()):
        job = db.get_job(f["job_id"])
        if not job:
            db.mark_followup(f["id"], "cancelled")
            continue
        d = followup_text(job, candidate, f["touch_number"], language)
        # Dedup per (job, kind, variant): touches 1-3 share kind 'follow_up' but differ by
        # variant 'touchN', so guarding on kind alone would drop touches 2 and 3.
        if not db.has_message(f["job_id"], d.kind, variant=d.variant):
            db.add_message(f["job_id"], channel=d.channel, kind=d.kind, body=d.body,
                           subject=d.subject, variant=d.variant, language=d.language, state="draft")
        db.mark_followup(f["id"], "done")
        summary["followups"] += 1

    summary["downtime_hours"] = heartbeat.downtime_hours(db)
    heartbeat.beat(db)
    db.log_event(None, "note", {"brain_run": True, **{k: summary[k] for k in
                 ("scored", "shortlisted", "followups")}})
    write_morning_brief(db, summary, language=language)
    return summary


def write_morning_brief(db: DB, summary: dict, language: str = "en") -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ready = db.list_jobs(state="ready")
    lines = [f"# Atlas — Resumen del {today}", ""]
    dt = summary.get("downtime_hours")
    if dt:
        lines += [f"> ⚠️ **Estuve sin correr ~{dt:.0f}h.** Revisa que el Mac esté despierto y "
                  "Claude Desktop abierto.", ""]
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
        lines.append(f"- **{j['title']}** @ {j['company']} (fit {j.get('fit_score')}){ref}\n"
                     f"  - Postular: {link}\n  - Paquete: data/outbox/{j['id']}/package.md")
    if summary.get("prepare_errors"):
        lines += ["", "## ⚠️ Errores al preparar"]
        lines += [f"- {e['id']}: {e['error']}" for e in summary["prepare_errors"]]
    health = [h for h in db.latest_source_health() if not h["ok"]]
    if health:
        lines += ["", "## ⚠️ Fuentes con problemas"]
        lines += [f"- {h['source']}: {(h['error'] or '')[:80]}" for h in health]
    (OUTBOX_DIR / "MORNING_BRIEF.md").write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description="Atlas daily brain (deterministic, sends nothing).")
    ap.add_argument("--limit", type=int, default=8, help="Max jobs to prepare this run.")
    ap.add_argument("--language", default="en", help="CV/outreach language: en | es")
    ap.add_argument("--no-discover", action="store_true", help="Skip discovery (score/prepare only).")
    ap.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    args = ap.parse_args()
    with DB() as db:
        summary = run(db, limit=args.limit, language=args.language, do_discover=not args.no_discover)
    print(json.dumps(summary, indent=2) if args.json else
          f"Brain done — {summary['shortlisted']} shortlisted, "
          f"{len(summary['prepared'])} prepared, {summary['followups']} follow-ups. "
          f"Brief: {OUTBOX_DIR / 'MORNING_BRIEF.md'}")


if __name__ == "__main__":
    main()
