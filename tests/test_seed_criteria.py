"""Shipped criteria templates must not carry misleading geo defaults.

`na`/`eu` in `acceptable_regions` conflated "I'd work for a US/EU company" with "I can reside
there" — exactly what let US-only jobs pass. And `geo_penalty` is a retired field (geo is now a
hard disqualifier), so it must not linger in the templates.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_TEMPLATES = sorted(
    p for p in _REPO.rglob("criteria*.md") if "/profiles/" not in p.as_posix()
)


def test_templates_exist():
    assert _TEMPLATES, "no shipped criteria templates found"


def test_shipped_criteria_do_not_default_to_na_or_eu_regions():
    offenders = []
    for p in _TEMPLATES:
        m = re.search(r"acceptable_regions:\s*\[([^\]]*)\]", p.read_text())
        if m and re.search(r"\b(na|eu)\b", m.group(1)):
            offenders.append(p.as_posix())
    assert offenders == [], f"remove na/eu region defaults from: {offenders}"


def test_shipped_criteria_have_no_retired_geo_penalty():
    offenders = [p.as_posix() for p in _TEMPLATES if re.search(r"^\s*geo_penalty\b", p.read_text(), re.M)]
    assert offenders == [], f"remove the retired geo_penalty line from: {offenders}"
