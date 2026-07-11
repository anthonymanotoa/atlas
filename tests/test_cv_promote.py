from pathlib import Path

import pytest
import yaml

from engine.cv.promote import PromoteError, promote_draft

REAL = {
    "basics": {"name": "Jane Roe", "email": "jane@gmail.com", "linkedin": "linkedin.com/in/janeroe"},
    "experience": [{"company": "Acme", "title": "Data Analyst", "start": "2022-01"}],
}


def _profile(tmp_path: Path, draft: dict | None) -> Path:
    prof = tmp_path / "profile"
    prof.mkdir()
    (prof / "master_cv.yaml").write_text(
        yaml.safe_dump({"basics": {"name": "Ada Lovelace", "email": "ada@example.com"}})
    )
    if draft is not None:
        (prof / "master_cv.draft.yaml").write_text(yaml.safe_dump(draft))
    return tmp_path


def test_promote_happy_path(tmp_path):
    root = _profile(tmp_path, REAL)
    out = promote_draft(root)
    promoted = yaml.safe_load(out.read_text())
    assert promoted["basics"]["name"] == "Jane Roe"
    backups = list((root / "profile").glob("master_cv.backup-*.yaml"))
    assert len(backups) == 1


def test_promote_rejects_placeholder_draft(tmp_path):
    root = _profile(tmp_path, {"basics": {"name": "Ada Lovelace", "email": "a@example.com"}})
    with pytest.raises(PromoteError, match="plantilla"):
        promote_draft(root)


def test_promote_rejects_source_text_residue(tmp_path):
    draft = dict(REAL) | {"_source_text": "raw pdf text"}
    root = _profile(tmp_path, draft)
    with pytest.raises(PromoteError, match="_source_text"):
        promote_draft(root)


def test_promote_requires_draft(tmp_path):
    root = _profile(tmp_path, None)
    with pytest.raises(PromoteError, match="draft"):
        promote_draft(root)
