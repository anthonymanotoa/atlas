"""CSV export with an editable column template. Local-only, no external services.

Two ways to customise the CSV "design":
  1. Edit ``config/csv_templates/default.yaml`` (a plain `columns:` list) by hand, or
  2. Pick columns in the dashboard's Export modal (persisted per-profile in the `meta`
     KV row ``csv_columns``).

Column resolution precedence: explicit request > saved ``csv_columns`` > default.yaml >
the hardcoded fallback below.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from pathlib import Path

import yaml

import engine.paths as paths
from engine import analytics


def _salary(job: dict) -> str:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if not lo and not hi:
        return ""
    cur = job.get("salary_currency") or ""
    iv = job.get("salary_interval") or ""
    rng = f"{int(lo)}–{int(hi)}" if lo and hi else f"{int(hi or lo)}"
    return f"{rng} {cur}/{iv}".strip()


def _remote(job: dict) -> str:
    return {1: "sí", 0: "no"}.get(job.get("is_remote"), "")


# Catalog: column id -> (Spanish header label, value accessor over an annotated job row).
COLUMNS: dict[str, tuple[str, Callable[[dict], object]]] = {
    "id": ("ID", lambda j: j.get("id")),
    "title": ("Puesto", lambda j: j.get("title")),
    "company": ("Empresa", lambda j: j.get("company")),
    "location": ("Ubicación", lambda j: j.get("location")),
    "state": ("Estado", lambda j: j.get("state")),
    "fit_score": ("Fit", lambda j: j.get("fit_score")),
    "is_remote": ("Remoto", _remote),
    "salary": ("Salario", _salary),
    "salary_min": ("Salario mín", lambda j: j.get("salary_min")),
    "salary_max": ("Salario máx", lambda j: j.get("salary_max")),
    "salary_currency": ("Moneda", lambda j: j.get("salary_currency")),
    "language": ("Idioma", lambda j: j.get("language")),
    "date_posted": ("Publicado", lambda j: j.get("date_posted")),
    "posted_days": ("Días publicado", lambda j: j.get("posted_days")),
    "url": ("URL", lambda j: j.get("url")),
    "apply_url": ("URL postulación", lambda j: j.get("apply_url")),
    "sources": ("Fuentes", lambda j: ", ".join(j.get("sources") or [])),
    "knockout_flags": ("Flags", lambda j: ", ".join(j.get("knockout_flags") or [])),
    "discovered_at": ("Descubierto", lambda j: j.get("discovered_at")),
}

# Sensible fallback if no template file or saved selection exists.
DEFAULT_COLUMNS = [
    "title",
    "company",
    "fit_score",
    "state",
    "salary",
    "language",
    "posted_days",
    "apply_url",
]


def available_columns() -> list[dict]:
    """The full catalog the UI offers, in catalog order."""
    return [{"id": cid, "label": label} for cid, (label, _) in COLUMNS.items()]


def _default_from_yaml() -> list[str] | None:
    for base in (paths.CONFIG_DIR, paths.REPO_ROOT / "config"):
        f = Path(base) / "csv_templates" / "default.yaml"
        if f.exists():
            data = yaml.safe_load(f.read_text()) or {}
            cols = [c for c in (data.get("columns") or []) if c in COLUMNS]
            if cols:
                return cols
    return None


def resolve_columns(requested: list[str] | None, saved_json: str | None) -> list[str]:
    """Pick the column set: explicit request > saved selection > default.yaml > fallback."""
    if requested:
        cols = [c for c in requested if c in COLUMNS]
        if cols:
            return cols
    if saved_json:
        try:
            saved = [c for c in json.loads(saved_json) if c in COLUMNS]
            if saved:
                return saved
        except (json.JSONDecodeError, TypeError):
            pass
    return _default_from_yaml() or DEFAULT_COLUMNS


def _prepare(job: dict) -> dict:
    """Annotate + parse JSON columns so list-valued fields render in the CSV."""
    analytics.annotate(job)
    for key, src in (("sources", "sources_json"), ("knockout_flags", "knockout_flags")):
        if not isinstance(job.get(key), list):
            try:
                job[key] = json.loads(job.get(src) or "[]")
            except (json.JSONDecodeError, TypeError):
                job[key] = []
    return job


def _fmt(v: object) -> str:
    return "" if v is None else str(v)


def generate_csv(jobs: list[dict], columns: list[str]) -> str:
    """Render annotated job rows to CSV text with Spanish header labels."""
    columns = [c for c in columns if c in COLUMNS] or DEFAULT_COLUMNS
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([COLUMNS[c][0] for c in columns])
    for job in jobs:
        _prepare(job)
        w.writerow([_fmt(COLUMNS[c][1](job)) for c in columns])
    return buf.getvalue()


def validate_download_dir(raw: str) -> str:
    """Expand + resolve a user-chosen download folder, creating it if needed.

    Local single-user app: the user picks a folder on their own machine. We expand
    ``~``, resolve, reject a path that exists as a non-directory, and create it otherwise.
    """
    p = Path(raw).expanduser()
    try:
        p = p.resolve()
    except OSError as e:
        raise ValueError(f"invalid path: {e}") from None
    if p.exists() and not p.is_dir():
        raise ValueError("path exists and is not a directory")
    p.mkdir(parents=True, exist_ok=True)
    return str(p)
