"""Demo-tagged ATS sources (pipeline-validation boards) must never pollute a real
profile's discover() run unless explicitly opted in via include_demo: true."""

from __future__ import annotations

from engine.config import CompanyTarget
from engine.db.models import DB
from engine.discovery.runner import partition_demo, discover


def test_partition_excludes_demo_by_default():
    demo_co = CompanyTarget(company="DemoCo", ats="lever", token="x", demo=True)
    real_co = CompanyTarget(company="RealCo", ats="lever", token="y")

    active, skipped = partition_demo([demo_co, real_co], include_demo=False)

    assert active == [real_co]
    assert skipped == ["DemoCo"]


def test_partition_includes_demo_when_flagged():
    demo_co = CompanyTarget(company="DemoCo", ats="lever", token="x", demo=True)
    real_co = CompanyTarget(company="RealCo", ats="lever", token="y")

    active, skipped = partition_demo([demo_co, real_co], include_demo=True)

    assert active == [demo_co, real_co]
    assert skipped == []


def test_discover_skips_demo_and_records_it():
    db = DB(":memory:")
    db.init_schema()

    demo_co = CompanyTarget(company="DemoCo", ats="lever", token="x", demo=True)
    summary = discover(
        db,
        sources_cfg={"ats": {"enabled": True}},
        companies=[demo_co],
        only={"ats"},
    )

    assert summary["skipped_demo"] == ["DemoCo"]
    assert not any("DemoCo" in label for label in summary["sources"])
