"""Deterministic CV + LinkedIn audit against current best practices.

This produces the structured findings the `cv-linkedin-advisor` skill builds on. The
deterministic checks catch the mechanical issues (placeholders, unquantified bullets,
missing target-domain framing, parse-safety); the LLM skill does the truthful repositioning
using the user's Claude memories + recent projects. The "target domain" is the profile's, not
hardcoded — positioning nudges are driven by criteria.repositioning_target / core_keywords.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from engine.config import Criteria, load_criteria, load_ontology

_DIGIT = re.compile(r"\d")
_PLACEHOLDER = re.compile(r"<[^>]+>")


@dataclass
class Finding:
    severity: str  # high | med | low
    area: str
    message: str
    suggestion: str


def _mentions_any(text: str, terms: list[str]) -> bool:
    """True if `text` contains any of `terms` (case-insensitive substring)."""
    t = text.lower()
    return any(term.lower() in t for term in terms)


def audit_cv(master: dict, criteria: Criteria | None = None) -> list[Finding]:
    """Audit a CV against best practices for the profile's domain.

    Domain-specific opinions are driven by `criteria`: positioning nudges only fire when
    `criteria.repositioning_target` is set, and 'core terms' come from `criteria.core_keywords`."""
    criteria = criteria or load_criteria()
    target = criteria.repositioning_target.strip()
    f: list[Finding] = []
    basics = master.get("basics", {}) or {}
    blob = _flatten(master)

    # 1. Placeholders left unfilled.
    placeholders = sorted(set(_PLACEHOLDER.findall(blob)))
    if placeholders:
        f.append(
            Finding(
                "high",
                "completitud",
                f"Hay placeholders sin rellenar: {', '.join(placeholders[:6])}",
                "Completa con tus datos reales antes de usar el CV.",
            )
        )
    confirma = blob.count("[confirma")
    if confirma:
        f.append(
            Finding(
                "high",
                "completitud",
                f"Hay {confirma} campos marcados [confirma: …] por llenar.",
                "Rellena fechas, educación, rol anterior y métricas reales.",
            )
        )

    # 2. Contact.
    if not basics.get("email"):
        f.append(
            Finding(
                "high",
                "contacto",
                "Falta el email en basics.",
                "Añádelo en el cuerpo (no en encabezado) para que el ATS lo lea.",
            )
        )
    if not basics.get("linkedin"):
        f.append(Finding("med", "contacto", "Falta el LinkedIn.", "Añade la URL de tu perfil."))

    # 3. Summary.
    summary = basics.get("summary", "") or ""
    words = len(summary.split())
    if words == 0:
        f.append(
            Finding(
                "high",
                "resumen",
                "No hay resumen profesional.",
                "Escribe 40–90 palabras con tu propuesta de valor.",
            )
        )
    elif words > 110:
        f.append(
            Finding(
                "low",
                "resumen",
                f"El resumen es largo ({words} palabras).",
                "Recórtalo a ~40–90 palabras.",
            )
        )
    if target and summary and not _mentions_any(summary, criteria.core_keywords):
        f.append(
            Finding(
                "med",
                f"posicionamiento {target}",
                f"El resumen no refleja tu objetivo ({target}).",
                f"Reposiciónalo hacia {target} de forma veraz, nombrando tus skills clave.",
            )
        )

    # 4. Skills.
    skills = master.get("skills", []) or []
    if len(skills) < 8:
        f.append(
            Finding(
                "med",
                "skills",
                f"Pocas skills listadas ({len(skills)}).",
                "Lista 12–18 skills canónicas que realmente tengas.",
            )
        )
    if target and not any(_mentions_any(s, criteria.core_keywords) for s in skills):
        f.append(
            Finding(
                "med",
                f"posicionamiento {target}",
                f"No hay skills de {target} en la lista.",
                f"Añade las de {target} que domines, de forma veraz.",
            )
        )

    # 5. Experience: quantified, ATS-friendly bullets.
    for exp in master.get("experience", []) or []:
        role = f"{exp.get('title', '?')} @ {exp.get('company', '?')}"
        hl = exp.get("highlights") or []
        if len(hl) < 2:
            f.append(
                Finding(
                    "med",
                    "experiencia",
                    f"'{role}' tiene <2 logros.",
                    "Añade 3–5 logros con verbo de acción + herramienta + resultado.",
                )
            )
        unquant = [h for h in hl if not _DIGIT.search(h)]
        if unquant:
            f.append(
                Finding(
                    "med",
                    "impacto",
                    f"'{role}': {len(unquant)} logros sin métrica.",
                    "Cuantifica (%, tiempo, escala) — solo con números reales.",
                )
            )

    # 6. Core keyword coverage for the profile's target domain (from criteria.core_keywords).
    ont = load_ontology()
    cv_low = blob.lower()
    missing = [
        c for c in criteria.core_keywords if c.lower() not in cv_low and c.lower() not in ont.get(c, [])
    ]
    if missing:
        f.append(
            Finding(
                "low",
                "keywords",
                f"Faltan términos núcleo: {', '.join(missing)}.",
                "Inclúyelos si aplican a tu experiencia real.",
            )
        )

    return f


def _flatten(obj) -> str:
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)


def audit_dict(master: dict, criteria: Criteria | None = None) -> dict:
    findings = audit_cv(master, criteria)
    by_sev = {"high": 0, "med": 0, "low": 0}
    for x in findings:
        by_sev[x.severity] = by_sev.get(x.severity, 0) + 1
    return {"findings": [asdict(x) for x in findings], "summary": by_sev}
