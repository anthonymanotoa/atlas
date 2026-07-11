"""Shortlist variant collapse (Task 9): near-identical reposts of the SAME role should not
flood the top-of-shortlist with 5 near-duplicate CVS Health cards. `collapse_variants` groups
by the SAME key `sweep_reposts` uses — (norm_company, core_title) — so collapse stays
consistent with the repost detector."""

from __future__ import annotations

from engine.scoring.dedupe import collapse_variants


def _job(id_, title, company, fit, discovered_at="2026-07-01T00:00:00+00:00", **extra):
    return {
        "id": id_,
        "title": title,
        "company": company,
        "fit_score": fit,
        "discovered_at": discovered_at,
        **extra,
    }


def test_collapses_five_same_company_variants():
    # Near-identical titles that must share a core_title (seniority/modality stripped).
    jobs = [
        _job("j1", "Data Analyst", "CVS Health", 88),
        _job("j2", "Data Analyst II", "CVS Health", 90),
        _job("j3", "Senior Data Analyst", "CVS Health", 92),
        _job("j4", "Data Analyst (Remote)", "CVS Health", 89),
        _job("j5", "Sr. Data Analyst - Hybrid", "CVS Health", 91),
    ]
    out = collapse_variants(jobs)
    assert len(out) == 1
    assert out[0]["variant_count"] == 5
    assert out[0]["id"] == "j3"  # highest fit (92) wins canonical
    assert set(out[0]["variant_ids"]) == {"j1", "j2", "j3", "j4", "j5"}
    assert out[0]["variant_ids"][0] == "j3"  # canonical first


def test_distinct_companies_not_collapsed():
    jobs = [
        _job("a1", "Data Analyst", "CVS Health", 90),
        _job("b1", "Data Analyst", "Walgreens", 90),
    ]
    out = collapse_variants(jobs)
    assert len(out) == 2
    for j in out:
        assert j["variant_count"] == 1
        assert j["variant_ids"] == [j["id"]]


def test_canonical_is_highest_fit():
    jobs = [
        _job("low", "Data Analyst", "Acme", 70),
        _job("high", "Data Analyst II", "Acme", 95),
        _job("mid", "Senior Data Analyst", "Acme", 80),
    ]
    out = collapse_variants(jobs)
    assert len(out) == 1
    assert out[0]["id"] == "high"
    assert out[0]["variant_count"] == 3


def test_none_fit_score_treated_as_lowest():
    jobs = [
        _job("no_fit", "Data Analyst", "Acme", None),
        _job("has_fit", "Data Analyst II", "Acme", 50),
    ]
    out = collapse_variants(jobs)
    assert len(out) == 1
    assert out[0]["id"] == "has_fit"


def test_tie_break_most_recent_discovered_at():
    jobs = [
        _job("older", "Data Analyst", "Acme", 90, discovered_at="2026-01-01T00:00:00+00:00"),
        _job("newer", "Data Analyst II", "Acme", 90, discovered_at="2026-06-01T00:00:00+00:00"),
    ]
    out = collapse_variants(jobs)
    assert len(out) == 1
    assert out[0]["id"] == "newer"


def test_does_not_mutate_input():
    jobs = [_job("solo", "Data Analyst", "Acme", 90)]
    out = collapse_variants(jobs)
    assert "variant_count" not in jobs[0]
    assert out[0] is not jobs[0]


def test_group_order_follows_input_order_of_canonical():
    # "Acme" group's canonical (b, fit 99) appears AFTER "Zed" in input order, but "Zed"'s
    # canonical comes first in the input overall, so Zed's group stays first in the output.
    jobs = [
        _job("zed1", "Backend Engineer", "Zed Corp", 60),
        _job("a1", "Data Analyst", "Acme", 50),
        _job("a2", "Data Analyst II", "Acme", 99),
    ]
    out = collapse_variants(jobs)
    assert [j["id"] for j in out] == ["zed1", "a2"]


def test_single_job_has_variant_count_one():
    jobs = [_job("solo", "Data Analyst", "Acme", 90)]
    out = collapse_variants(jobs)
    assert out[0]["variant_count"] == 1
    assert out[0]["variant_ids"] == ["solo"]
