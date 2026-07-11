"""Atlas command-line interface.

`atlas <command>` — the deterministic engine the Cowork brain orchestrates, and the
commands you run by hand. Nothing here sends or submits anything.
"""

from __future__ import annotations

import os

import typer
from rich.console import Console
from rich.table import Table

import engine.paths as paths
from engine import __version__
from engine.config import load_master_cv
from engine.paths import REPO_ROOT

# Load .env (Adzuna keys etc.) without overriding a real shell env.
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:  # noqa: BLE001
    pass

app = typer.Typer(add_completion=False, help="Atlas — personal job-search cockpit (local, $0).")
console = Console()


@app.callback()
def _main(
    profile: str | None = typer.Option(
        None, "--profile", help="Profile (account) to act on. Default: the active profile."
    ),
) -> None:
    """Atlas — personal job-search cockpit (local, $0)."""
    if not profile:
        return
    from engine import profiles

    if not profiles.valid_id(profile):
        console.print(f"[red]✗[/] id de perfil inválido: {profile!r}")
        raise typer.Exit(2)
    # If profiles already exist, an unknown id is almost certainly a typo — don't silently
    # spawn a junk profile dir.
    if profiles.list_profiles() and not profiles.exists(profile):
        console.print(
            f"[red]✗[/] perfil desconocido: {profile!r}. "
            f"Créalo con `atlas profiles create {profile}`."
        )
        raise typer.Exit(2)
    os.environ["ATLAS_PROFILE"] = profile  # agree with any child process / re-import
    paths.set_profile(profile)


def _db():
    from engine.db.models import DB

    return DB()


def _warn_if_template_cv(console: Console) -> bool:
    """Print a prominent warning if the active master CV is still the seed template.

    Never blocks: only warns. Returns True iff a warning was printed (useful for
    `doctor`, which folds this into its report)."""
    from engine.cv.placeholder import find_placeholders

    try:
        cv = load_master_cv()
    except Exception:  # noqa: BLE001 — a broken/missing CV is not this helper's job
        return False
    findings = find_placeholders(cv)
    if findings:
        console.print(
            "[bold red]⚠ Tu master CV sigue siendo la PLANTILLA[/bold red] — "
            "nada de lo generado es enviable. Mapea profile/master_cv.draft.yaml y corre "
            "[bold]atlas cv promote[/bold]."
        )
        for f in findings:
            console.print(f"  [red]•[/red] {f}")
        return True
    return False


@app.command()
def version() -> None:
    """Print the Atlas version."""
    console.print(f"Atlas v{__version__}")


@app.command()
def doctor() -> None:
    """Check the environment + the three $0 safeguards."""
    console.rule("[bold]atlas doctor")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")

    ok = True
    if api_key:
        ok = False
        console.print(
            "[bold red]✗ ANTHROPIC_API_KEY is set[/] — `claude -p`/SDK would bill "
            "per-token to an API account. Unset it before scheduling the brain."
        )
    else:
        console.print("[green]✓[/] ANTHROPIC_API_KEY not set (good).")
    default_base = base_url in (None, "", "https://api.anthropic.com", "https://api.anthropic.com/")
    if base_url and not default_base:
        console.print(
            f"[yellow]![/] ANTHROPIC_BASE_URL is set to a non-default host ({base_url}). "
            "Confirm Claude Code `/status` shows your Max subscription, not API billing."
        )
    else:
        console.print("[green]✓[/] ANTHROPIC_BASE_URL is default/unset.")

    console.print(f"[green]✓[/] Active profile: {paths.PROFILE_ID or 'legacy'}")
    console.print(f"[green]✓[/] DB path: {paths.DB_PATH}")
    _warn_if_template_cv(console)
    console.print("\n[bold]Manual checklist for a true $0 guarantee:[/]")
    console.print(
        "  1. Run the brain as a Claude [bold]Cowork/Desktop scheduled task[/] (never `claude -p`)."
    )
    console.print(
        "  2. [bold]Disable usage credits / overage billing[/] in your Claude account "
        "→ the system fails closed."
    )
    console.print(
        "  3. In Claude Desktop, enable [bold]Keep computer awake[/] and keep the app open."
    )
    raise typer.Exit(0 if ok else 1)


