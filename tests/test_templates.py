"""Boundary tests for the outreach length caps and phrasing helpers.

The drafts have hard limits (cold email ≤125 words, LinkedIn note ≤180 chars).
These pin the cap behavior so a future edit can't silently blow past them.
"""

from __future__ import annotations

from engine.outreach.templates import _linkedin_note, _skills_phrase, _word_cap


def test_word_cap_at_boundary():
    exactly = " ".join(["w"] * 125)
    assert _word_cap(exactly) == exactly  # 125 words: unchanged
    assert not _word_cap(exactly).endswith("…")

    over = " ".join(["w"] * 126)
    capped = _word_cap(over)
    assert capped.endswith("…")
    assert len(capped.rstrip("…").split()) == 125  # truncated to 125 words


def test_linkedin_note_respects_180_char_cap():
    long_company = "A" * 120
    long_role = "B" * 120
    for lang in ("en", "es"):
        note = _linkedin_note(long_company, long_role, lang)
        assert len(note) <= 180
        assert note.endswith("…")

    short = _linkedin_note("Acme", "Data Scientist", "en")
    assert len(short) <= 180
    assert not short.endswith("…")  # short note kept intact


def test_skills_phrase_forms():
    assert _skills_phrase([]) == "my core skills"  # domain-neutral fallback
    assert _skills_phrase([], language="es") == "mis competencias clave"
    assert _skills_phrase(["python"]) == "Python"
    assert _skills_phrase(["python", "sql", "aws"]) == "Python, SQL and AWS"  # Oxford-style, n=3
    assert _skills_phrase(["AutoCAD", "Revit"]) == "AutoCAD and Revit"  # preserves given casing
