"""Lightweight, dependency-free language detection for job descriptions.

Heuristic stop-word scoring across the languages Atlas cares about (en/es, the
languages it tailors CVs in) plus the non-target languages it should flag and
downrank (de/fr/pt). Returns a 2-letter code or None when there isn't enough
signal. Deterministic and offline — no new dependency, keeps the $0 invariant.

This lives at the engine root (like `util.py`) so both `normalize` (sets the
field at discovery time) and `scoring.fit` (penalises off-target postings) can use
it without a layering inversion.
"""

from __future__ import annotations

# Common function words, space-padded so we match whole words on a space-padded text.
_MARKERS: dict[str, tuple[str, ...]] = {
    "en": (
        " the ",
        " and ",
        " for ",
        " with ",
        " you ",
        " we ",
        " our ",
        " your ",
        " will ",
        " are ",
        " to the ",
        " experience ",
        " team ",
        " role ",
        " skills ",
    ),
    "es": (
        " el ",
        " la ",
        " los ",
        " las ",
        " de ",
        " para ",
        " con ",
        " que ",
        " una ",
        " experiencia ",
        " conocimientos ",
        " equipo ",
        " puesto ",
        " trabajo ",
        " buscamos ",
        " requisitos ",
    ),
    "de": (
        " und ",
        " für ",
        " mitarbeiter",
        " wir ",
        " sie ",
        " bei uns",
        " kenntnisse",
        " der ",
        " die ",
        " das ",
        " mit ",
        " eine ",
    ),
    "fr": (
        " et de ",
        " pour ",
        " vous ",
        " nous ",
        " entreprise ",
        " compétences",
        " le ",
        " la ",
        " des ",
        " avec ",
        " une ",
        " votre ",
    ),
    "pt": (
        " e ",
        " para ",
        " com ",
        " você ",
        " nós ",
        " empresa ",
        " conhecimentos",
        " trabalho ",
        " experiência ",
        " da ",
        " do ",
        " uma ",
    ),
}

TARGET_AND_FLAGGED = tuple(_MARKERS)  # ("en","es","de","fr","pt")


def detect_language(text: str | None, *, min_hits: int = 3) -> str | None:
    """Best-effort language code for a posting. None when signal is too weak.

    Counts space-padded marker occurrences per language and returns the strongest,
    provided it clears `min_hits` (so a one-line snippet doesn't get mislabelled).
    """
    if not text:
        return None
    t = f" {text.lower()} "
    scores = {lang: sum(t.count(m) for m in markers) for lang, markers in _MARKERS.items()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] < min_hits:
        return None
    return best