@app.command()
def discover(
    only: str | None = typer.Option(
        None, help="Comma list to limit sources: ats,jobspy,indeed,linkedin,himalayas,adzuna"
    ),
) -> None:
    """Pull jobs from all enabled sources into the database (idempotent)."""
    from engine.discovery.runner import discover as run_discover

    only_set = {s.strip() for s in only.split(",")} if only else None
    with _db() as db:
        summary = run_discover(db, only=only_set)

    table = Table(title="Discovery", show_lines=False)
    for col in ("source", "ok", "fetched", "new", "seen", "ms"):
        table.add_column(col)
    for label, s in sorted(summary["sources"].items()):
        table.add_row(
            label,
            "✓" if s["ok"] else "[red]✗[/]",
            str(s["fetched"]),
            f"[green]{s['new']}[/]",
            str(s["seen"]),
            str(s["ms"]),
        )
    console.print(table)
    console.print(
        f"[bold]Total:[/] {summary['new']} new, {summary['seen']} seen, "
        f"{summary['fetched']} fetched"
    )
    if summary["errors"]:
        console.print("[yellow]Source issues:[/] " + "; ".join(summary["errors"]))


@app.command()
def score(
    rescore: bool = typer.Option(False, help="Re-score every job, not just newly discovered ones."),
) -> None:
    """Score fit for discovered jobs; shortlist those above the threshold."""
    from engine.config import load_criteria
    from engine.scoring.run import score_jobs

    criteria = load_criteria()
    with _db() as db:
        scored, shortlisted = score_jobs(db, criteria, rescore=rescore)
    console.print(
        f"Scored [bold]{scored}[/], shortlisted [green]{shortlisted}[/] "
        f"(threshold {criteria.shortlist_threshold})."
    )


@app.command()
def top(
    n: int = typer.Option(15, help="How many to show."),
    state: str = typer.Option("shortlisted", help="Pipeline state to list."),
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show every posting, including near-identical reposts (skip variant collapsing).",
    ),
) -> None:
    """List the highest-fit jobs in a given state.

    By default, near-identical reposts of the same role (same company + core title — the
    5-CVS-Health-postings problem) collapse into a single row tagged '×N'; pass --all to see
    every variant.
    """
    from engine.scoring.priority import priority as blended_priority

    with _db() as db:
        if show_all:
            pool = db.list_jobs(state=state)
        else:
            from engine.scoring.dedupe import collapse_variants

            # Collapse needs the full pool BEFORE truncating to n, else a repost cluster could
            # eat all n slots and hide other jobs that would otherwise make the cut.
            pool = collapse_variants(db.list_jobs(state=state))
        # Collapse (or not) first, THEN sort by blended priority, THEN take the top n — sorting
        # before truncating so a high-match/lower-fit job doesn't get cut by a raw-fit ordering.
        jobs = sorted(
            pool,
            key=lambda j: blended_priority(j.get("fit_score"), j.get("match_score")),
            reverse=True,
        )[:n]
    table = Table(title=f"Top {state}" + ("" if show_all else "  (variantes colapsadas)"))
    for col in ("PRIORIDAD", "FIT (criterios)", "CV MATCH (keywords)", "title", "company", "remote", "id"):
        table.add_column(col)
    for j in jobs:
        rem = {1: "✓", 0: "✗"}.get(j["is_remote"], "?")
        match = j.get("match_score")
        title = (j["title"] or "")[:42]
        variant_count = j.get("variant_count") or 1
        if variant_count > 1:
            title = f"{title} [dim]×{variant_count}[/]"
        table.add_row(
            str(blended_priority(j.get("fit_score"), j.get("match_score"))),
            str(j.get("fit_score")),
            f"{match}%" if match is not None else "—",
            title,
            (j["company"] or "")[:22],
            rem,
            j["id"],
        )
    console.print(table)
    console.print(
        "[dim]fit = encaje con tus criterios · CV match = cobertura de keywords de la "
        "vacante en tu CV · prioridad = 0.7·fit + 0.3·match[/]"
    )


