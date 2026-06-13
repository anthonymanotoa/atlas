"""P1-B CSV export: column resolution, CSV generation, download-dir validation."""

from __future__ import annotations

import pytest

from engine import export


def test_resolve_columns_precedence():
    # explicit request wins (bogus ids dropped)
    assert export.resolve_columns(["title", "bogus"], None) == ["title"]
    # saved selection used when no explicit request
    assert export.resolve_columns(None, '["company","title"]') == ["company", "title"]
    # default (yaml or fallback) is non-empty and valid
    assert export.resolve_columns(None, None)


def test_generate_csv_header_and_values():
    jobs = [
        {
            "title": "DS",
            "company": "Acme",
            "salary_min": 100000,
            "salary_max": 120000,
            "salary_currency": "USD",
            "salary_interval": "yearly",
            "sources_json": '["greenhouse"]',
        }
    ]
    text = export.generate_csv(jobs, ["title", "company", "salary", "sources"])
    lines = text.splitlines()
    assert lines[0] == "Puesto,Empresa,Salario,Fuentes"
    assert lines[1].startswith("DS,Acme,")
    assert "100000–120000 USD/yearly" in lines[1]
    assert "greenhouse" in lines[1]


def test_generate_csv_falls_back_when_no_valid_columns():
    text = export.generate_csv([], ["bogus"])
    # header still renders from the fallback column set
    assert text.splitlines()[0]


def test_validate_download_dir_creates_and_rejects_file(tmp_path):
    out = export.validate_download_dir(str(tmp_path / "exports"))
    assert (tmp_path / "exports").is_dir() and out.endswith("exports")
    f = tmp_path / "afile"
    f.write_text("x")
    with pytest.raises(ValueError):
        export.validate_download_dir(str(f))
