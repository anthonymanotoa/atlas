"""Domain-agnostic portfolio: the prompt, the proof-source builder section, and the
peer-research host filter must all be driven by the profile (master_cv basics + criteria +
cv_layout proof_source), NOT by a hardcoded data-scientist persona.

These tests exercise two profiles end-to-end:
  - ARCHITECTURE: proof_source "visual_gallery", basics.label "Arquitecta" → a visual gallery,
    no GitHub, no Vercel/Next.js/"AI builds" data persona.
  - DATA: proof_source "github", basics.label "Senior Data Scientist" → the data role survives
    and the GitHub proof path is selected (no live network needed).
"""

from __future__ import annotations

from engine.config import Criteria
from engine.portfolio.builder import _proof_section_html, generate_portfolio
from engine.portfolio.peer_research import _proof_hosts, research_queries
from engine.portfolio.prompt import build_portfolio_prompt

# ── fixtures ──────────────────────────────────────────────────────────────────

ARCH_CV = {
    "basics": {
        "name": "Arq. Sofía Vega",
        "label": "Arquitecta",
        "summary": "Arquitecta junior enfocada en BIM y visualización.",
        "linkedin": "https://li/in/sofia",
        "portfolio": "https://issuu.com/sofiavega/docs/portfolio",
        "website": "https://sofiavega.com",
        # no github / email — must not be assumed
    },
    "skills": ["Revit (Avanzado)", "AutoCAD (Avanzado)", "Lumion (Avanzado)", "BIM (Intermedio)"],
    "experience": [
        {
            "title": "Dibujante de arquitectura",
            "company": "Estudio Loja",
            "start": "Jan 2024",
            "end": "Present",
            "highlights": ["Produje planos y documentación de obra en AutoCAD y Revit."],
        }
    ],
    "projects": [
        {
            "name": "Rehabilitación patrimonial — Centro histórico",
            "description": "Proyecto de taller de rehabilitación patrimonial.",
        },
        {"name": "Vivienda unifamiliar", "description": "Diseño residencial con render en tiempo real."},
    ],
    "education": [{"degree": "Arquitecta", "area": "Arquitectura", "institution": "Universidad X"}],
}

ARCH_LAYOUT = {
    "order": ["summary", "skills", "projects", "experience", "education", "licensure"],
    "labels": {},
    "proof_source": "visual_gallery",
}

ARCH_CRITERIA = Criteria(
    roles=["architect", "architectural designer", "bim modeler"],
    role_aliases=["arquitecta"],
    core_keywords=["revit", "autocad", "bim"],
    prose="Busco roles de arquitectura de edificios; el portafolio es el filtro decisivo.",
)

DATA_CV = {
    "basics": {
        "name": "Ada Lovelace",
        "label": "Senior Data Scientist & AI Engineer",
        "summary": "5+ years in retention and GenAI.",
        "linkedin": "https://li/in/ada",
        "github": "github.com/ada",
        "email": "ada@example.com",
    },
    "skills": ["SQL", "Python", "Large Language Models"],
    "experience": [
        {
            "title": "Sr Data Specialist",
            "company": "Acme Corp",
            "start": "Feb 2025",
            "end": "Present",
            "highlights": ["Own retention analytics (AOV, CVR, LTV)."],
        }
    ],
    "projects": [{"name": "Churn model", "description": "XGBoost churn model"}],
}

DATA_LAYOUT = {
    "order": ["summary", "skills", "experience", "education", "certs", "projects"],
    "labels": {},
    "proof_source": "github",
}

DATA_CRITERIA = Criteria(
    roles=["data scientist", "ai engineer"],
    repositioning_target="AI/ML",
    core_keywords=["sql", "python"],
    prose="Senior data scientist moving deeper into AI/ML.",
)


# ── build_portfolio_prompt: architecture ──────────────────────────────────────


def test_prompt_architecture_uses_real_role_not_data_persona():
    p = build_portfolio_prompt(ARCH_CV, layout=ARCH_LAYOUT, criteria=ARCH_CRITERIA)
    # the real architecture role/label drives the hero, not the DS persona
    assert "Arquitecta" in p
    assert "Senior Data Scientist" not in p
    assert "AI Engineer" not in p
    # the DS-specific stack / sections must be gone for a visual_gallery profile
    assert "Vercel" not in p
    assert "Next.js" not in p
    assert "AI builds" not in p
    # the candidate's real material is woven in
    assert "Estudio Loja" in p
    assert "Revit (Avanzado)" in p


def test_prompt_architecture_foregrounds_visual_gallery_and_external_links():
    p = build_portfolio_prompt(ARCH_CV, layout=ARCH_LAYOUT, criteria=ARCH_CRITERIA).lower()
    # a visual_gallery profile points at the portfolio link, NOT code repos
    assert "github" not in p
    assert "galería" in p or "gallery" in p or "visual" in p
    assert "issuu.com/sofiavega" in p  # the real portfolio link surfaces


