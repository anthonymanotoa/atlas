"""Small shared utilities (HTML→text, salary coercion)."""

from __future__ import annotations

import html
import re
from typing import Any

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</(p|div|li|h[1-6]|br|tr)\s*>", re.I)
_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n\s*\n\s*\n+")


def html_to_text(s: str | None) -> str:
    """Convert HTML (as returned by ATS feeds) to readable plain text."""
    if not s:
        return ""
    s = _BLOCK.sub("\n", s)
    s = re.sub(r"<li[^>]*>", "\n• ", s, flags=re.I)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = _WS.sub(" ", s)
    s = _NL.sub("\n\n", s)
    return s.strip()


def to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def canonical_salary_interval(raw: str | None) -> str | None:
    """Normalize a source's salary-interval string to a canonical token.

    Sources are inconsistent: Lever emits 'per-year-salary'/'per-month-salary'/'per-hour-wage',
    others emit 'annually'/'yearly'/'monthly'/'hourly'. Returns one of
    hourly|daily|weekly|monthly|yearly (matching scoring.fit's multiplier map) or None.
    """
    if not raw:
        return None
    s = str(raw).lower()
    if "hour" in s:
        return "hourly"
    if "week" in s:
        return "weekly"
    if "month" in s:
        return "monthly"
    if "year" in s or "annum" in s or "annual" in s:
        return "yearly"
    if "day" in s or "dai" in s:  # "per-day-wage" and the bare token "daily" both → daily
        return "daily"
    return None


def first(*vals: Any) -> Any:
    for v in vals:
        if v not in (None, "", []):
            return v
    return None
