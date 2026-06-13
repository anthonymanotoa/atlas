"""P2-C: supervised social search queue + query building."""

from __future__ import annotations

from engine.db.models import DB
from engine.social import search


def test_queue_is_idempotent_and_clears(tmp_path):
    db = DB(tmp_path / "a.db")
    try:
        items = search.queue_search(db, "job1", "Acme", "Data Scientist")
        assert len(items) == 1 and items[0]["job_id"] == "job1"
        # queuing the same job again doesn't duplicate
        assert len(search.queue_search(db, "job1", "Acme", "Data Scientist")) == 1
        assert search.pending_searches(db)[0]["company"] == "Acme"
        search.clear_search(db, "job1")
        assert search.pending_searches(db) == []
    finally:
        db.close()


def test_search_queries_mention_company_and_platforms():
    q = search.search_queries("Acme", "Data Scientist")
    assert "Acme" in q["linkedin_recruiters"]
    assert set(q) == {"linkedin_recruiters", "linkedin_posts", "x"}
