"""P3-F portfolio: GitHub-handle parsing + standalone HTML generation."""

from __future__ import annotations

from engine.portfolio.builder import _gh_handle, generate_portfolio
from engine.portfolio.peer_examples import (
    load_references,
    peer_examples_for,
    portfolio_patterns_for,
)
from engine.portfolio.prompt import build_portfolio_prompt


def test_gh_handle_extracts():
    assert _gh_handle("https://github.com/anthonym") == "anthonym"
    assert _gh_handle("@anthonym") == "anthonym"
    assert _gh_handle(None) is None


def test_generate_portfolio_is_standalone(tmp_path):
    cv = {
        "basics": {
            "name": "Ada Lovelace",
            "label": "Data Scientist",
            "summary": "AI/ML focus",
            "email": "a@x.com",
            "linkedin": "https://li/in/ada",
        },
        "skills": ["Python", "SQL"],
        "experience": [
            {
                "title": "DS",
                "company": "Acme",
                "dates": "2020–",
                "highlights": ["Built X improving Y 30%"],
            }
        ],
        "projects": [{"name": "Proj", "description": "desc"}],
    }
    path = generate_portfolio(cv, version="t1", output_dir=tmp_path)
    text = path.read_text()
    assert path.name == "index.html"
    assert "Ada Lovelace" in text and "Python" in text and "Built X" in text
    assert "<style>" in text  # inline CSS
    assert (
        "cdn" not in text.lower() and "http-equiv" not in text.lower()
    )  # standalone, offline-safe


def test_peer_examples_are_well_formed():
    examples = peer_examples_for("data")
    assert len(examples) >= 8
    for ex in examples:
        assert ex["url"].startswith("http")
        assert ex["peer_name"] and ex["role_match"]
        assert ex["key_strengths"] and ex["what_to_steal"]
    assert set(portfolio_patterns_for("data")) >= {
        "secciones",
        "como_mostrar_proyectos",
        "diseno",
    }


def test_references_are_domain_scoped_and_empty_when_absent():
    # A domain with no committed references file gets a blank set — a new domain never
    # inherits another field's portfolios.
    blank = load_references("no_such_domain_xyz")
    assert blank == {"examples": [], "patterns": {}}
    # The data/AI domain ships a populated set.
    assert peer_examples_for("data") and portfolio_patterns_for("data")


def test_architecture_references_are_well_formed_and_distinct_from_data():
    arch = peer_examples_for("architecture")
    assert len(arch) >= 6
    for ex in arch:
        assert ex["url"].startswith("http")
        assert ex["peer_name"] and ex["role_match"]
        assert ex["key_strengths"] and ex["what_to_steal"]
    # Architecture proof lives on visual hosts / personal sites, never code hosting.
    assert any("behance.net" in ex["url"] or "issuu.com" in ex["url"] for ex in arch)
    assert not any("github" in ex["url"] for ex in arch)
    # The two domains are genuinely decoupled — no shared reference URLs.
    data_urls = {ex["url"] for ex in peer_examples_for("data")}
    assert data_urls.isdisjoint({ex["url"] for ex in arch})
    assert set(portfolio_patterns_for("architecture")) >= {
        "secciones",
        "como_mostrar_proyectos",
        "diseno",
        "errores_a_evitar",
    }


def test_portfolio_prompt_personalizes_from_cv():
    cv = {
        "basics": {
            "name": "Ada Lovelace",
            "label": "Senior Data Scientist & AI Engineer",
            "summary": "5+ years in retention and GenAI.",
            "linkedin": "https://li/in/x",
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
    }
    p = build_portfolio_prompt(cv)
    assert "Ada Lovelace" in p
    assert "Senior Data Scientist & AI Engineer" in p
    assert "Acme Corp" in p and "AOV" in p  # experience woven in from the CV
    assert "Large Language Models" in p
    assert len(p) > 2000  # detailed, not a stub
