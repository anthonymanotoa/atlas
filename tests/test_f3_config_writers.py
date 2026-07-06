"""F3: cadencia configurable + writers de criteria/companies (escriben SOLO rutas del perfil)."""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError


@pytest.fixture
def cfg_env(tmp_path, monkeypatch):
    """Config aislada en tmp_path: reapunta las rutas del perfil a un dir temporal.

    Las rutas se leen tarde (``paths.CRITERIA_PATH`` en tiempo de llamada), así que basta
    con monkeypatch-ear los globals de ``engine.paths`` — NO recargamos ``engine.config``:
    un ``importlib.reload`` reasigna la clase ``Criteria`` a un objeto nuevo y contamina a
    los tests que la importaron a nivel de módulo (su ``==`` compara clases distintas).
    """
    import engine.config
    import engine.paths

    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("ATLAS_PROFILE", raising=False)
    monkeypatch.setattr(engine.paths, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(engine.paths, "CRITERIA_PATH", tmp_path / "config" / "criteria.md")
    monkeypatch.setattr(engine.paths, "COMPANIES_PATH", tmp_path / "config" / "companies.yaml")
    return engine.config


def test_followup_cadence_defaults(cfg_env):
    c = cfg_env.Criteria()
    assert c.followup_cadence["applied"] == {"days": 7, "max_touches": 2}
    assert c.followup_cadence["responded"] == {"days": 1, "max_touches": 1}
    assert c.followup_cadence["interview"] == {"days": 1, "max_touches": 1}


def test_followup_cadence_round_trips_through_markdown(cfg_env):
    c = cfg_env.Criteria(followup_cadence={"applied": {"days": 5, "max_touches": 3}})
    text = cfg_env.criteria_to_markdown(c)
    meta, _prose = cfg_env._split_frontmatter(text)
    back = cfg_env.Criteria(**meta)
    assert back.followup_cadence == {"applied": {"days": 5, "max_touches": 3}}


def test_update_criteria_fields_patches_frontmatter_preserving_prose(cfg_env):
    import engine.paths as paths

    paths.CRITERIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.CRITERIA_PATH.write_text(
        "---\nroles: [data scientist]\nshortlist_threshold: 60\n---\n\nProsa para el brain.\n"
    )
    merged = cfg_env.update_criteria_fields({"shortlist_threshold": 68.0})
    assert merged.shortlist_threshold == 68.0
    text = paths.CRITERIA_PATH.read_text()
    assert "shortlist_threshold: 68" in text
    assert "Prosa para el brain." in text  # la prosa sobrevive
    assert "data scientist" in text  # los campos no tocados sobreviven
    assert cfg_env.load_criteria().shortlist_threshold == 68.0


def test_update_criteria_fields_rejects_non_writable(cfg_env):
    with pytest.raises(ValueError):
        cfg_env.update_criteria_fields({"roles": ["hacker"]})


def test_update_criteria_fields_validates_before_writing(cfg_env):
    import engine.paths as paths

    paths.CRITERIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.CRITERIA_PATH.write_text("---\nshortlist_threshold: 60\n---\n\nx\n")
    with pytest.raises(ValidationError):  # pydantic rechaza el tipo
        cfg_env.update_criteria_fields({"shortlist_threshold": "not-a-number"})
    assert "60" in paths.CRITERIA_PATH.read_text()  # el archivo NO cambió


def test_save_company_appends_and_dedupes(cfg_env):
    import engine.paths as paths

    entry = {"company": "Acme Robotics", "ats": "greenhouse", "token": "acmerobotics"}
    assert cfg_env.save_company(entry) is True
    assert cfg_env.save_company(entry) is False  # dup exacto
    assert (
        cfg_env.save_company({"company": "ACME ROBOTICS", "ats": "lever", "token": "x"}) is False
    )  # dup por nombre
    data = yaml.safe_load(paths.COMPANIES_PATH.read_text())
    assert len(data["companies"]) == 1
    assert data["companies"][0]["token"] == "acmerobotics"
    loaded = cfg_env.load_companies()
    assert loaded and loaded[0].ats == "greenhouse"


def test_save_company_dedupes_by_ats_and_token(cfg_env):
    assert cfg_env.save_company({"company": "Foo", "ats": "greenhouse", "token": "shared"}) is True
    # Different name, same ats+token → treated as the same board, rejected.
    assert cfg_env.save_company({"company": "Bar", "ats": "greenhouse", "token": "shared"}) is False


def test_save_company_rejects_invalid_entry(cfg_env):
    with pytest.raises(ValidationError):  # pydantic: falta company/ats
        cfg_env.save_company({"token": "x"})


def test_load_discovery_seeds_empty_when_absent(cfg_env):
    assert cfg_env.load_discovery_seeds() == []


def test_load_discovery_seeds_reads_candidates(cfg_env):
    import engine.paths as paths

    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (paths.CONFIG_DIR / "discovery_seeds.yaml").write_text(
        "candidates:\n  - Acme Robotics\n  - '  Globex  '\n  - ''\n"
    )
    assert cfg_env.load_discovery_seeds() == ["Acme Robotics", "Globex"]
