"""CV↔JD match score — a visible 0–100 of how well the master CV covers a posting.

Distinct from `fit_score` (job vs. the user's *criteria*): this is the CV vs. the *job
description*. It reuses the same gazetteer + truthful coverage predicate as the tailor
(`engine/cv/tailor.py`), but weights by keyword importance and never renders a document, so
it's cheap enough to compute for every scored job. The `missing` list is the importance-ranked
JD keywords the CV doesn't evidence — i.e. honest gaps surfaced for the user, never faked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.cv.keywords import KeywordHit, build_alias_index, extract_jd_keywords

# Mirror tailor.TOP_JD_KEYWORDS so the match report and the tailored-CV coverage share scope.
TOP_JD_KEYWORDS = 25


@dataclass
class MatchResult:
    score: int  # 0–100: importance-weighted coverage of the JD's keywords by the CV
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # importance-ranked gaps


def _cv_corpus(master: dict) -> str:
    """Lowercased text of everything the CV can truthfully evidence."""
    return " ".join(
        [
            (master.get("basics", {}) or {}).get("summary", "") or "",
            *(master.get("skills") or []),
            *[h for exp in (master.get("experience") or []) for h in (exp.get("highlights") or [])],
            *[" ".join(exp.get("skills") or []) for exp in (master.get("experience") or [])],
        ]
    ).lower()


def match_score(job: dict, master: dict, ontology: dict[str, list[str]]) -> MatchResult:
    """Importance-weighted coverage of a posting's JD keywords by the user's real CV.

    ``score = round(100 · Σ importance(matched) / Σ importance(all top-N JD keywords))``.
    A keyword counts as covered if its canonical/surface form appears in the user's skills
    (canonicalized) or anywhere in the CV corpus — the same predicate the tailor uses, so the
    match report and the tailored-CV coverage stay consistent.
    """
    title = job.get("title") or ""
    desc = job.get("description") or ""
    hits: list[KeywordHit] = extract_jd_keywords(title, desc, ontology)[:TOP_JD_KEYWORDS]
    if not hits:
        return MatchResult(0, [], [])

    alias_index = build_alias_index(ontology)
    user_canon = {alias_index.get(s.lower(), s) for s in (master.get("skills") or [])}
    corpus = _cv_corpus(master)

    matched: list[str] = []
    missing: list[str] = []
    w_matched = w_total = 0.0
    for h in hits:
        w_total += h.importance
        covered = h.canonical in user_canon or h.canonical in corpus or h.surface.lower() in corpus
        if covered:
            matched.append(h.canonical)
            w_matched += h.importance
        else:
            missing.append(h.canonical)
    score = round(100 * w_matched / w_total) if w_total else 0
    return MatchResult(score=score, matched=matched, missing=missing)