@app.command()
def tailor(
    job_id: str,
    language: str | None = typer.Option(None, help="CV language: en | es (def: idioma del perfil)"),
    pdf: bool = typer.Option(True, help="Also render a PDF (native, via reportlab)."),
) -> None:
    """Generate a parse-safe, JD-tailored CV for a job (DOCX + optional PDF)."""
    from engine.config import load_ontology
    from engine.cv.build import build_for_job
    from engine.cv.match import match_score
    from engine.cv.review_report import build_review

    _warn_if_template_cv(console)
    with _db() as db:
        res = build_for_job(db, job_id, language=language, make_pdf=pdf)
        job = db.get_job(job_id) or {}
    master = load_master_cv()
    m = match_score(job, master, load_ontology())
    console.print(f"[bold]CV built[/] for {job_id}  (ATS: {res.ats_target})")
    console.print(f"  DOCX: {res.docx_path}")
    console.print(f"  PDF:  {res.pdf_path or '[yellow]not generated[/]'}")
    console.print(
        f"  Keyword coverage: [bold]{res.coverage:.0%}[/]  "
        f"({len(res.matched)} matched, {len(res.missing)} missing)"
    )
    console.print(f"  CV↔JD match: [bold]{m.score}/100[/] (distinto del fit puesto↔criterios)")
    parse = "[green]✓ parse-safe[/]" if res.parse_ok else f"[red]✗ {res.parse_issues}[/]"
    console.print(f"  Parse check: {parse}")
    if res.missing:
        console.print(
            f"  [yellow]Missing JD keywords[/] (add only if true): {', '.join(res.missing[:10])}"
        )
    coverage = {"coverage": res.coverage, "matched": res.matched, "missing": res.missing}
    review = build_review(res.docx_path, res.pdf_path, master, job, coverage)
    (res.docx_path.parent / "review.md").write_text(review.markdown)
    console.print("  Revisión determinista:")
    for c in review.checks:
        console.print(f"    {'✅' if c.ok else '⚠️ '} {c.name}: {c.detail}")


@app.command(name="import-cv")
def import_cv(
    path: str,
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing master_cv.draft.yaml."
    ),
) -> None:
    """Extract an existing CV (PDF/DOCX) into a reviewable master_cv DRAFT.

    Deterministic text extraction only — never invents structure and NEVER touches your
    master_cv.yaml. Next step: ask Claude (Cowork) to map the draft into the schema, review it,
    then save it as master_cv.yaml yourself.
    """
    from pathlib import Path

    from engine.cv.import_cv import build_draft, extract_text

    src = Path(path).expanduser()
    if not src.exists():
        console.print(f"[red]File not found:[/] {src}")
        raise typer.Exit(1)
    try:
        text = extract_text(src)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from e
    if not text.strip():
        console.print(
            "[yellow]No text extracted[/] (scanned/image-only PDF?). Try a text-based file."
        )
        raise typer.Exit(1)

    draft_path = (
        paths.MASTER_CV_PATH.parent / "master_cv.draft.yaml"
    )  # late-path-read (per profile)
    if draft_path.exists() and not force:
        console.print(
            f"[yellow]Draft already exists:[/] {draft_path}\n  Re-run with --force to overwrite."
        )
        raise typer.Exit(1)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    from engine import profiles

    draft_path.write_text(build_draft(text, domain=profiles.domain_of(paths.PROFILE_ID)))
    console.print(f"[green]✓[/] Draft written: {draft_path}")
    console.print(
        "  Next: ask Claude (Cowork) to map `_source_text` into the schema, review, then save as master_cv.yaml."
    )
    console.print("  [dim]Your existing master_cv.yaml was NOT touched.[/]")


@app.command()
def outreach(
    job_id: str,
    language: str | None = typer.Option(None, help="en | es (def: idioma del perfil)"),
) -> None:
    """Draft all outreach variants for a job (cover/recruiter/HM/referral/cold/note)."""
    from engine.outreach.build import build_outreach

    with _db() as db:
        drafts = build_outreach(db, job_id, language=language)
    console.print(f"Drafted [green]{len(drafts)}[/] messages for {job_id}:")
    for d in drafts:
        console.print(f"  • {d.kind} ({d.channel})")


@app.command()
def prep(
    job_id: str,
    language: str | None = typer.Option(None, help="en | es (def: idioma del perfil)"),
) -> None:
    """Full prep for one job: tailor CV → draft outreach → write the send-ready package."""
    from engine.cv.build import build_for_job
    from engine.cv.review_report import build_review
    from engine.outreach.build import build_outreach, write_package

    _warn_if_template_cv(console)
    master = load_master_cv()
    with _db() as db:
        cv = build_for_job(db, job_id, language=language)
        build_outreach(db, job_id, language=language)
        pkg = write_package(db, job_id, language=language)
        job = db.get_job(job_id) or {}
    console.print(f"[bold green]Ready[/]: {job_id}")
    console.print(f"  Coverage {cv.coverage:.0%} · parse {'✓' if cv.parse_ok else '✗'}")
    console.print(f"  Package: {pkg}")
    coverage = {"coverage": cv.coverage, "matched": cv.matched, "missing": cv.missing}
    review = build_review(cv.docx_path, cv.pdf_path, master, job, coverage)
    (cv.docx_path.parent / "review.md").write_text(review.markdown)
    console.print("  Revisión determinista:")
    for c in review.checks:
        console.print(f"    {'✅' if c.ok else '⚠️ '} {c.name}: {c.detail}")


