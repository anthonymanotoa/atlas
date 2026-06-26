"""P1-A quality gates: language detection, salary/date parsing, scoring refinements, annotate."""

from __future__ import annotations

from datetime import UTC, datetime

from engine import analytics
from engine.config import Criteria
from engine.discovery.ats.ashby import _parse_salary_string, _salary_from_comp
from engine.discovery.ats.lever import _date_from_ms
from engine.lang import detect_language
from engine.scoring.fit import score_job


# ── language detection ────────────────────────────────────────────────────────
def test_detect_language_en_es_and_weak():
    assert (
        detect_language(
            "We are looking for a senior data scientist with experience in Python and our team"
        )
        == "en"
    )
    assert (
        detect_language(
            "Buscamos un científico de datos senior con experiencia en Python y conocimientos "
            "para el equipo y el puesto"
        )
        == "es"
    )
    assert detect_language("kurz") is None  # not enough signal


# ── lever date_posted ─────────────────────────────────────────────────────────
def test_lever_date_from_ms():
    assert _date_from_ms(1700000000000) == "2023-11-14"  # epoch ms → ISO date
    assert _date_from_ms(None) is None
    assert _date_from_ms("nope") is None


# ── ashby salary ──────────────────────────────────────────────────────────────
def test_ashby_salary_structured():
    comp = {
        "summaryComponents": [
            {
                "componentType": "Salary",
                "interval": "1 YEAR",
                "currencyCode": "USD",
                "minValue": 120000,
                "maxValue": 160000,
            }
        ]
    }
    assert _salary_from_comp(comp) == (120000, 160000, "USD", "yearly")


def test_ashby_salary_string_fallback():
    mn, mx, cur, _interval = _parse_salary_string("$120K – $160K • Offers Equity")
    assert (mn, mx, cur) == (120000, 160000, "USD")
    assert _parse_salary_string("competitive salary") == (None, None, None, None)


# ── scoring refinements ───────────────────────────────────────────────────────
def _crit(**kw) -> Criteria:
    base: dict = {"roles": ["data scientist"], "remote_required": False, "languages": ["en", "es"]}
    base.update(kw)
    return Criteria(**base)


def test_scoring_exec_is_overqualified_dq():
    r = score_job(
        {"title": "VP of Data", "description": "lead the org", "company": "Acme"}, _crit()
    )
    assert r.disqualified
    assert any("over-qualified" in k for k in r.knockouts)


def test_scoring_company_blocklist():
    r = score_job(
        {"title": "Senior Data Scientist", "description": "python", "company": "Evil Corp Inc"},
        _crit(company_blocklist=["evil corp"]),
    )
    assert r.disqualified and r.score == 0.0


def test_scoring_freshness_downranks_stale():
    today = datetime.now(UTC).date().isoformat()
    base = {"title": "Senior Data Scientist", "description": "python sql", "company": "Acme"}
    stale = score_job({**base, "date_posted": "2000-01-01"}, _crit(max_age_days=30))
    fresh = score_job({**base, "date_posted": today}, _crit(max_age_days=30))
    assert fresh.score > stale.score


def test_scoring_language_penalty_uses_stored_language():
    r = score_job(
        {"title": "Data Scientist", "description": "x", "company": "Acme", "language": "de"},
        _crit(),
    )
    assert any("de-language" in reason for reason in r.reasons)


def test_scoring_flags_excessive_years():
    r = score_job(
        {
            "title": "Senior Data Scientist",
            "description": "Requires 15+ years of experience",
            "company": "Acme",
        },
        _crit(max_years_required=10),
    )
    assert any("15+ years" in k for k in r.knockouts)


# ── seniority-fit realism (P4): Staff/Principal + years-gap awareness ──────────
def _remote_job(title: str, desc: str) -> dict:
    return {
        "title": title,
        "description": desc,
        "company": "Acme",
        "is_remote": 1,
        "workplace_type": "remote",
    }


def test_staff_title_is_a_stretch_not_a_bonus():
    """A Staff/Principal IC role is over-qualified for a ~5yr candidate: flagged and held
    below the shortlist threshold, never bonused (the 'Staff Engineer wants 15 yrs' case)."""
    crit = _crit(candidate_years=5, remote_required=True, shortlist_threshold=62)
    staff = score_job(_remote_job("Staff Data Scientist", "python sql. 10+ years."), crit)
    senior = score_job(_remote_job("Senior Data Scientist", "python sql. 4+ years."), crit)
    assert senior.score >= crit.shortlist_threshold  # realistic → shortlistable
    assert staff.score < crit.shortlist_threshold  # stretch → browse-only, not shortlisted
    assert any("staff" in k for k in staff.knockouts)  # label derives from the matched term


def test_large_years_gap_softcaps_even_a_senior_title():
    crit = _crit(candidate_years=5, remote_required=True, shortlist_threshold=62)
    r = score_job(
        _remote_job("Senior Data Scientist", "python sql. 15+ years of experience required."),
        crit,
    )
    assert r.score < crit.shortlist_threshold
    assert any("años" in k for k in r.knockouts)


def test_small_years_gap_stays_shortlistable():
    crit = _crit(candidate_years=5, remote_required=True, shortlist_threshold=62)
    r = score_job(_remote_job("Senior Data Scientist", "python sql. 7+ years."), crit)
    assert r.score >= crit.shortlist_threshold  # 7 vs 5 = within reach, no realism penalty


# ── analytics.annotate ────────────────────────────────────────────────────────
def test_annotate_salary_visible_and_posted_days():
    job = {
        "discovered_at": "2026-06-10T00:00:00+00:00",
        "date_posted": "2026-06-01",
        "salary_min": 100000,
    }
    analytics.annotate(job)
    assert job["salary_visible"] is True
    assert job["posted_days"] is not None

    bare = {"discovered_at": "2026-06-10T00:00:00+00:00"}
    analytics.annotate(bare)
    assert bare["salary_visible"] is False
