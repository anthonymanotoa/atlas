"""Peer-portfolio research (P3-F).

Storage + (future) SUPERVISED Claude-in-Chrome flow to study peers with a similar
profile and capture what to emulate. Reference-only: we store links + extracted notes,
never clone or hoard a peer's portfolio HTML (respect terms/copyright). The actual
browsing is human-driven and account-safe — see docs/RATE_LIMITING.md.
"""

from __future__ import annotations

from engine.db.models import DB


def list_peers(db: DB) -> list[dict]:
    return db.list_peer_portfolios()


def add_peer(
    db: DB,
    *,
    peer_name: str,
    role_match: str | None = None,
    peer_profile_url: str | None = None,
    peer_portfolio_url: str | None = None,
    key_strengths: list[str] | None = None,
    how_to_emulate: list[str] | None = None,
    source_url: str | None = None,
    notes: str | None = None,
) -> int:
    """Store a peer reference the human confirmed during a supervised research session."""
    return db.add_peer_portfolio(
        peer_name=peer_name,
        role_match=role_match,
        peer_profile_url=peer_profile_url,
        peer_portfolio_url=peer_portfolio_url,
        key_strengths=key_strengths,
        how_to_emulate=how_to_emulate,
        source_url=source_url,
        notes=notes,
    )


# Where peers in a given domain actually publish their portfolios. Driven by the profile's
# proof_source so an architect's search hits Behance/Issuu, not code-hosting domains.
_PROOF_HOSTS: dict[str, list[str]] = {
    "github": ["github.io", "vercel.app"],
    "visual_gallery": ["behance.net", "issuu.com", "cargo.site"],
    "none": [],
}


def _proof_hosts(proof_source: str | None) -> list[str]:
    """Host filter for the 'portfolios' search, keyed by proof_source (defaults to github)."""
    return _PROOF_HOSTS.get(proof_source or "github", _PROOF_HOSTS["github"])


def research_queries(role_match: str, *, proof_source: str | None = None) -> dict[str, str]:
    """Ready-to-paste queries for the supervised Chrome session (no requests made here).

    `proof_source` (from cv_layout.yaml) chooses where to look for peer portfolios:
    code hosts for "github", visual hosts (Behance/Issuu/Cargo) for "visual_gallery".
    """
    role = (role_match or "").strip()
    hosts = _proof_hosts(proof_source)
    site_filter = " ".join(f"OR site:{h}" for h in hosts).removeprefix("OR ")
    portfolios = f"{role} portfolio {site_filter}".strip() if hosts else f"{role} portfolio"
    return {
        "portfolios": portfolios,
        "linkedin_peers": f"site:linkedin.com/in {role}",
    }
