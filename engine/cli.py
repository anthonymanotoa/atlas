"""Atlas command-line interface.

`atlas <command>` — the deterministic engine the Cowork brain orchestrates, and the
commands you run by hand. Nothing here sends or submits anything.
"""
from __future__ import annotations

import os
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from engine import __version__
from engine.paths import DB_PATH, REPO_ROOT

# Load .env (Adzuna keys etc.) without overriding a real shell env.
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:  # noqa: BLE001
    pass

app = typer.Typer(add_completion=False, help="Atlas — personal job-search cockpit (local, $0).")
console = Console()


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
        console.print("[bold red]✗ ANTHROPIC_API_KEY is set[/] — `claude -p`/SDK would bill "
                      "per-token to an API account. Unset it before scheduling the brain.")
    else:
        console.print("[green]✓[/] ANTHROPIC_API_KEY not set (good).")
    default_base = base_url in (None, "", "https://api.anthropic.com", "https://api.anthropic.com/")
    if base_url and not default_base:
        console.print(f"[yellow]![/] ANTHROPIC_BASE_URL is set to a non-default host ({base_url}). "
                      "Confirm Claude Code `/status` shows your Max subscription, not API billing.")
    else:
        console.print("[green]✓[/] ANTHROPIC_BASE_URL is default/unset.")

    console.print(f"[green]✓[/] DB path: {DB_PATH}")
    console.print("\n[bold]Manual checklist for a true $0 guarantee:[/]")
    console.print("  1. Run the brain as a Claude [bold]Cowork/Desktop scheduled task[/] "
                  "(never `claude -p`).")
    console.print("  2. [bold]Disable usage credits / overage billing[/] in your Claude account "
                  "→ the system fails closed.")
    console.print("  3. In Claude Desktop, enable [bold]Keep computer awake[/] and keep the app open.")
    raise typer.Exit(0 if ok else 1)


@app.command()
def discover(
    only: Optional[str] = typer.Option(None, help="Comma list to limit sources: ats,jobspy,indeed,linkedin,himalayas,adzuna"),
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
        table.add_row(label, "✓" if s["ok"] else "[red]✗[/]", str(s["fetched"]),
                      f"[green]{s['new']}[/]", str(s["seen"]), str(s["ms"]))
    console.print(table)
    console.print(f"[bold]Total:[/] {summary['new']} new, {summary['seen']} seen, "
                  f"{summary['fetched']} fetched")
    if summary["errors"]:
        console.print("[yellow]Source issues:[/] " + "; ".join(summary["errors"]))


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
            table.add_row(h["source"], "✓" if h["ok"] else "[red]✗[/]", str(h["count"]),
                          (h["run_at"] or "")[:19], (h["error"] or "")[:40])
        console.print(table)


@app.command(name="resolve-ats")
def resolve_ats(url: str) -> None:
    """Detect which ATS a company careers URL uses (for companies.yaml)."""
    from engine.discovery.registry import resolve_ats as resolve
    result = resolve(url)
    console.print(result or "[yellow]No known ATS detected[/]")


if __name__ == "__main__":
    app()
