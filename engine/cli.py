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
) -> None:
    """List the highest-fit jobs in a given state."""
    with _db() as db:
        jobs = db.list_jobs(state=state, limit=n)
    table = Table(title=f"Top {state}")
    for col in ("score", "title", "company", "remote", "id"):
        table.add_column(col)
    for j in jobs:
        rem = {1: "✓", 0: "✗"}.get(j["is_remote"], "?")
        table.add_row(
            str(j.get("fit_score")),
            (j["title"] or "")[:42],
            (j["company"] or "")[:22],
            rem,
            j["id"],
        )
    console.print(table)


@app.command()
def tailor(
    job_id: str,
    language: str = typer.Option("en", help="CV language: en | es"),
    pdf: bool = typer.Option(True, help="Also render a PDF (native, via reportlab)."),
) -> None:
    """Generate a parse-safe, JD-tailored CV for a job (DOCX + optional PDF)."""
    from engine.cv.build import build_for_job

    with _db() as db:
        res = build_for_job(db, job_id, language=language, make_pdf=pdf)
    console.print(f"[bold]CV built[/] for {job_id}  (ATS: {res.ats_target})")
    console.print(f"  DOCX: {res.docx_path}")
    console.print(f"  PDF:  {res.pdf_path or '[yellow]not generated[/]'}")
    console.print(
        f"  Keyword coverage: [bold]{res.coverage:.0%}[/]  "
        f"({len(res.matched)} matched, {len(res.missing)} missing)"
    )
    parse = "[green]✓ parse-safe[/]" if res.parse_ok else f"[red]✗ {res.parse_issues}[/]"
    console.print(f"  Parse check: {parse}")
    if res.missing:
        console.print(
            f"  [yellow]Missing JD keywords[/] (add only if true): {', '.join(res.missing[:10])}"
        )


@app.command()
def outreach(job_id: str, language: str = typer.Option("en", help="en | es")) -> None:
    """Draft all outreach variants for a job (cover/recruiter/HM/referral/cold/note)."""
    from engine.outreach.build import build_outreach

    with _db() as db:
        drafts = build_outreach(db, job_id, language=language)
    console.print(f"Drafted [green]{len(drafts)}[/] messages for {job_id}:")
    for d in drafts:
        console.print(f"  • {d.kind} ({d.channel})")


@app.command()
def prep(job_id: str, language: str = typer.Option("en", help="en | es")) -> None:
    """Full prep for one job: tailor CV → draft outreach → write the send-ready package."""
    from engine.cv.build import build_for_job
    from engine.outreach.build import build_outreach, write_package

    with _db() as db:
        cv = build_for_job(db, job_id, language=language)
        build_outreach(db, job_id, language=language)
        pkg = write_package(db, job_id, language=language)
    console.print(f"[bold green]Ready[/]: {job_id}")
    console.print(f"  Coverage {cv.coverage:.0%} · parse {'✓' if cv.parse_ok else '✗'}")
    console.print(f"  Package: {pkg}")


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
    language: str = typer.Option("en", help="CV/outreach language: en | es"),
    discover: bool = typer.Option(True, help="Run discovery first."),
    json_out: bool = typer.Option(
        False, "--json", help="Emit the run summary as JSON (for the orchestrator)."
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
        s = run(db, limit=limit, language=language, do_discover=discover)
    if json_out:
        import json as _json

        print(_json.dumps(s, indent=2, ensure_ascii=False))
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
        "\nPara la mejora completa (IA-forward, LinkedIn), usa la guía "
        "[bold]cv-linkedin-advisor[/] (advisor/cv_linkedin_advisor.md)."
    )


@app.command()
def status() -> None:
    """Show pipeline counts and the latest health of each source."""
    with _db() as db:
        counts = db.counts_by_state()
        health = db.latest_source_health()
        last_run = db.meta_get("last_run")
    console.print(f"[bold]Pipeline[/] (last run: {last_run or 'never'})")
    for state, n in counts.items():
        console.print(f"  {state:<12} {n}")
    if health:
        table = Table(title="Source health")
        for col in ("source", "ok", "count", "when", "error"):
            table.add_column(col)
        for h in health:
            table.add_row(
                h["source"],
                "✓" if h["ok"] else "[red]✗[/]",
                str(h["count"]),
                (h["run_at"] or "")[:19],
                (h["error"] or "")[:40],
            )
        console.print(table)


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
) -> None:
    """Create a new profile seeded from the templates, ready to edit."""
    from engine import profiles

    try:
        res = profiles.create_profile(profile_id, label)
    except ValueError as e:
        console.print(f"[red]✗[/] {e}")
        raise typer.Exit(2) from None
    verb = "Creado" if res["created"] else "Ya existía"
    console.print(f"[green]✓[/] {verb} perfil [bold]{profile_id}[/] → {res['root']}")
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
        console.print(f"  {mark} [bold]{p['id']}[/]{owner} — {p.get('label', '')}")


if __name__ == "__main__":
    app()