@app.command(name="import-connections")
def import_connections(csv_path: str) -> None:
    """Import a LinkedIn Connections.csv export to power referral detection."""
    from pathlib import Path

    from engine.referrals.connections import import_connections_csv

    with _db() as db:
        n = import_connections_csv(db, Path(csv_path))
    console.print(f"Imported [green]{n}[/] connections.")


@app.command()
def referrals() -> None:
    """Show shortlisted jobs where you have a 1st-degree connection at the company."""
    from engine.referrals.connections import match_referrals

    with _db() as db:
        jobs = db.list_jobs(states=["shortlisted", "tailored", "drafted", "ready"])
        rows = [(j, match_referrals(db, j.get("company", ""))) for j in jobs]
    rows = [(j, r) for j, r in rows if r]
    if not rows:
        console.print("No referral matches yet. Import your Connections.csv first.")
        return
    table = Table(title="Referral opportunities")
    for col in ("company", "role", "connection", "title"):
        table.add_column(col)
    for j, r in rows:
        c = r[0]
        table.add_row(j["company"], (j["title"] or "")[:32], c["name"], (c.get("title") or "")[:30])
    console.print(table)


@app.command()
def brain(
    limit: int = typer.Option(8, help="Max jobs to fully prepare this run."),
    language: str | None = typer.Option(None, help="CV/outreach language: en | es (def: perfil)"),
    discover: bool = typer.Option(True, help="Run discovery first."),
    json_out: bool = typer.Option(
        False, "--json", help="Emit the run summary as JSON (for the orchestrator)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the pipeline without any writes."
    ),
) -> None:
    """Run the full daily pipeline: discover → score → prepare → brief. Sends nothing."""
    import sys

    from engine import profiles

    # The auto-run is the owner's, on the owner's Claude subscription. Refuse to run it for
    # another profile so a stray `--profile alex brain` can't burn the owner's budget.
    if not profiles.is_owner(paths.PROFILE_ID):
        console.print(
            "[red]✗[/] El brain (auto-run) solo corre para el perfil del dueño. "
            f"Activo: {paths.PROFILE_ID}. Usa `atlas --profile owner brain`."
        )
        raise typer.Exit(1)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from brain.run_brain import run

    with _db() as db:
        s = run(db, limit=limit, language=language, do_discover=discover, dry_run=dry_run)
    if json_out:
        import json as _json

        print(_json.dumps(s, indent=2, ensure_ascii=False))
        return
    if dry_run:
        console.print(
            f"[bold cyan]DRY RUN[/] — would discover: {s['would_discover']}, "
            f"would score: {s['would_score']}, would prep: {len(s['would_prep'])} job(s), "
            f"pending intents: {s['pending_intents']}"
        )
        for j in s["would_prep"]:
            tag = "already prepared" if j["already_prepared"] else "pending"
            console.print(f"  - {j['title']} @ {j['company']} ({tag})")
        return
    console.print(
        f"[bold green]Brain done[/] — new {s['discover'].get('new', 0)}, "
        f"shortlisted {s['shortlisted']}, prepared {len(s['prepared'])}, "
        f"follow-ups {s['followups']}."
    )
    if s.get("downtime_hours"):
        console.print(f"[yellow]⚠️ Was down ~{s['downtime_hours']:.0f}h[/] before this run.")
    console.print(f"Morning brief: {paths.OUTBOX_DIR / 'MORNING_BRIEF.md'}")


@app.command()
def advise(json_out: bool = typer.Option(False, "--json", help="Emit findings as JSON.")) -> None:
    """Audit your master CV against best practices (feeds the cv-linkedin-advisor guide)."""
    import json as _json

    from engine.advisor import audit_dict
    from engine.config import load_master_cv

    result = audit_dict(load_master_cv())
    if json_out:
        print(_json.dumps(result, indent=2, ensure_ascii=False))
        return
    s = result["summary"]
    console.print(
        f"[bold]Auditoría del CV[/] — {s['high']} altas · {s['med']} medias · {s['low']} bajas"
    )
    colors = {"high": "red", "med": "yellow", "low": "cyan"}
    for x in result["findings"]:
        console.print(f"  [{colors[x['severity']]}]●[/] [{x['area']}] {x['message']}")
        console.print(f"     → {x['suggestion']}")
    console.print(
        "\nPara la mejora completa (CV + LinkedIn, según tu rol objetivo), usa la guía "
        "[bold]cv-linkedin-advisor[/] (advisor/cv_linkedin_advisor.md)."
    )


