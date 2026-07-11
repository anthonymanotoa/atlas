"""Deterministic template-identity detector for master_cv.yaml.

The seed master CV ships with the "Ada Lovelace" placeholder identity. Anything
generated from it (tailored CVs, outreach, portfolio) is unusable. This module is
the single source of truth for "is this CV still the template?".
"""

from __future__ import annotations

PLACEHOLDER_NAMES = {"ada lovelace"}
PLACEHOLDER_DOMAINS = ("example.com", "example.org")
PLACEHOLDER_URL_FRAGMENTS = ("linkedin.com/in/example", "github.com/example")


def find_placeholders(cv: dict) -> list[str]:
    findings: list[str] = []
    basics = cv.get("basics") or {}
    name = (basics.get("name") or "").strip()
    if not name:
        findings.append("basics.name vacío")
    elif name.lower() in PLACEHOLDER_NAMES:
        findings.append(f"basics.name es la plantilla: {name!r} (Ada Lovelace)")
    email = (basics.get("email") or "").lower()
    if any(d in email for d in PLACEHOLDER_DOMAINS):
        findings.append(f"basics.email usa dominio de ejemplo: {email!r} (example.com)")
    for key in ("linkedin", "github", "website"):
        val = (basics.get(key) or "").lower()
        if any(frag in val for frag in PLACEHOLDER_URL_FRAGMENTS) or any(
            d in val for d in PLACEHOLDER_DOMAINS
        ):
            findings.append(f"basics.{key} es URL de ejemplo: {val!r}")
    return findings


def is_template_cv(cv: dict) -> bool:
    return bool(find_placeholders(cv))
