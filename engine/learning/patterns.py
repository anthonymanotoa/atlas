"""Deterministic pattern detection over confirmed outcomes (P2-D).

Pure functions: a list of `application_outcomes` dicts → a list of
(pattern_type, observation, confidence, evidence_count). Confidence saturates with
evidence so a single data point never drives the scorer hard.
"""

from __future__ import annotations

from statistics import median

_SAT = 5.0  # evidence count at which confidence reaches 1.0


def _conf(n: int) -> float:
    return round(min(n / _SAT, 1.0), 2)


def detect(outcomes: list[dict]) -> list[tuple[str, str, float, int]]:
    n = len(outcomes)
    if n == 0:
        return []
    learned: list[tuple[str, str, float, int]] = []

    days = [o["response_days"] for o in outcomes if o.get("response_days") is not None]
    if days:
        learned.append(
            (
                "process_speed",
                f"Responde en ~{int(median(days))} días (mediana de {len(days)}).",
                _conf(len(days)),
                len(days),
            )
        )

    rejected = sum(1 for o in outcomes if o.get("final_state") == "rejected")
    learned.append(("rejection_rate", f"Rechazo en {rejected}/{n} casos.", _conf(n), n))

    offers = sum(1 for o in outcomes if o.get("offer_made") or o.get("final_state") == "offer")
    if offers:
        learned.append(("offer_rate", f"Oferta en {offers}/{n} casos.", _conf(n), n))

    advanced = [
        o
        for o in outcomes
        if o.get("final_state") in ("interviewed", "offer") or o.get("interview_count")
    ]
    if advanced:
        via_ref = sum(1 for o in advanced if o.get("recruiter_source") == "referral")
        if via_ref:
            learned.append(
                (
                    "referral_conversion",
                    f"{via_ref}/{len(advanced)} avances vinieron por referido — prioriza referidos.",
                    _conf(len(advanced)),
                    len(advanced),
                )
            )
    return learned