_STATE_STYLE = {
    "ok": "[green]{}[/]",
    "ok_empty": "[yellow]{}[/]",
    "unconfigured": "[dim]{}[/]",
    "error": "[red]{}[/]",
}


@app.command()
def status() -> None:
    """Show pipeline counts and the latest health of each source."""
    from engine import intents as eng_intents
    from engine.discovery.health import classify_sources

    with _db() as db:
        counts = db.counts_by_state()
        health = db.latest_source_health()
        classified = {c["source"]: c for c in classify_sources(db)}
        last_run = db.meta_get("last_run")
        stale = eng_intents.stale_intents(db)
        last_sweep = db.last_liveness_sweep()
    console.print(f"[bold]Pipeline[/] (last run: {last_run or 'never'})")
    for state, n in counts.items():
        console.print(f"  {state:<12} {n}")
    console.print(
        f"[bold]Liveness:[/] último sweep {(last_sweep or 'nunca')[:19]} · "
        f"{counts.get('expired', 0)} expirados"
    )
    if health:
        table = Table(title="Source health")
        for col in ("source", "ok", "count", "when", "state", "hint/error"):
            table.add_column(col)
        for h in health:
            c = classified.get(h["source"], {})
            state_label = _STATE_STYLE.get(c.get("state"), "{}").format(c.get("state", ""))
            hint = c.get("hint") or (h["error"] or "")[:40]
            table.add_row(
                h["source"],
                "✓" if h["ok"] else "[red]✗[/]",
                str(h["count"]),
                (h["run_at"] or "")[:19],
                state_label,
                hint[:60],
            )
        console.print(table)
    if stale:
        console.print(f"[yellow]⚠ {len(stale)} intent(s) atascados >48h[/]")


@app.command(name="export")
def export_csv(
    state: str | None = typer.Option(None, help="Limit to a pipeline state (e.g. shortlisted)."),
    columns: str | None = typer.Option(None, help="Comma list of column ids (else saved/default)."),
    to: str | None = typer.Option(
        None, "--to", help="Output dir (else your download_dir setting, else the outbox)."
    ),
) -> None:
    """Export jobs to CSV using your editable template, into your chosen folder."""
    from datetime import UTC, datetime
    from pathlib import Path

    from engine import export as exp

    requested = [c.strip() for c in columns.split(",") if c.strip()] if columns else None
    with _db() as db:
        cols = exp.resolve_columns(requested, db.meta_get("csv_columns"))
        jobs = db.list_jobs(state=state, limit=5000)
        dest_raw = to or db.meta_get("download_dir") or str(paths.OUTBOX_DIR)
        text = exp.generate_csv(jobs, cols)
    dest = Path(exp.validate_download_dir(dest_raw))
    out = dest / f"atlas_jobs_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    out.write_text(text, encoding="utf-8")
    console.print(f"[green]✓[/] Exporté {len(jobs)} filas → {out}")


@app.command()
def outcome(
    job_id: str = typer.Argument(..., help="Job id the outcome is for."),
    state: str = typer.Option(..., help="rejected | responded | interviewed | offer | ghosted"),
    response_days: int | None = typer.Option(None, help="Days until they responded."),
    interviews: int = typer.Option(0, help="How many interview rounds happened."),
    recruiter_source: str | None = typer.Option(
        None, help="referral | recruiter | cold | inbound | unknown"
    ),
    reason: str | None = typer.Option(None, help="Short reason / feedback."),
) -> None:
    """Record a CONFIRMED application outcome and refresh this company's learnings (P2-D)."""
    from engine.learning.runner import auto_learn

    with _db() as db:
        job = db.get_job(job_id)
        if not job:
            console.print(f"[red]✗[/] job desconocido: {job_id}")
            raise typer.Exit(2)
        db.record_outcome(
            job_id,
            job.get("company", ""),
            final_state=state,
            response_days=response_days,
            interview_count=interviews,
            offer_made=(state == "offer"),
            recruiter_source=recruiter_source,
            reason=reason,
        )
        n = auto_learn(db, job.get("company", ""))
    console.print(f"[green]✓[/] Outcome registrado para {job.get('company')}. Learnings: {n}.")


