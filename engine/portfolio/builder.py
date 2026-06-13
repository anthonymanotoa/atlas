"""Portfolio generator (P3-F).

Renders the user's master_cv.yaml into a clean, **standalone** single-page HTML site
(inline CSS, no external CDN — so it works offline and prints cleanly). Local-only: it
writes under OUTBOX_DIR and is NEVER auto-published. Optionally enriches with public
GitHub repo metadata (GITHUB_TOKEN is optional and unrelated to the $0/no-Anthropic-key
rule; 60 req/h unauthenticated, 5000/h with a token).
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

import engine.paths as paths

_STYLE = """
:root{--fg:#1a1a1f;--muted:#555;--accent:#3b5bdb;--line:#e4e4ea;--bg:#fff}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:var(--fg);
  background:var(--bg);max-width:820px;margin:0 auto;padding:48px 24px;line-height:1.5}
h1{font-size:2rem;margin:0}
h2{font-size:1.1rem;margin:2rem 0 .5rem;border-bottom:2px solid var(--line);padding-bottom:.25rem}
.sub{color:var(--muted);font-size:1.05rem;margin:.25rem 0 0}
.contact{color:var(--muted);font-size:.9rem;margin-top:.5rem}
.contact a{color:var(--accent);text-decoration:none}
.role{margin:1rem 0}
.role .h{font-weight:600}
.role .meta{color:var(--muted);font-size:.85rem}
ul{margin:.4rem 0 .4rem 1.1rem;padding:0}
.skills span{display:inline-block;background:#f1f2f6;border-radius:6px;padding:2px 8px;margin:2px;font-size:.82rem}
.repo{font-size:.9rem;margin:.3rem 0}
.repo a{color:var(--accent);text-decoration:none}
footer{margin-top:3rem;color:#aaa;font-size:.75rem}
"""


def _e(v: object) -> str:
    return html.escape(str(v or ""))


def _gh_handle(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.search(r"github\.com/([A-Za-z0-9_-]+)", raw)
    return m.group(1) if m else raw.strip().lstrip("@") or None


def _github_repos(username: str | None, *, limit: int = 6) -> list[dict]:
    """Best-effort public repos, newest first. Returns [] on any error / no username."""
    if not username:
        return []
    try:
        import httpx

        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = httpx.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": limit, "type": "owner"},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        return [
            {
                "name": x["name"],
                "url": x["html_url"],
                "desc": x.get("description") or "",
                "stars": x.get("stargazers_count", 0),
            }
            for x in r.json()
            if not x.get("fork")
        ][:limit]
    except Exception:  # noqa: BLE001 — enrichment is optional; never fail the build
        return []


def _render_html(cv: dict, repos: list[dict]) -> str:
    b = cv.get("basics", {}) or {}
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{_e(b.get('name') or 'Portfolio')}</title>",
        f"<style>{_STYLE}</style></head><body>",
        f"<h1>{_e(b.get('name'))}</h1>",
        f"<div class='sub'>{_e(b.get('label'))}</div>",
    ]
    contact = " · ".join(
        filter(
            None,
            [
                _e(b.get("email")) if b.get("email") else "",
                f"<a href='{_e(b.get('linkedin'))}'>LinkedIn</a>" if b.get("linkedin") else "",
                _e(b.get("location")) if b.get("location") else "",
            ],
        )
    )
    if contact:
        parts.append(f"<div class='contact'>{contact}</div>")
    if b.get("summary"):
        parts.append(f"<h2>Resumen</h2><p>{_e(b.get('summary'))}</p>")

    skills = cv.get("skills") or []
    if skills:
        parts.append("<h2>Skills</h2><div class='skills'>")
        parts += [f"<span>{_e(s)}</span>" for s in skills]
        parts.append("</div>")

    exp = cv.get("experience") or []
    if exp:
        parts.append("<h2>Experiencia</h2>")
        for e in exp:
            parts.append("<div class='role'>")
            parts.append(f"<div class='h'>{_e(e.get('title'))} · {_e(e.get('company'))}</div>")
            parts.append(f"<div class='meta'>{_e(e.get('dates') or e.get('start'))}</div>")
            hls = e.get("highlights") or []
            if hls:
                parts.append("<ul>" + "".join(f"<li>{_e(h)}</li>" for h in hls) + "</ul>")
            parts.append("</div>")

    projects = cv.get("projects") or []
    if projects:
        parts.append("<h2>Proyectos</h2>")
        for p in projects:
            parts.append(
                f"<div class='role'><div class='h'>{_e(p.get('name'))}</div>"
                f"<div>{_e(p.get('description'))}</div></div>"
            )

    if repos:
        parts.append("<h2>GitHub</h2>")
        for repo in repos:
            stars = f" ★{repo['stars']}" if repo["stars"] else ""
            parts.append(
                f"<div class='repo'><a href='{_e(repo['url'])}'>{_e(repo['name'])}</a>{stars}"
                f" — {_e(repo['desc'])}</div>"
            )

    edu = cv.get("education") or []
    if edu:
        parts.append("<h2>Educación</h2>")
        for ed in edu:
            parts.append(
                f"<div class='role'><div class='h'>{_e(ed.get('degree') or ed.get('area'))}</div>"
                f"<div class='meta'>{_e(ed.get('institution'))} · {_e(ed.get('dates'))}</div></div>"
            )

    parts.append("<footer>Generado localmente con Atlas · privado, no publicado.</footer>")
    parts.append("</body></html>")
    return "".join(parts)


def generate_portfolio(
    cv: dict,
    *,
    version: str = "v1",
    include_github: bool = False,
    output_dir: Path | None = None,
) -> Path:
    """Render master_cv.yaml → a standalone index.html. Returns the file path."""
    repos = (
        _github_repos(_gh_handle((cv.get("basics", {}) or {}).get("github")))
        if include_github
        else []
    )
    out_dir = Path(output_dir) if output_dir else (paths.OUTBOX_DIR / f"portfolio_{version}")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(_render_html(cv, repos), encoding="utf-8")
    return path
