"""P3-F portfolio: GitHub-handle parsing + standalone HTML generation."""

from __future__ import annotations

from engine.portfolio.builder import _gh_handle, generate_portfolio
from engine.portfolio.peer_examples import PEER_EXAMPLES, PORTFOLIO_PATTERNS
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
    assert len(PEER_EXAMPLES) >= 8
    for ex in PEER_EXAMPLES:
        assert ex["url"].startswith("http")
        assert ex["peer_name"] and ex["role_match"]
        assert ex["key_strengths"] and ex["what_to_steal"]
    assert set(PORTFOLIO_PATTERNS) >= {"secciones", "como_mostrar_proyectos", "diseno"}


def test_portfolio_prompt_personalizes_from_cv():
    cv = {
        "basics": {
            "name": "Anthony Manotoa",
            "label": "Senior Data Scientist & AI Engineer",
            "summary": "5+ years in retention and GenAI.",
            "linkedin": "https://li/in/x",
        },
        "skills": ["SQL", "Python", "Large Language Models"],
        "experience": [
            {
                "title": "Sr Data Specialist",
                "company": "Trafilea",
                "start": "Feb 2025",
                "end": "Present",
                "highlights": ["Own retention analytics (AOV, CVR, LTV)."],
            }
        ],
    }
    p = build_portfolio_prompt(cv)
    assert "Anthony Manotoa" in p
    assert "Senior Data Scientist & AI Engineer" in p
    assert "Trafilea" in p and "AOV" in p  # real experience woven in
    assert "Large Language Models" in p
    assert len(p) > 2000  # detailed, not a stub