@app.command(name="resolve-ats")
def resolve_ats(url: str) -> None:
    """Detect which ATS a company careers URL uses (for companies.yaml)."""
    from engine.discovery.registry import resolve_ats as resolve

    result = resolve(url)
    console.print(result or "[yellow]No known ATS detected[/]")


# ── profiles (accounts) ───────────────────────────────────────────────────────
profiles_app = typer.Typer(help="Manage Atlas profiles (accounts) — local, no password.")
app.add_typer(profiles_app, name="profiles")


@profiles_app.command("init")
def profiles_init() -> None:
    """One-time migration of your current data into the 'owner' profile (idempotent)."""
    from engine import profiles

    res = profiles.init_owner()
    if res["migrated"]:
        console.print(f"[green]✓[/] Migrado a perfil [bold]owner[/] → {res['root']}")
    else:
        console.print("[dim]El perfil owner ya existe; nada que migrar.[/]")
    console.print(f"Perfiles: {', '.join(p['id'] for p in profiles.list_profiles())}")


@profiles_app.command("create")
def profiles_create(
    profile_id: str = typer.Argument(..., help="id corto: minúsculas, dígitos, '-' o '_'."),
    label: str | None = typer.Option(None, "--label", help="Nombre visible en el selector."),
    domain: str = typer.Option(
        "data", "--domain", help="Industria/dominio del perfil (selecciona su seed pack)."
    ),
) -> None:
    """Create a new profile seeded from the templates for its domain, ready to edit."""
    from engine import profiles

    try:
        res = profiles.create_profile(profile_id, label, domain=domain)
    except ValueError as e:
        console.print(f"[red]✗[/] {e}")
        raise typer.Exit(2) from None
    verb = "Creado" if res["created"] else "Ya existía"
    console.print(
        f"[green]✓[/] {verb} perfil [bold]{profile_id}[/] [dim]({res['domain']})[/] → {res['root']}"
    )
    console.print(
        f"  Edita: profiles/{profile_id}/config/criteria.md · "
        f"profiles/{profile_id}/profile/master_cv.yaml"
    )


@profiles_app.command("list")
def profiles_list() -> None:
    """List profiles and show which one is active."""
    from engine import profiles

    active = profiles.get_active()
    rows = profiles.list_profiles()
    if not rows:
        console.print("Sin perfiles todavía. Corre `atlas profiles init`.")
        return
    for p in rows:
        mark = "[green]●[/]" if p["id"] == active else " "
        owner = " [dim](dueño)[/]" if p.get("is_owner") else ""
        dom = f" [dim]· {p.get('domain', 'data')}[/]"
        console.print(f"  {mark} [bold]{p['id']}[/]{owner} — {p.get('label', '')}{dom}")


# ── interviews (P3-E) — manual entry + prep-doc generation ─────────────────────
interview_app = typer.Typer(help="Manage interviews + generate prep docs (manual entry).")
app.add_typer(interview_app, name="interview")


@interview_app.command("add")
def interview_add(
    job_id: str,
    scheduled_at: str = typer.Argument(None, help="When (YYYY-MM-DD or ISO)."),
    round: str = typer.Option(
        None, "--round", help="phone|technical|system_design|hiring_manager|final"
    ),
    mode: str = typer.Option(None, help="video|onsite|phone"),
) -> None:
    """Add an interview for a job (manual)."""
    with _db() as db:
        if not db.get_job(job_id):
            console.print(f"[red]✗[/] job desconocido: {job_id}")
            raise typer.Exit(2)
        iid = db.add_interview(job_id, scheduled_at=scheduled_at, round=round, mode=mode)
    console.print(
        f"[green]✓[/] entrevista {iid} para {job_id}. Agrega entrevistadores en el dashboard."
    )


@interview_app.command("list")
def interview_list() -> None:
    """List scheduled interviews."""
    with _db() as db:
        rows = db.list_interviews()
        jobs = {j["id"]: j for j in db.list_jobs()}
    if not rows:
        console.print("Sin entrevistas. Agrega una con `atlas interview add <job_id>`.")
        return
    table = Table(title="Interviews")
    for col in ("id", "when", "round", "company", "prep"):
        table.add_column(col)
    for r in rows:
        job = jobs.get(r["job_id"], {})
        table.add_row(
            str(r["id"]),
            (r.get("scheduled_at") or "—")[:16],
            r.get("round") or "—",
            (job.get("company") or "—")[:24],
            "✓" if r.get("prep_path") else "—",
        )
    console.print(table)


