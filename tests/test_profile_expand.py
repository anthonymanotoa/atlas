"""engine/profile_expand.py — aplicación aditiva/idempotente al YAML del perfil (F4 §7.2).

apply_items escribe SOLO los ítems confirmados al master_cv (ruta gitignoreada), es aditivo
(nunca pisa lo existente) e idempotente (aplicar dos veces no duplica). El writer valida el
JSON de ítems propuestos por el brain (target/value/source) y persiste el borrador. $0: no hay
LLM en el backend/engine — el escaneo lo hace el brain; esto es mutación determinista de YAML.
"""

from __future__ import annotations

import pytest
import yaml

import engine.paths as paths
from engine import intents
from engine.db.models import DB


@pytest.fixture
def db(tmp_path, monkeypatch):
    # perfil gitignored simulado: un master_cv.yaml en un dir temporal
    master = tmp_path / "master_cv.yaml"
    master.write_text(
        yaml.safe_dump(
            {
                "basics": {"name": "Ada"},
                "skills": ["Python", "SQL"],
                "experience": [{"company": "Example Corp", "title": "SWE", "highlights": []}],
                "projects": [],
                "certifications": [],
            },
            sort_keys=False,
        )
    )
    monkeypatch.setattr(paths, "MASTER_CV_PATH", master)
    # apply_items abre su propio `with DB()` (lee paths.DB_PATH tarde), así que lo apuntamos
    # a la misma DB temporal que crea el fixture — de lo contrario abriría otra base.
    db_path = tmp_path / "t.db"
    monkeypatch.setattr(paths, "DB_PATH", db_path)
    with DB(db_path) as d:
        yield d


def _items() -> list[dict]:
    return [
        {"target": "skills", "value": "Rust", "source": "github.com/ada/ripgrep-fork"},
        {"target": "skills", "value": "Python", "source": "github (ya existe)"},  # idempotente
        {
            "target": "certification",
            "value": {"name": "CKA", "issuer": "CNCF", "date": "2026"},
            "source": "cncf.io/certification/cka",
        },
    ]


def test_expand_writer_persists_draft(db):
    iid = intents.enqueue(db, "profile_expand", {"github_user": "ada"})
    intents.mark_running(db, iid)
    ref = intents.apply_result(db, iid, {"items": _items()})
    assert ref.startswith("profile_expansion:")
    exp = db.list_profile_expansions()[0]
    assert len(exp["items"]) == 3
    # nada tocó el YAML todavía (solo draft)
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert cv["skills"] == ["Python", "SQL"]


def test_expand_writer_rejects_bad_target(db):
    iid = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid, {"items": [{"target": "salary", "value": "1M", "source": "dreams"}]}
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_expand_writer_rejects_empty_items(db):
    iid = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"items": []})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_expand_writer_rejects_missing_source(db):
    iid = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid, {"items": [{"target": "skills", "value": "Rust", "source": "  "}]}
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_expand_writer_rejects_empty_value(db):
    iid = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid, {"items": [{"target": "skills", "value": "", "source": "github.com/ada"}]}
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_items_is_additive_and_idempotent(db):
    from engine.profile_expand import apply_items

    exp_id = db.add_profile_expansion(intent_id=None, items=_items())
    out = apply_items(exp_id, [0, 1, 2])  # incluye el "Python" ya existente
    assert out["ok"] and out["applied"] == 2 and out["skipped_existing"] == 1
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert "Rust" in cv["skills"]
    assert cv["skills"].count("Python") == 1  # no duplicó
    assert any(c["name"] == "CKA" for c in cv["certifications"])
    # re-aplicar es idempotente
    again = apply_items(exp_id, [0])
    assert again["applied"] == 0 and again["skipped_existing"] == 1
    assert db.get_profile_expansion(exp_id)["items"][0]["applied"] is True


def test_apply_items_never_touches_unconfirmed(db):
    """Solo los índices confirmados se escriben; los omitidos quedan intactos y re-ofrecibles."""
    from engine.profile_expand import apply_items

    exp_id = db.add_profile_expansion(intent_id=None, items=_items())
    out = apply_items(exp_id, [0])  # solo Rust
    assert out["applied"] == 1 and out["skipped_existing"] == 0
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert "Rust" in cv["skills"]
    # la certificación NO confirmada no se escribió
    assert cv["certifications"] == []
    stored = db.get_profile_expansion(exp_id)["items"]
    assert stored[0]["applied"] is True
    assert "applied" not in stored[2] or stored[2].get("applied") is not True


def test_apply_items_additive_preserves_existing_cv(db):
    """Nunca pisa/borra el CV existente del usuario — solo agrega."""
    from engine.profile_expand import apply_items

    exp_id = db.add_profile_expansion(intent_id=None, items=_items())
    apply_items(exp_id, [0, 2])
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert cv["basics"] == {"name": "Ada"}  # intacto
    assert "Python" in cv["skills"] and "SQL" in cv["skills"]  # preexistentes intactos
    assert cv["experience"][0]["company"] == "Example Corp"  # intacto


def test_apply_items_rejects_out_of_range_index(db):
    from engine.profile_expand import apply_items

    exp_id = db.add_profile_expansion(intent_id=None, items=_items())
    with pytest.raises(ValueError):
        apply_items(exp_id, [99])


def test_apply_items_unknown_expansion_raises(db):
    from engine.profile_expand import apply_items

    with pytest.raises(ValueError):
        apply_items(9999, [0])


def test_apply_items_experience_highlight_and_project(db):
    """Los targets experience_highlight y project también son aditivos/idempotentes."""
    from engine.profile_expand import apply_items

    items = [
        {
            "target": "experience_highlight",
            "value": {"company": "Example Corp", "highlight": "Shipped X to 1M users"},
            "source": "github.com/ada/x",
        },
        {
            "target": "project",
            "value": {"name": "ripgrep-fork", "description": "A faster grep"},
            "source": "github.com/ada/ripgrep-fork",
        },
    ]
    exp_id = db.add_profile_expansion(intent_id=None, items=items)
    out = apply_items(exp_id, [0, 1])
    assert out["applied"] == 2
    cv = yaml.safe_load(paths.MASTER_CV_PATH.read_text())
    assert "Shipped X to 1M users" in cv["experience"][0]["highlights"]
    assert any(p["name"] == "ripgrep-fork" for p in cv["projects"])
    # idempotente
    again = apply_items(exp_id, [0, 1])
    assert again["applied"] == 0 and again["skipped_existing"] == 2
