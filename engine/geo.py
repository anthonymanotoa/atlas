"""Country/region gazetteer + geo-scope logic for remote-restriction scoring (F2).

Deterministic and dependency-free: a small embedded map of common countries onto the four
coarse regions the scorer reasons about (latam / eu / na / apac), the text aliases the
extractor in engine/normalize.py recognizes, and the single coverage predicate the scorer
(engine/scoring/fit.py, factor 2c) calls.

Scope tokens — the ``jobs.geo_scope`` vocabulary:
  * ISO-2 country codes ("us", "gb", "ec", ...)
  * regions: "latam" | "eu" | "na" | "apac" | "emea"
  * "worldwide" (explicitly unrestricted) | "unknown" (remote, nothing detected)
  * ""          (not applicable: confirmed on-site posting)
Multiple tokens are comma-joined ("us,ca").
"""

from __future__ import annotations

# ISO-2 → coarse region. "eu" means geographic Europe: the restriction language in real
# postings ("Europe only", "EU-based") almost never distinguishes EU membership, so we don't.
COUNTRY_TO_REGION: dict[str, str] = {
    # LatAm (20)
    "ar": "latam",
    "bo": "latam",
    "br": "latam",
    "cl": "latam",
    "co": "latam",
    "cr": "latam",
    "cu": "latam",
    "do": "latam",
    "ec": "latam",
    "gt": "latam",
    "hn": "latam",
    "mx": "latam",
    "ni": "latam",
    "pa": "latam",
    "pe": "latam",
    "pr": "latam",
    "py": "latam",
    "sv": "latam",
    "uy": "latam",
    "ve": "latam",
    # North America (2)
    "ca": "na",
    "us": "na",
    # Europe (33)
    "at": "eu",
    "be": "eu",
    "bg": "eu",
    "ch": "eu",
    "cy": "eu",
    "cz": "eu",
    "de": "eu",
    "dk": "eu",
    "ee": "eu",
    "es": "eu",
    "fi": "eu",
    "fr": "eu",
    "gb": "eu",
    "gr": "eu",
    "hr": "eu",
    "hu": "eu",
    "ie": "eu",
    "is": "eu",
    "it": "eu",
    "lt": "eu",
    "lu": "eu",
    "lv": "eu",
    "mt": "eu",
    "nl": "eu",
    "no": "eu",
    "pl": "eu",
    "pt": "eu",
    "ro": "eu",
    "rs": "eu",
    "se": "eu",
    "si": "eu",
    "sk": "eu",
    "ua": "eu",
    # APAC (18)
    "au": "apac",
    "bd": "apac",
    "cn": "apac",
    "hk": "apac",
    "id": "apac",
    "in": "apac",
    "jp": "apac",
    "kr": "apac",
    "lk": "apac",
    "my": "apac",
    "np": "apac",
    "nz": "apac",
    "ph": "apac",
    "pk": "apac",
    "sg": "apac",
    "th": "apac",
    "tw": "apac",
    "vn": "apac",
}

# USPS two-letter state/territory codes, lowercased. Used only to stop a US-scoped location
# ("CO, US") from mis-reading a state abbreviation as the ISO-2 country that shares its spelling
# (CO→Colombia, PA→Panama, DE→Germany, …). See extract_geo_restriction in engine/normalize.py.
US_STATE_CODES: frozenset[str] = frozenset(
    {
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
        "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
        "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
        "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
        "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
        "dc",
    }
)
# The ISO-2 country codes that collide with a USPS state code: {ar, ca, co, de, id, in, mt, pa}.
STATE_CODE_COLLISIONS: frozenset[str] = frozenset(
    c for c in COUNTRY_TO_REGION if c in US_STATE_CODES
)

