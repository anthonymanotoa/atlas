"""F3 §6.3: matcher determinista de historias STAR+R + formateo para pegar."""

from __future__ import annotations

from engine.stories import format_story, match_stories

ONTOLOGY = {"python": ["py"], "airflow": ["apache airflow"], "sql": []}

S1 = {
    "id": 1,
    "title": "Pipeline caído en Black Friday",
    "situation": "ETL crítico caído en pico",
    "task": "Restaurar en menos de 1h",
    "action": "Rollback y circuit breaker en Airflow",
    "result": "Recuperado en 40 minutos",
    "reflection": "Añadí alertas proactivas",
    "skills": ["python", "airflow"],
}
S2 = {
    "id": 2,
    "title": "Negociación con stakeholder",
    "situation": "Roadmap en conflicto",
    "task": "Alinear prioridades",
    "action": "Workshop de trade-offs",
    "result": "Acuerdo en 2 semanas",
    "reflection": "Escuchar primero",
    "skills": ["communication"],
}


def test_match_ranks_by_skill_and_token_overlap():
    ranked = match_stories([S1, S2], "Tell me about debugging a python airflow incident", ONTOLOGY)
    assert ranked and ranked[0][0]["id"] == 1
    assert ranked[0][1] > 0
    ids = [s["id"] for s, _ in ranked]
    assert ids.index(1) < ids.index(2) if 2 in ids else True


def test_match_canonicalizes_aliases():
    # "apache airflow" en la query debe matchear la skill canónica "airflow"
    ranked = match_stories([S1], "experience with apache airflow", ONTOLOGY)
    assert ranked and ranked[0][0]["id"] == 1


def test_match_hyphenated_canonical_gets_skill_boost():
    """A hyphenated whole-skill query ("scikit-learn") must earn the 3x skill boost.

    The word tokenizer splits "scikit-learn" into {scikit, learn}, so the whole-skill
    canonical never appears as a single token — like space-separated multiword aliases,
    the hyphen-joined form must be detected as a raw phrase hit in the query.
    """
    ontology = {"scikit-learn": ["sklearn"]}
    hyphen_story = {
        "id": 1,
        "title": "ML model",
        "situation": "Built a churn model",
        "task": "",
        "action": "trained a classifier",
        "result": "",
        "reflection": "",
        "skills": ["scikit-learn"],
    }
    ranked = match_stories([hyphen_story], "your scikit-learn experience", ontology)
    assert ranked and ranked[0][0]["id"] == 1
    # 3x skill weight for the whole-skill overlap (not merely a body-token score).
    assert ranked[0][1] >= 3.0
    # The alias "sklearn" must reach the same canonical and boost too.
    ranked_alias = match_stories([hyphen_story], "your sklearn experience", ontology)
    assert ranked_alias and ranked_alias[0][1] >= 3.0


def test_match_empty_query_returns_empty():
    assert match_stories([S1, S2], "", ONTOLOGY) == []


def test_no_match_returns_empty():
    assert match_stories([S2], "kubernetes cluster autoscaling", ONTOLOGY) == []


def test_format_story_structure_and_truncation():
    text = format_story(S1)
    for label in ("Situación:", "Tarea:", "Acción:", "Resultado:", "Reflexión:"):
        assert label in text
    assert text.startswith("**Pipeline caído en Black Friday**")
    short = format_story(S1, max_words=10)
    assert len(short.split()) <= 11 and short.endswith("…")


# --- Extra coverage beyond the brief: determinism, skill-weight, tie-breaking, format edges ---


def test_skill_weight_beats_bare_token_overlap():
    """A story matching a query skill (weight 3x) outranks one that only shares plain tokens."""
    skill_story = {
        "id": 1,
        "title": "x",
        "situation": "",
        "task": "",
        "action": "",
        "result": "",
        "reflection": "",
        "skills": ["python"],
    }
    token_story = {
        "id": 2,
        "title": "notes on incident and rollback and pico",
        "situation": "incident",
        "task": "rollback",
        "action": "pico",
        "result": "",
        "reflection": "",
        "skills": [],
    }
    ranked = match_stories([token_story, skill_story], "python incident", ONTOLOGY)
    assert ranked[0][0]["id"] == 1  # the skill match wins despite fewer plain-token hits


def test_ranking_is_deterministic_and_tie_broken_by_id():
    """Same inputs -> same order; ties resolve by ascending story id, stably."""
    a = {
        "id": 7,
        "title": "python work",
        "situation": "",
        "task": "",
        "action": "",
        "result": "",
        "reflection": "",
        "skills": ["python"],
    }
    b = {
        "id": 3,
        "title": "python work",
        "situation": "",
        "task": "",
        "action": "",
        "result": "",
        "reflection": "",
        "skills": ["python"],
    }
    ranked1 = match_stories([a, b], "python", ONTOLOGY)
    ranked2 = match_stories([b, a], "python", ONTOLOGY)
    # Identical scores, so identical ordering regardless of input order.
    assert [s["id"] for s, _ in ranked1] == [s["id"] for s, _ in ranked2]
    # Tie broken by ascending id.
    assert [s["id"] for s, _ in ranked1] == [3, 7]


def test_format_story_omits_missing_sections():
    sparse = {
        "id": 9,
        "title": "Only a title",
        "situation": "",
        "task": "",
        "action": "",
        "result": "",
        "reflection": "",
        "skills": [],
    }
    text = format_story(sparse)
    assert text == "**Only a title**"
    assert "Situación:" not in text


def test_format_story_no_truncation_when_under_limit():
    text = format_story(S1, max_words=400)
    assert not text.endswith("…")
    assert "Reflexión: Añadí alertas proactivas" in text
