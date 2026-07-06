"""Deterministic geo-restriction extraction for remote postings (spec §5.2 / §8 corpus)."""

from __future__ import annotations

from engine.normalize import Job, extract_geo_restriction


# ── The mandatory corpus from the spec (§8) ──────────────────────────────────
def test_remote_us_only_location():
    raw, scope = extract_geo_restriction("Remote — US only", "", True)
    assert scope == "us"
    assert raw == "Remote — US only"


def test_remote_must_be_uk_based_location():
    raw, scope = extract_geo_restriction("Remote (must be UK-based)", "", True)
    assert scope == "gb"
    assert raw == "Remote (must be UK-based)"


def test_remote_latam_location():
    assert extract_geo_restriction("Remote LatAm", "", True)[1] == "latam"


def test_remote_worldwide_location():
    assert extract_geo_restriction("Remote worldwide", "", True)[1] == "worldwide"


def test_remote_without_restriction_is_unknown():
    assert extract_geo_restriction("Remote", "Great team, async culture.", True) == (
        None,
        "unknown",
    )


def test_onsite_is_not_applicable():
    assert extract_geo_restriction("Quito, Ecuador", "on-site role", False) == (None, "")


# ── Description-body patterns ────────────────────────────────────────────────
def test_must_reside_in():
    raw, scope = extract_geo_restriction(
        "Remote", "You must reside in the United States to apply.", True
    )
    assert scope == "us"
    assert raw == "must reside in the United States"


def test_must_be_based_in():
    assert (
        extract_geo_restriction("Remote", "Candidates must be based in Germany.", True)[1] == "de"
    )


def test_eligible_to_work_in():
    assert extract_geo_restriction("Remote", "Must be eligible to work in Canada.", True)[1] == "ca"


def test_authorized_to_work_in():
    assert (
        extract_geo_restriction("Remote", "You are authorized to work in the UK.", True)[1] == "gb"
    )


def test_remote_paren_us():
    assert extract_geo_restriction("", "This role is Remote (US).", True)[1] == "us"


def test_remote_dash_usa_location():
    assert extract_geo_restriction("Remote - USA", "", True)[1] == "us"


def test_within_the_eu():
    assert extract_geo_restriction("Remote", "You are located within the EU.", True)[1] == "eu"


def test_country_only_suffix_in_description():
    raw, scope = extract_geo_restriction("Remote", "Open to Brazil only.", True)
    assert scope == "br"


def test_specific_country_in_remote_location():
    # A remote job whose location names a country IS a restriction signal (spec §5.2).
    assert extract_geo_restriction("Remote - Poland", "", True)[1] == "pl"


def test_uppercase_iso2_code_in_location():
    assert extract_geo_restriction("Remote - Quito, EC", "", True)[1] == "ec"


def test_lowercase_word_us_never_matches_description():
    # "join us" must never read as a US restriction — description matches are anchored.
    assert extract_geo_restriction("Remote", "Come join us on our mission!", True)[1] == "unknown"


# ── Job.finalize wiring ──────────────────────────────────────────────────────
def test_finalize_fills_geo_fields():
    j = Job(
        source="himalayas",
        title="Data Engineer",
        company="Acme",
        location="Remote — US only",
        is_remote=True,
    ).finalize()
    assert j.geo_scope == "us"
    assert j.geo_restriction == "Remote — US only"


def test_finalize_onsite_gets_empty_scope():
    j = Job(
        source="indeed",
        title="Data Engineer",
        company="Acme",
        location="Berlin, Germany",
        is_remote=False,
        workplace_type="onsite",
    ).finalize()
    assert j.geo_scope == ""
    assert j.geo_restriction is None