@interview_app.command("prep")
def interview_prep(
    interview_id: int,
    language: str | None = typer.Option(None, help="en | es (def: idioma del perfil)"),
) -> None:
    """Generate the prep doc (likely questions + STAR scaffolds) for an interview."""
    from engine.interview.interview_prep import gen_prep_doc

    with _db() as db:
        path = gen_prep_doc(db, interview_id, language=language)
    console.print(f"[green]✓[/] Prep generado → {path}")


# ── portfolio (P3-F) — local generation + peer references ──────────────────────
portfolio_app = typer.Typer(help="Generate a local portfolio site + manage peer references.")
app.add_typer(portfolio_app, name="portfolio")


@portfolio_app.command("generate")
def portfolio_generate(
    github: bool = typer.Option(False, "--github", help="Include public GitHub repos."),
) -> None:
    """Render your master_cv.yaml into a standalone local portfolio (never published)."""
    from datetime import UTC, datetime

    from engine.portfolio.builder import generate_portfolio

    _warn_if_template_cv(console)
    version = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    with _db() as db:
        path = generate_portfolio(load_master_cv(), version=version, include_github=github)
        db.add_portfolio(version=version, path_html=str(path))
    console.print(f"[green]✓[/] Portafolio → {path}")
    console.print("[dim]Local y privado. Ábrelo con `atlas portfolio open`.[/]")


@portfolio_app.command("list")
def portfolio_list() -> None:
    """List generated portfolio versions."""
    with _db() as db:
        rows = db.list_portfolios()
    if not rows:
        console.print("Sin portafolios. Corre `atlas portfolio generate`.")
        return
    for r in rows:
        console.print(f"  [bold]{r['version']}[/] → {r['path_html']}")


@portfolio_app.command("open")
def portfolio_open() -> None:
    """Open the latest portfolio in your browser (local file)."""
    import subprocess

    with _db() as db:
        p = db.latest_portfolio()
    if not p:
        console.print("Sin portafolios. Corre `atlas portfolio generate`.")
        raise typer.Exit(1)
    subprocess.run(["open", p["path_html"]], check=False)  # noqa: S607 — local macOS open
    console.print(f"Abriendo {p['path_html']}")


@portfolio_app.command("research")
def portfolio_research(
    enqueue: bool = typer.Option(
        False, "--enqueue", help="Encola el intent portfolio_research (el brain investiga peers vivos)."
    ),
) -> None:
    """Muestra las referencias curadas + los peers descubiertos (con fecha de research)."""
    from engine import intents as eng_intents
    from engine.portfolio.peer_examples import load_references
    from engine.profiles import domain_of

    if enqueue:
        with _db() as db:
            iid = eng_intents.enqueue(db, "portfolio_research", {})
        console.print(
            f"[green]✓[/] Intent {iid} encolado. El brain lo drena en el próximo `corre atlas`."
        )
        return

    with _db() as db:
        domain = domain_of(paths.PROFILE_ID)
        references = load_references(domain)
        peers = db.list_peer_portfolios()

    console.print(f"[bold]Referencias curadas[/] ({domain})")
    if not references["examples"]:
        console.print("  (sin referencias curadas para este dominio)")
    for ex in references["examples"]:
        console.print(f"  • {ex.get('peer_name', '—')} — {ex.get('url', '—')}")

    console.print("\n[bold]Peers descubiertos (research vivo)[/]")
    if not peers:
        console.print("  Ninguno todavía. Corre `atlas portfolio research --enqueue`.")
        return
    table = Table()
    for col in ("peer_name", "role_match", "reviewed_at"):
        table.add_column(col)
    for p in peers:
        table.add_row(
            p.get("peer_name") or "—",
            (p.get("role_match") or "—")[:40],
            (p.get("reviewed_at") or "—")[:16],
        )
    console.print(table)


# ── intents (F4) — la cola que el brain drena como paso 0 de "corre atlas" ─────
intents_app = typer.Typer(help="Cola de intents (handoff web → brain). El brain la drena.")
app.add_typer(intents_app, name="intents")


