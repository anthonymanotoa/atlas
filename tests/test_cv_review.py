"""engine/cv/review.py — dump del CV tailoreado + (Task 7) apply_edit/resolve_flag."""

from __future__ import annotations

import pytest
import yaml

import engine.paths as paths
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    with DB(tmp_path / "t.db") as d:
        d.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="Data Scientist",
                company="Acme",
                url="https://x/1",
                description="We need Python and SQL for analytics.",
            )
        )
        yield d


def test_dump_tailored_cv_writes_parseable_yaml(db):
    from engine.cv.review import dump_tailored_cv

    jid = db.list_jobs()[0]["id"]
    path = dump_tailored_cv(db, jid)
    assert path.name == "cv_for_review.yaml"
    cv = yaml.safe_load(path.read_text())
    assert isinstance(cv, dict)  # estructura de master_cv tailoreada


def test_dump_unknown_job_raises(db):
    from engine.cv.review import dump_tailored_cv

    with pytest.raises(ValueError):
        dump_tailored_cv(db, "nope")
