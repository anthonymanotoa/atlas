"""Story bank STAR+R (F3 §6.3) — matcher determinista + formateo.

Port del scoring por overlap de career-ops `match-star.mjs`: sin LLM. Ante una pregunta
de entrevista o un JD, rankea las historias del banco por solape de skills (peso 3x) y
de tokens de texto, canonicalizando ambos lados con la ontología del perfil
(engine.config.load_ontology: canonical → aliases).

Determinista y $0: el mismo input produce siempre el mismo ranking, con desempate estable
por `id` de historia (asc). No hace red ni llamadas a modelos.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-zA-Z0-9áéíóúñüÁÉÍÓÚÑÜ+#.]{2,}")
_STOPWORDS = frozenset(
    # English
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "with",
        "on",
        "at",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "how",
        "what",
        "when",
        "tell",
        "me",
        "about",
        "your",
        "you",
        "my",
        "i",
        "we",
        "they",
        "it",
        "this",
        "that",
    }
    # Spanish
    | {
        "de",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "unas",
        "unos",
        "y",
        "o",
        "u",
        "en",
        "que",
        "con",
        "para",
        "como",
        "sobre",
        "del",
        "al",
        "su",
        "sus",
        "mi",
        "mis",
        "fue",
        "eran",
        "ser",
        "estar",
        "cuando",
        "cómo",
        "qué",
        "cuéntame",
    }
)
SKILL_WEIGHT = 3.0
_STORY_TEXT_KEYS = ("title", "situation", "task", "action", "result", "reflection")


def _tokens(text: str) -> set[str]:
    return {t.lower().rstrip(".") for t in _WORD.findall(text or "")} - _STOPWORDS


def _alias_map(ontology: dict[str, list[str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for canonical, aliases in (ontology or {}).items():
        can = canonical.lower()
        out[can] = can
        for a in aliases or []:
            out[a.lower()] = can
    return out


def _canonicalize(tokens: set[str], amap: dict[str, str]) -> set[str]:
    return {amap.get(t, t) for t in tokens}


def match_stories(
    stories: list[dict], query_text: str, ontology: dict[str, list[str]]
) -> list[tuple[dict, float]]:
    """Historias rankeadas por relevancia a la query. Solo devuelve score > 0.

    Puntúa ``SKILL_WEIGHT * |skills ∩ query| + |tokens ∩ query|`` tras canonicalizar
    ambos lados con la ontología. Orden descendente por score, con desempate estable
    por ``id`` de historia (ascendente) para que el ranking sea reproducible.
    """
    amap = _alias_map(ontology)
    # Los alias que el tokenizador por palabra parte —multi-palabra ("apache airflow") o
    # con guion ("scikit-learn")— no sobreviven como un solo token: _WORD no incluye ni
    # espacio ni guion. Detectarlos como frase cruda en la query y añadir su canónico para
    # que ganen el boost 3x de skill igual que los alias de una sola palabra.
    query_low = (query_text or "").lower()
    phrase_hits = {
        can for alias, can in amap.items() if (" " in alias or "-" in alias) and alias in query_low
    }
    q = _canonicalize(_tokens(query_text), amap) | phrase_hits
    if not q:
        return []
    out: list[tuple[dict, float]] = []
    for s in stories:
        skills = _canonicalize({str(x).lower() for x in (s.get("skills") or [])}, amap)
        body = " ".join(str(s.get(k) or "") for k in _STORY_TEXT_KEYS)
        toks = _canonicalize(_tokens(body), amap)
        score = SKILL_WEIGHT * len(q & skills) + len(q & toks)
        if score > 0:
            out.append((s, round(score, 1)))
    # Desempate determinista: score desc, luego id asc (0 si falta id).
    return sorted(out, key=lambda p: (-p[1], _story_id(p[0])))


def _story_id(story: dict) -> int:
    """id de historia como int para el desempate; 0 si ausente o no numérico."""
    try:
        return int(story.get("id", 0))
    except (TypeError, ValueError):
        return 0


def format_story(story: dict, max_words: int = 400) -> str:
    """Bloque STAR+R listo para pegar; truncado limpio a max_words con elipsis."""
    parts = [f"**{story.get('title', '')}**"]
    for label, key in (
        ("Situación", "situation"),
        ("Tarea", "task"),
        ("Acción", "action"),
        ("Resultado", "result"),
        ("Reflexión", "reflection"),
    ):
        if story.get(key):
            parts.append(f"{label}: {story[key]}")
    text = "\n\n".join(parts)
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"