@intents_app.command("list")
def intents_list(
    status: str = typer.Option("pending", help="pending|running|done|error|all"),
    json_out: bool = typer.Option(False, "--json", help="JSON para el brain."),
) -> None:
    """List queued intents (the brain drains these as step 0)."""
    import json as _json

    from engine import intents as eng_intents

    with _db() as db:
        rows = eng_intents.list_intents(db, status=None if status == "all" else status)
    if json_out:
        print(_json.dumps(rows, indent=2, ensure_ascii=False))
        return
    table = Table(title=f"Intents ({status})")
    for col in ("id", "type", "job", "status", "edad", "created", "result/error"):
        table.add_column(col)
    for r in rows:
        age = r.get("age_hours")
        edad = f"{age}h" if age is not None else "—"
        if r.get("is_stale"):
            edad = f"[red]{edad}[/]"
        table.add_row(
            r["id"],
            r["type"],
            (r.get("job_id") or "—")[:18],
            r["status"],
            edad,
            (r.get("created_at") or "")[:16],
            (r.get("result_ref") or r.get("error") or "")[:30],
        )
    console.print(table)


@intents_app.command("start")
def intents_start(intent_id: str) -> None:
    """Mark an intent running and print which prompt file drives it."""
    from engine import intents as eng_intents

    with _db() as db:
        try:
            eng_intents.mark_running(db, intent_id)
            row = eng_intents.get_intent(db, intent_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    console.print(
        f"[green]✓[/] {intent_id} → running. Prompt: "
        f"brain/prompts/{eng_intents.PROMPT_FILES[row['type']]}"
    )


@intents_app.command("context")
def intents_context(intent_id: str) -> None:
    """Print the deterministic context JSON the brain needs for this intent."""
    import json as _json

    from engine import intents as eng_intents

    with _db() as db:
        try:
            ctx = eng_intents.context_for(db, intent_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    print(_json.dumps(ctx, indent=2, ensure_ascii=False))


@intents_app.command("complete")
def intents_complete(
    intent_id: str,
    result_file: str = typer.Option(..., "--result-file", help="JSON con el resultado."),
) -> None:
    """Validate the brain's result JSON and write it to the destination tables."""
    import json as _json
    from pathlib import Path

    from engine import intents as eng_intents

    p = Path(result_file).expanduser()
    if not p.exists():
        console.print(f"[red]✗[/] no existe: {p}")
        raise typer.Exit(2)
    try:
        result = _json.loads(p.read_text())
    except _json.JSONDecodeError as e:
        console.print(f"[red]✗ JSON inválido:[/] {e}")
        raise typer.Exit(2) from None
    with _db() as db:
        try:
            ref = eng_intents.apply_result(db, intent_id, result)
        except ValueError as e:
            console.print(
                f"[red]✗ resultado rechazado:[/] {e}\n"
                "  (el intent sigue running — corrige el JSON y reintenta)"
            )
            raise typer.Exit(2) from None
    console.print(f"[green]✓[/] {intent_id} → done ({ref})")


@intents_app.command("fail")
def intents_fail(
    intent_id: str,
    error: str = typer.Option(..., "--error", help="Por qué no se pudo ejecutar."),
) -> None:
    """Mark an intent as errored (visible in the web panel)."""
    from engine import intents as eng_intents

    with _db() as db:
        try:
            eng_intents.mark_error(db, intent_id, error)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    console.print(f"[yellow]![/] {intent_id} → error registrado")


@intents_app.command("requeue")
def intents_requeue(intent_id: str) -> None:
    """Re-enqueue a stuck (error/running) intent as pending — desatasca la cola."""
    from engine import intents as eng_intents

    with _db() as db:
        try:
            eng_intents.requeue(db, intent_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(1) from None
    console.print(f"[green]✓[/] {intent_id} → pending (requeued)")


# ── cv — utilidades de CV para el brain ────────────────────────────────────────
cv_app = typer.Typer(help="Utilidades de CV para el brain.")
app.add_typer(cv_app, name="cv")


@cv_app.command("dump")
def cv_dump(job_id: str) -> None:
    """Dump the tailored CV YAML for a job (input for the LLM reviewer / PDF fixes)."""
    from engine.cv.review import dump_tailored_cv

    with _db() as db:
        try:
            path = dump_tailored_cv(db, job_id)
        except ValueError as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(2) from None
    console.print(f"[green]✓[/] {path}")


@cv_app.command("promote")
def cv_promote() -> None:
    """Valida el draft y lo promueve a master (con backup)."""
    from engine.cv.promote import PromoteError, promote_draft

    try:
        out = promote_draft(paths.PROFILE_ROOT)
    except PromoteError as e:
        console.print(f"[red]✗[/] {e}")
        raise typer.Exit(1) from None
    console.print(f"[green]✓[/] Master CV promovido: {out}")


if __name__ == "__main__":
    app()
