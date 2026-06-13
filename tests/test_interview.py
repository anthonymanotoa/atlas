"""P3-E interview prep: role-question selection + grounded prep-doc generation."""

from __future__ import annotations

import engine.paths as paths
from engine.db.models import DB
from engine.interview.interview_prep import _role_questions, gen_prep_doc
from engine.normalize import Job


def test_role_questions_match_and_default():
    qs = _role_questions("Senior Data Scientist", "a/b testing and models", "en")
    assert any("A/B" in q for q in qs)
    assert _role_questions("Plumber", "pipes", "en")  # unknown role → non-empty default


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
