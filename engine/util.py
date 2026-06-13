"""Small shared utilities (HTML→text, salary coercion)."""
from __future__ import annotations

import html
import re
from typing import Any, Optional

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</(p|div|li|h[1-6]|br|tr)\s*>", re.I)
_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n\s*\n\s*\n+")


def html_to_text(s: Optional[str]) -> str:
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


def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def first(*vals: Any) -> Any:
    for v in vals:
        if v not in (None, "", []):
            return v
    return None
