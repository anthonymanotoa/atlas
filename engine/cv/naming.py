"""Human-readable, ATS-safe filenames + the per-profile CV library folder.

Two problems this solves:
  1. Downloads were all called ``cv_en.pdf`` — impossible to tell which company a saved CV
     was for. Every download now gets a name like
     ``Ada_Lovelace__Acme_Inc__Senior_Data_Scientist__en.pdf``.
  2. There was no single place to browse every tailored CV. Each ``build_for_job`` now drops a
     nicely-named copy into ``data/outbox/cv_library/`` (per profile), so the user has one
     folder with all their CVs, clearly labelled.

Filenames are transliterated to ASCII + ``[A-Za-z0-9_]`` only, so they're safe on every OS and
for every ATS upload widget.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

import engine.paths as paths

_BAD = re.compile(r"[^A-Za-z0-9]+")


def slug(s: str | None, maxlen: int = 40) -> str:
    """Transliterate to ASCII and collapse to ``Word_Word`` (no accents, spaces or punctuation)."""
    text = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    text = _BAD.sub("_", text).strip("_")
    return text[:maxlen].strip("_")


def cv_filename(
    cv_name: str | None,
    company: str | None,
    title: str | None,
    language: str,
    fmt: str,
) -> str:
    """``Name__Company__Role__lang.fmt`` — the naming convention for every downloaded/saved CV."""
    parts = [slug(cv_name, 30), slug(company, 30), slug(title, 45), slug(language, 4) or "en"]
    stem = "__".join(p for p in parts if p) or "cv"
    ext = (fmt or "pdf").lower().lstrip(".")
    return f"{stem}.{ext}"


def library_dir() -> Path:
    """The active profile's CV library folder (created on demand)."""
    d = paths.OUTBOX_DIR / "cv_library"
    d.mkdir(parents=True, exist_ok=True)
    return d


def copy_to_library(
    src: Path,
    *,
    cv_name: str | None,
    company: str | None,
    title: str | None,
    language: str,
    fmt: str,
) -> Path | None:
    """Copy a rendered CV into the library under its human-readable name. Best-effort."""
    try:
        if not src or not Path(src).exists():
            return None
        dest = library_dir() / cv_filename(cv_name, company, title, language, fmt)
        shutil.copy2(str(src), str(dest))
        return dest
    except OSError:
        return None
