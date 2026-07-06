"""Knock-out pre-scan (F3 §6.4) — visibilidad pre-aplicación, sin tocar el score.

Escaneo determinista del JD contra el perfil: requisitos que suelen descalificar a un
candidato remoto internacional (work authorization, clearance, años muy por encima,
grado no evidenciado en el CV, idioma fuera del perfil). Cada warning cita la evidencia.
"""

from __future__ import annotations

import re

from engine.config import Criteria
from engine.scoring.fit import _required_years

_VISA_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bauthori[sz]ed to work in\b", re.I), "pide autorización de trabajo"),
    (re.compile(r"\bwork (?:permit|authori[sz]ation)\b", re.I), "pide permiso de trabajo"),
    (
        re.compile(
            r"\bvisa sponsorship (?:is )?not available\b|\bno visa sponsorship\b"
            r"|\bwithout (?:visa )?sponsorship\b|\b(?:cannot|unable to) (?:offer|provide) (?:visa )?sponsorship\b",
            re.I,
        ),
        "sin patrocinio de visa",
    ),
    (re.compile(r"\bu\.?s\.? citizen(?:ship)?\b", re.I), "pide ciudadanía US"),
    (re.compile(r"\bsecurity clearance\b", re.I), "pide security clearance"),
    (re.compile(r"\bmust (?:be located|reside|live) in\b", re.I), "exige residencia específica"),
]

_DEGREE_RE = re.compile(
    r"\b(bachelor'?s?|master'?s?|ph\.?d|licenciatura|maestr[ií]a|doctorado)\b"
    r"[^.\n]{0,80}\b(?:required|is required|requerid[oa])\b",
    re.I,
)
_DEGREE_LEVEL = {
    "bachelor": 1, "licenciatura": 1, "bsc": 1, "b.s": 1, "ingenier": 1,
    "master": 2, "maestr": 2, "msc": 2, "m.s": 2,
    "phd": 3, "ph.d": 3, "doctorado": 3, "doctor": 3,
}
# A degree named as "preferred/nice-to-have but NOT required" is not a knock-out — skip when a
# negator precedes the "required" token inside the matched span (mirrors the F2 negated-hybrid
# guard in fit.py). Anchors the pattern to a genuine requirement, not a benign "not required".
_DEGREE_NOT_REQUIRED = re.compile(r"\b(?:not|no|n.t)\b[^.\n]{0,12}\brequir", re.I)
_LANG_RE = re.compile(
    r"\b(?:fluent|fluency|proficien\w+|native)\s+(?:in\s+)?"
    r"(english|spanish|german|french|portuguese|dutch|italian|ingl[eé]s|alem[aá]n|franc[eé]s|portugu[eé]s|italiano)\b",
    re.I,
)
_LANG_CODE = {
    "english": "en", "inglés": "en", "ingles": "en",
    "spanish": "es",
    "german": "de", "alemán": "de", "aleman": "de",
    "french": "fr", "francés": "fr", "frances": "fr",
    "portuguese": "pt", "portugués": "pt", "portugues": "pt",
    "dutch": "nl", "italian": "it", "italiano": "it",
}


def _evidence(text: str, m: re.Match, pad: int = 60) -> str:
    start, end = max(m.start() - pad, 0), min(m.end() + pad, len(text))
    return " ".join(text[start:end].split())


def _level_in(text: str) -> int:
    low = text.lower()
    return max((lv for term, lv in _DEGREE_LEVEL.items() if term in low), default=0)


def _cv_degree_level(master_cv: dict) -> int:
    hay = " ".join(str(e) for e in (master_cv.get("education") or []))
    return _level_in(hay)


def prescan(job: dict, criteria: Criteria, master_cv: dict) -> list[dict]:
    """Warnings deterministas {code, label, evidence}. Lista vacía = nada detectado."""
    text = f"{job.get('title') or ''}\n{job.get('description') or ''}"
    warnings: list[dict] = []
    # 1. Visa / work authorization / clearance / residencia — un solo warning (el primero).
    for rx, label in _VISA_PATTERNS:
        m = rx.search(text)
        if m:
            warnings.append(
                {"code": "work_authorization", "label": label, "evidence": _evidence(text, m)}
            )
            break
    # 2. Años muy por encima del candidato (gap > 2 — más laxo que el scorer, es un aviso).
    req = _required_years(job.get("description") or "")
    if req and criteria.candidate_years and req > criteria.candidate_years + 2:
        warnings.append(
            {
                "code": "years_gap",
                "label": f"pide {req}+ años (tienes ~{criteria.candidate_years})",
                "evidence": f"{req}+ years required",
            }
        )
    # 3. Grado requerido no evidenciado en el master CV. Skip "not required" (benign nice-to-have).
    m = _DEGREE_RE.search(text)
    if m and not _DEGREE_NOT_REQUIRED.search(m.group(0)):
        asked = _level_in(m.group(1))
        if asked > _cv_degree_level(master_cv):
            warnings.append(
                {
                    "code": "degree",
                    "label": f"exige {m.group(1).lower()} (no evidenciado en tu CV)",
                    "evidence": _evidence(text, m),
                }
            )
    # 4. Idioma requerido fuera del perfil.
    m = _LANG_RE.search(text)
    if m:
        code = _LANG_CODE.get(m.group(1).lower())
        if code and code not in criteria.languages:
            warnings.append(
                {
                    "code": "language",
                    "label": f"exige {m.group(1)} fluido",
                    "evidence": _evidence(text, m),
                }
            )
    return warnings
