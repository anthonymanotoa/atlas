"""Deterministic CV + LinkedIn audit against current best practices.

This produces the structured findings the `cv-linkedin-advisor` skill builds on. The
deterministic checks catch the mechanical issues (placeholders, unquantified bullets,
missing AI-forward framing, parse-safety); the LLM skill does the truthful repositioning
using the user's Claude memories + recent projects.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from engine.config import load_ontology

_DIGIT = re.compile(r"\d")
_PLACEHOLDER = re.compile(r"<[^>]+>")
AI_TERMS = ("ai", "llm", "genai", "generative", "machine learning", "ml ", "prompt",
            "rag", "agent", "language model")


@dataclass
class Finding:
    severity: str   # high | med | low
    area: str
    message: str
    suggestion: str


def _has_ai(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in AI_TERMS)


def audit_cv(master: dict) -> list[Finding]:
    f: list[Finding] = []
    basics = master.get("basics", {}) or {}
    blob = _flatten(master)

    # 1. Placeholders left unfilled.
    placeholders = sorted(set(_PLACEHOLDER.findall(blob)))
    if placeholders:
        f.append(Finding("high", "completitud",
                         f"Hay placeholders sin rellenar: {', '.join(placeholders[:6])}",
                         "Completa con tus datos reales antes de usar el CV."))
    confirma = blob.count("[confirma")
    if confirma:
        f.append(Finding("high", "completitud",
                         f"Hay {confirma} campos marcados [confirma: …] por llenar.",
                         "Rellena fechas, educación, rol anterior y métricas reales."))

    # 2. Contact.
    if not basics.get("email"):
        f.append(Finding("high", "contacto", "Falta el email en basics.",
                         "Añádelo en el cuerpo (no en encabezado) para que el ATS lo lea."))
    if not basics.get("linkedin"):
        f.append(Finding("med", "contacto", "Falta el LinkedIn.", "Añade la URL de tu perfil."))

    # 3. Summary.
    summary = basics.get("summary", "") or ""
    words = len(summary.split())
    if words == 0:
        f.append(Finding("high", "resumen", "No hay resumen profesional.",
                         "Escribe 40–90 palabras con tu propuesta de valor y enfoque en IA."))
    elif words > 110:
        f.append(Finding("low", "resumen", f"El resumen es largo ({words} palabras).",
                         "Recórtalo a ~40–90 palabras."))
    if summary and not _has_ai(summary):
        f.append(Finding("med", "posicionamiento IA",
                         "El resumen no menciona IA/LLM/ML pese a tu pivote.",
                         "Reposiciona hacia IA/ML: nombra LLMs, GenAI o agentes de forma veraz."))

    # 4. Skills.
    skills = master.get("skills", []) or []
    if len(skills) < 8:
        f.append(Finding("med", "skills", f"Pocas skills listadas ({len(skills)}).",
                         "Lista 12–18 skills canónicas que realmente tengas."))
    if not any(_has_ai(s) for s in skills):
        f.append(Finding("med", "posicionamiento IA", "No hay skills de IA en la lista.",
                         "Añade las de IA que domines (LLMs, GenAI, RAG, Prompt Engineering)."))

    # 5. Experience: quantified, ATS-friendly bullets.
    for exp in master.get("experience", []) or []:
        role = f"{exp.get('title','?')} @ {exp.get('company','?')}"
        hl = exp.get("highlights") or []
        if len(hl) < 2:
            f.append(Finding("med", "experiencia", f"'{role}' tiene <2 logros.",
                             "Añade 3–5 logros con verbo de acción + herramienta + resultado."))
        unquant = [h for h in hl if not _DIGIT.search(h)]
        if unquant:
            f.append(Finding("med", "impacto", f"'{role}': {len(unquant)} logros sin métrica.",
                             "Cuantifica (%, tiempo, escala) — solo con números reales."))

    # 6. Ontology coverage for a DS/AI target.
    ont = load_ontology()
    cv_low = blob.lower()
    core = ["python", "sql", "machine learning", "large language models", "a/b testing",
            "statistics", "generative ai"]
    missing = [c for c in core if c not in cv_low and c not in ont.get(c, [])]
    if missing:
        f.append(Finding("low", "keywords", f"Faltan términos núcleo: {', '.join(missing)}.",
                         "Inclúyelos si aplican a tu experiencia real."))

    return f


def _flatten(obj) -> str:
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)


def audit_dict(master: dict) -> dict:
    findings = audit_cv(master)
    by_sev = {"high": 0, "med": 0, "low": 0}
    for x in findings:
        by_sev[x.severity] = by_sev.get(x.severity, 0) + 1
    return {"findings": [asdict(x) for x in findings], "summary": by_sev}
