"""P3-E interview prep: role-question selection + grounded prep-doc generation."""

from __future__ import annotations

import engine.paths as paths
from engine.db.models import DB
from engine.interview.interview_prep import _role_questions, _topics_to_review, gen_prep_doc
from engine.normalize import Job


def test_role_questions_match_and_default():
    qs = _role_questions("Senior Data Scientist", "a/b testing and models", "en")
    assert any("A/B" in q for q in qs)
    assert _role_questions("Plumber", "pipes", "en")  # unknown role → non-empty default


def test_topics_to_review_are_jd_derived_gaps():
    ontology = {"kubernetes": ["k8s"], "python": []}
    job = {"title": "ML Engineer", "description": "kubernetes and python required"}
    cv = {"skills": ["python"]}  # evidences python, misses kubernetes
    topics = _topics_to_review(job, cv, ontology)
    assert "kubernetes" in topics  # the gap
    assert "python" not in topics  # already evidenced → not a review topic


def test_topics_to_review_empty_when_no_jd_match():
    # Degrades gracefully: nothing in the JD maps to the ontology → no topics section.
    assert (
        _topics_to_review(
            {"title": "Barista", "description": "coffee"}, {"skills": []}, {"python": []}
        )
        == []
    )


def test_prep_doc_lists_jd_topics_section(tmp_path, monkeypatch):
    import engine.interview.interview_prep as ip

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)
    monkeypatch.setattr(ip, "load_ontology", lambda: {"kubernetes": ["k8s"], "python": []})
    monkeypatch.setattr(ip, "load_master_cv", lambda: {"skills": ["python"]})
    db = DB(tmp_path / "topics.db")
    try:
        db.upsert_job(
            Job(
                source="greenhouse",
                title="ML Engineer",
                company="Acme",
                description="kubernetes and python required",
            )
        )
        jid = db.list_jobs()[0]["id"]
        iid = db.add_interview(jid, scheduled_at="2026-07-15", round="technical")
        text = gen_prep_doc(db, iid, language="en").read_text()
        assert "Topics to review" in text
        assert "kubernetes" in text
    finally:
        db.close()


def test_gen_prep_doc_writes_grounded_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path)  # don't write to the repo's data/
    db = DB(tmp_path / "a.db")
    try:
        db.upsert_job(
            Job(
                source="greenhouse",
                title="Senior Data Scientist",
                company="Acme",
                description="A/B testing and machine learning models in production",
            )
        )
        jid = db.list_jobs()[0]["id"]
        iid = db.add_interview(jid, scheduled_at="2026-07-15", round="technical")
        db.add_interviewer(iid, name="Jane Doe", title="ML Lead", linkedin_url="https://li/in/jane")
        path = gen_prep_doc(db, iid, language="en")
        text = path.read_text()
        assert "Interview prep" in text
        assert "Jane Doe" in text
        assert "A/B test" in text  # DS role question
        assert db.get_interview(iid)["prep_path"]  # persisted back on the row
    finally:
        db.close()
