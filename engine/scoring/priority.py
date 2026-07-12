"""Blended ranking score for the shortlist (Task 10).

Atlas jobs carry two distinct 0-100 scores that get confused at a glance: `fit_score`
(job↔criteria — "does this role match what I'm looking for") and `match_score`
(CV↔JD keyword coverage — "does my CV read as a match for this posting"). A job can be
fit=100/match=20 (great role, CV needs tailoring) — showing both raw numbers side by
side with no framing reads as contradictory. `priority` blends them into one ranking
number so `top` and the dashboard can sort/label sensibly.
"""

from __future__ import annotations

FIT_WEIGHT = 0.7
MATCH_WEIGHT = 0.3


def priority(fit_score: float | None, match_score: int | None) -> float:
    """Blended ranking score: `fit*0.7 + match*0.3` when a match score exists, else `fit`.

    A missing `fit_score` is treated as 0 (an unscored job never outranks a scored one).
    A missing `match_score` means the CV↔JD match hasn't been computed yet (e.g. before
    `tailor` runs) — priority then falls back to fit alone rather than blending in a
    penalizing zero. Rounded to 1 decimal.
    """
    fit = fit_score if fit_score is not None else 0.0
    if match_score is None:
        return round(fit, 1)
    return round(fit * FIT_WEIGHT + match_score * MATCH_WEIGHT, 1)