# Text alias (lowercase) → scope token. Only UNAMBIGUOUS aliases belong here: full country
# names, region names, and safe short forms. Bare ISO-2 codes are deliberately absent —
# lowercased they collide with English/Spanish words ("in", "us", "it", "no", "es") — and
# are matched separately, uppercase-only, in the location field (see engine/normalize.py).
GEO_ALIASES: dict[str, str] = {
    # US / UK / safe short forms
    "united states": "us",
    "usa": "us",
    "u.s.": "us",
    "u.s.a.": "us",
    "us": "us",
    "america": "us",
    "united kingdom": "gb",
    "uk": "gb",
    "u.k.": "gb",
    "great britain": "gb",
    "england": "gb",
    # LatAm countries
    "argentina": "ar",
    "bolivia": "bo",
    "brazil": "br",
    "brasil": "br",
    "chile": "cl",
    "colombia": "co",
    "costa rica": "cr",
    "cuba": "cu",
    "dominican republic": "do",
    "ecuador": "ec",
    "el salvador": "sv",
    "guatemala": "gt",
    "honduras": "hn",
    "mexico": "mx",
    "méxico": "mx",
    "nicaragua": "ni",
    "panama": "pa",
    "panamá": "pa",
    "paraguay": "py",
    "peru": "pe",
    "perú": "pe",
    "puerto rico": "pr",
    "uruguay": "uy",
    "venezuela": "ve",
    # North America
    "canada": "ca",
    "canadá": "ca",
    # Europe
    "austria": "at",
    "belgium": "be",
    "bulgaria": "bg",
    "croatia": "hr",
    "cyprus": "cy",
    "czech republic": "cz",
    "czechia": "cz",
    "denmark": "dk",
    "estonia": "ee",
    "finland": "fi",
    "france": "fr",
    "germany": "de",
    "deutschland": "de",
    "greece": "gr",
    "hungary": "hu",
    "iceland": "is",
    "ireland": "ie",
    "italy": "it",
    "italia": "it",
    "latvia": "lv",
    "lithuania": "lt",
    "luxembourg": "lu",
    "malta": "mt",
    "netherlands": "nl",
    "the netherlands": "nl",
    "norway": "no",
    "poland": "pl",
    "portugal": "pt",
    "romania": "ro",
    "serbia": "rs",
    "slovakia": "sk",
    "slovenia": "si",
    "spain": "es",
    "españa": "es",
    "sweden": "se",
    "switzerland": "ch",
    "ukraine": "ua",
    # APAC
    "australia": "au",
    "bangladesh": "bd",
    "china": "cn",
    "hong kong": "hk",
    "india": "in",
    "indonesia": "id",
    "japan": "jp",
    "korea": "kr",
    "south korea": "kr",
    "malaysia": "my",
    "nepal": "np",
    "new zealand": "nz",
    "pakistan": "pk",
    "philippines": "ph",
    "singapore": "sg",
    "sri lanka": "lk",
    "taiwan": "tw",
    "thailand": "th",
    "vietnam": "vn",
    # Regions
    "latam": "latam",
    "latin america": "latam",
    "latinoamérica": "latam",
    "latinoamerica": "latam",
    "américa latina": "latam",
    "america latina": "latam",
    "south america": "latam",
    "central america": "latam",
    "europe": "eu",
    "european union": "eu",
    "eu": "eu",
    "emea": "emea",
    "north america": "na",
    "apac": "apac",
    "asia pacific": "apac",
    "asia-pacific": "apac",
    # Explicitly unrestricted
    "worldwide": "worldwide",
    "anywhere": "worldwide",
    "global": "worldwide",
    "globally": "worldwide",
}


def region_of(country: str) -> str | None:
    """The coarse region of an ISO-2 country code, or None for unknown codes."""
    return COUNTRY_TO_REGION.get((country or "").strip().lower())


def geo_scope_covers(scope: str, country: str, regions: list[str]) -> bool:
    """True when a job's geo scope admits the candidate (→ the scorer must NOT penalize).

    ``scope`` is the ``jobs.geo_scope`` value (comma-joined scope tokens); ``country`` is
    the candidate's ISO-2 code; ``regions`` is criteria.acceptable_regions. Blank/worldwide/
    unknown scopes always cover — we never penalize on missing signal. "worldwide" inside
    ``regions`` is the default no-op (it expresses "unrestricted remote is fine"), NOT a
    whitelist for restricted scopes.
    """
    parts = {p.strip().lower() for p in (scope or "").split(",") if p.strip()}
    if not parts or parts & {"worldwide", "unknown"}:
        return True
    cc = (country or "").strip().lower()
    if cc and cc in parts:
        return True
    creg = COUNTRY_TO_REGION.get(cc)
    if creg and creg in parts:
        return True
    accept = {r.strip().lower() for r in regions if r and r.strip().lower() != "worldwide"}
    if parts & accept:
        return True
    # EMEA (Europe, Middle East, Africa) covers EU region candidates: since the gazetteer has
    # no separate Middle-East/Africa region bucket, "eu" is the only genuine geographic subset.
    if "emea" in parts and creg == "eu":
        return True
    # A country token that lies inside an acceptable region ("br" ⊂ "latam").
    return any(COUNTRY_TO_REGION.get(p) in accept for p in parts if COUNTRY_TO_REGION.get(p))
