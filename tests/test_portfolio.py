"""P3-F portfolio: GitHub-handle parsing + standalone HTML generation."""

from __future__ import annotations

from engine.portfolio.builder import _gh_handle, generate_portfolio


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