def test_prompt_does_not_assume_github_or_email_links():
    # ARCH_CV has no github / email; the links block must not fabricate them
    p = build_portfolio_prompt(ARCH_CV, layout=ARCH_LAYOUT, criteria=ARCH_CRITERIA)
    assert "li/in/sofia" in p  # linkedin present → shown
    assert "sofiavega.com" in p  # website present → shown


# ── build_portfolio_prompt: data (regression) ─────────────────────────────────


def test_prompt_data_keeps_role_and_is_detailed():
    p = build_portfolio_prompt(DATA_CV, layout=DATA_LAYOUT, criteria=DATA_CRITERIA)
    assert "Senior Data Scientist & AI Engineer" in p
    assert "Ada Lovelace" in p
    assert "Acme Corp" in p and "AOV" in p
    assert "Large Language Models" in p
    assert len(p) > 2000  # still a detailed brief, not a stub


def test_prompt_default_call_is_backward_compatible():
    # the legacy 1-arg call (no layout/criteria) must still produce the data brief
    p = build_portfolio_prompt(DATA_CV)
    assert "Senior Data Scientist & AI Engineer" in p
    assert len(p) > 2000


def test_prompt_role_falls_back_to_criteria_roles_when_no_label():
    cv = {"basics": {"name": "No Label"}, "skills": ["X"]}
    p = build_portfolio_prompt(cv, layout=ARCH_LAYOUT, criteria=ARCH_CRITERIA)
    # no basics.label → use the criteria roles, never the DS default
    assert "architect" in p.lower()
    assert "Senior Data Scientist" not in p


# ── builder proof-source ──────────────────────────────────────────────────────


def test_visual_gallery_proof_section_no_network(tmp_path):
    # visual_gallery must NOT hit api.github.com and must link the portfolio + projects
    html = _proof_section_html(ARCH_CV, "visual_gallery")
    assert "api.github.com" not in html
    assert "issuu.com/sofiavega" in html
    assert "Rehabilitación patrimonial" in html  # projects rendered as the visual proof


def test_none_proof_section_is_empty():
    assert _proof_section_html(DATA_CV, "none").strip() == ""


def test_visual_gallery_does_not_duplicate_projects(tmp_path):
    # The visual proof block lists the projects; the standard "Proyectos" section must be
    # skipped so each project appears exactly once (not in both).
    path = generate_portfolio(
        ARCH_CV, version="dedup", output_dir=tmp_path, proof_source="visual_gallery"
    )
    html = path.read_text()
    assert html.count("Rehabilitación patrimonial") == 1


def test_generate_portfolio_visual_gallery_does_not_fetch_github(tmp_path, monkeypatch):
    import engine.portfolio.builder as builder

    def _boom(*a, **k):  # any github fetch in visual_gallery mode is a bug
        raise AssertionError("github fetch must not happen for visual_gallery")

    monkeypatch.setattr(builder, "_github_repos", _boom)
    path = generate_portfolio(
        ARCH_CV, version="arch", output_dir=tmp_path, proof_source="visual_gallery"
    )
    text = path.read_text()
    assert "issuu.com/sofiavega" in text
    assert "api.github.com" not in text


def test_generate_portfolio_github_path_selected(tmp_path, monkeypatch):
    import engine.portfolio.builder as builder

    calls = {}

    def _fake_repos(username, **k):
        calls["username"] = username
        return [{"name": "atlas", "url": "https://github.com/ada/atlas", "desc": "x", "stars": 3}]

    monkeypatch.setattr(builder, "_github_repos", _fake_repos)
    path = generate_portfolio(
        DATA_CV, version="data", output_dir=tmp_path, include_github=True, proof_source="github"
    )
    text = path.read_text()
    assert calls.get("username") == "ada"  # github proof path was selected + handle parsed
    assert "atlas" in text


# ── peer_research host filter ─────────────────────────────────────────────────


def test_proof_hosts_visual_gallery():
    hosts = _proof_hosts("visual_gallery")
    assert "behance.net" in hosts
    assert "issuu.com" in hosts
    assert "github.io" not in hosts and "vercel.app" not in hosts


def test_proof_hosts_github():
    hosts = _proof_hosts("github")
    assert "github.io" in hosts
    assert "vercel.app" in hosts


def test_research_queries_uses_proof_hosts():
    arch = research_queries("architect", proof_source="visual_gallery")
    assert "behance.net" in arch["portfolios"]
    assert "vercel.app" not in arch["portfolios"]
    data = research_queries("data scientist", proof_source="github")
    assert "github.io" in data["portfolios"] or "vercel.app" in data["portfolios"]
    # backward-compatible default (no proof_source) keeps the github/vercel hosts
    legacy = research_queries("data scientist")
    assert "github.io" in legacy["portfolios"] or "vercel.app" in legacy["portfolios"]
