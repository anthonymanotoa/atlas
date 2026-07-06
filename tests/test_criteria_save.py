"""criteria.md writer: frontmatter round-trips through the Criteria model (F2 wizard)."""

from __future__ import annotations

import engine.paths as paths
from engine.config import (
    Criteria,
    _split_frontmatter,
    criteria_to_markdown,
    load_criteria,
    save_criteria,
)


def test_markdown_has_frontmatter_and_prose():
    c = Criteria(roles=["data engineer"], candidate_country="ec", prose="# Mi búsqueda\nTexto.")
    md = criteria_to_markdown(c)
    assert md.startswith("---\n")
    assert "candidate_country: ec" in md
    assert md.rstrip().endswith("Texto.")
    assert "prose:" not in md  # prose is the body, never a frontmatter key


def test_markdown_roundtrips_through_split_frontmatter():
    """criteria_to_markdown(load_criteria()) parses back to an equivalent Criteria + prose."""
    c = load_criteria()
    md = criteria_to_markdown(c)
    meta, prose = _split_frontmatter(md)
    meta["prose"] = prose
    c2 = Criteria(**meta)
    # Lossless for BOTH frontmatter and prose.
    assert c2 == c
    assert c2.prose.strip() == c.prose.strip()


def test_save_and_reload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "config" / "criteria.md")
    c = Criteria(
        roles=["data engineer"],
        candidate_country="ec",
        acceptable_regions=["latam"],
        geo_penalty=15.0,
        re_apply_window_days=14,
        prose="# Mi búsqueda",
    )
    written = save_criteria(c)
    assert written == tmp_path / "config" / "criteria.md" and written.exists()
    c2 = load_criteria()
    assert c2.roles == ["data engineer"]
    assert c2.candidate_country == "ec"
    assert c2.acceptable_regions == ["latam"]
    assert c2.geo_penalty == 15.0
    assert c2.re_apply_window_days == 14
    assert "Mi búsqueda" in c2.prose


def test_save_writes_to_profile_path_not_example(tmp_path, monkeypatch):
    """save_criteria writes CRITERIA_PATH itself, never the committed `.example` fallback."""
    target = tmp_path / "config" / "criteria.md"
    monkeypatch.setattr(paths, "CRITERIA_PATH", target)
    save_criteria(Criteria(roles=["data engineer"]))
    assert target.exists()
    # The `.example` sibling must NOT be created by a save.
    assert not target.with_name("criteria.example.md").exists()
