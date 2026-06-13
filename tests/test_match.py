"""CV↔JD match score: importance-weighted coverage with an honest missing list."""

from __future__ import annotations

from engine.cv.match import match_score

ONTOLOGY = {
    "python": ["py"],
    "machine learning": ["ml"],
    "sql": [],
    "kubernetes": ["k8s"],
    "pytorch": [],
}


def _job(title: str = "Data Scientist", desc: str = "") -> dict:
    return {"title": title, "description": desc}


def test_score_is_bounded_and_monotonic_in_coverage():
    job = _job("Machine Learning Engineer", "We need python, sql, pytorch and kubernetes.")
    weak = {"skills": ["python"]}
    strong = {"skills": ["python", "sql", "pytorch", "kubernetes", "machine learning"]}
    s_weak = match_score(job, weak, ONTOLOGY)
    s_strong = match_score(job, strong, ONTOLOGY)
    assert 0 <= s_weak.score <= 100
    assert 0 <= s_strong.score <= 100
    assert s_strong.score > s_weak.score
    assert s_strong.score == 100  # covers everything the JD asks for


def test_missing_lists_uncovered_jd_keywords():
    res = match_score(
        _job("ML Engineer", "python and kubernetes required"), {"skills": ["python"]}, ONTOLOGY
    )
    assert "python" in res.matched
    assert "kubernetes" in res.missing
    assert "kubernetes" not in res.matched


def test_coverage_via_highlights_not_just_skills():
    # A keyword evidenced only in an experience highlight still counts as covered (truthful).
    cv = {
        "skills": [],
        "experience": [{"highlights": ["Built dashboards on top of SQL warehouses"]}],
    }
    res = match_score(_job("Data Scientist", "sql required"), cv, ONTOLOGY)
    assert "sql" in res.matched


def test_no_jd_keywords_scores_zero():
    res = match_score(_job("Barista", "make coffee"), {"skills": ["python"]}, ONTOLOGY)
    assert res.score == 0
    assert res.matched == [] and res.missing == []


def test_title_keyword_weighs_more_than_body_only():
    # importance gives +3 for a title hit; covering the title keyword should pull the score high.
    res = match_score(
        _job("Python Engineer", "sql nice to have"),
        {"skills": ["python"]},
        {"python": [], "sql": []},
    )
    assert res.score > 50
