"""The imported-CV draft scaffold is per-domain: an architecture import surfaces the
licensure / pitch / portfolio fields to fill; data is unchanged."""

from __future__ import annotations

import yaml

from engine.cv.import_cv import build_draft


def test_architecture_draft_scaffold_has_licensure_and_pitch():
    data = yaml.safe_load(build_draft("texto extraído", domain="architecture"))
    assert "licensure" in data
    assert "pitch" in data["basics"]
    assert "portfolio" in data["basics"]
    assert data["_source_text"] == "texto extraído"


def test_data_draft_scaffold_unchanged():
    data = yaml.safe_load(build_draft("texto", domain="data"))
    assert "licensure" not in data
    assert data["basics"].get("name") == ""
