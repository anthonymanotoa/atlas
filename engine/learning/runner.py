"""Learning loop runner (P2-D): turn confirmed outcomes into per-company learnings.

Idempotent — re-running on the same outcomes upserts the same rows. Reads only
HUMAN-confirmed outcomes; never invents data.
"""

from __future__ import annotations

from engine.db.models import DB
from engine.learning.patterns import detect


def auto_learn(db: DB, company: str) -> int:
    """Recompute + upsert learnings for one company. Returns the number of patterns."""
    learned = detect(db.outcomes_for_company(company))
    for pattern_type, observation, confidence, evidence in learned:
        db.upsert_learning(company, pattern_type, observation, confidence, evidence)
    return len(learned)


def auto_learn_all(db: DB) -> int:
    """Recompute learnings for every company that has outcomes. Returns total patterns."""
    return sum(auto_learn(db, c) for c in db.companies_with_outcomes())
