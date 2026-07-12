from pathlib import Path

import pytest
import yaml

from engine.cv.promote import PromoteError, promote_draft

REAL = {
    "basics": {
        "name": "Jane Roe",
        "email": "jane@gmail.com",
        "linkedin": "linkedin.com/in/janeroe",
    },
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


def test_promote_twice_keeps_both_backups(tmp_path, monkeypatch):
    """Two promotions in the same UTC second must not clobber the first backup."""
    root = _profile(tmp_path, REAL)

    # Freeze "now" so both promote_draft calls compute the same timestamp,
    # simulating two promotions within the same UTC second.
    import engine.cv.promote as promote_mod

    frozen = promote_mod.datetime(2026, 1, 1, 12, 0, 0, tzinfo=promote_mod.UTC)

    class _FrozenDatetime(promote_mod.datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr(promote_mod, "datetime", _FrozenDatetime)

    # First promotion: backs up the seeded master_cv.yaml.
    promote_draft(root)

    # Restore a draft for the second promotion (promote_draft consumes nothing,
    # but master_cv.yaml now holds the first draft's content — write a fresh draft
    # so the second promotion has something new to promote).
    draft2 = dict(REAL) | {"basics": dict(REAL["basics"]) | {"name": "John Doe"}}
    (root / "profile" / "master_cv.draft.yaml").write_text(yaml.safe_dump(draft2))

    promote_draft(root)

    backups = sorted((root / "profile").glob("master_cv.backup-*.yaml"))
    assert len(backups) == 2, f"expected 2 distinct backups, found {len(backups)}: {backups}"

    names = sorted(yaml.safe_load(b.read_text())["basics"]["name"] for b in backups)
    assert names == ["Ada Lovelace", "Jane Roe"], (
        f"one of the two backups was clobbered by the other promotion; got {names}"
    )
