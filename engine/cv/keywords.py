"""Extract job-description keywords using the skills ontology.

Not naive frequency: we match each ontology skill's surface forms (canonical +
aliases/acronyms) with word boundaries, and rank by importance (title hits weigh more).
This high-precision gazetteer approach is what the tailoring + coverage report use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class KeywordHit:
    canonical: str
    surface: str          # the exact surface form found in the JD
    in_title: bool
    count: int

    @property
    def importance(self) -> float:
        return (3.0 if self.in_title else 0.0) + min(self.count, 5)


@lru_cache(maxsize=512)
def _rx(surface: str) -> re.Pattern:
    # word-ish boundaries that tolerate symbols like a/b, c++, .net, scikit-learn
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(surface) + r"(?![A-Za-z0-9])", re.I)


def build_alias_index(ontology: dict[str, list[str]]) -> dict[str, str]:
    """surface form (lower) -> canonical skill."""
    idx: dict[str, str] = {}
    for canonical, aliases in ontology.items():
        for surface in [canonical, *aliases]:
            idx[surface.lower()] = canonical
    return idx


def extract_jd_keywords(title: str, text: str, ontology: dict[str, list[str]]) -> list[KeywordHit]:
    title_l = (title or "").lower()
    body = f"{title or ''}\n{text or ''}"
    hits: dict[str, KeywordHit] = {}
    for canonical, aliases in ontology.items():
        best: KeywordHit | None = None
        for surface in [canonical, *aliases]:
            matches = _rx(surface).findall(body)
            if not matches:
                continue
            in_title = bool(_rx(surface).search(title_l))
            cand = KeywordHit(canonical, surface, in_title, len(matches))
            if best is None or cand.importance > best.importance:
                best = cand
        if best:
            hits[canonical] = best
    return sorted(hits.values(), key=lambda h: h.importance, reverse=True)
