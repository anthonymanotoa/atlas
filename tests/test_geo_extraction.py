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


# ── Conservatism: non-restriction prose must stay "unknown" (no false positives) ──
def test_customers_based_in_country_is_unknown():
    # Company/customer-HQ prose is NOT a candidate-residency requirement.
    assert extract_geo_restriction("Remote", "Our customers are based in Germany.", True) == (
        None,
        "unknown",
    )


def test_company_based_in_country_is_unknown():
    assert extract_geo_restriction("Remote", "The company is based in the Netherlands.", True) == (
        None,
        "unknown",
    )


def test_headquarters_based_in_country_is_unknown():
    assert extract_geo_restriction("Remote", "Our headquarters are based in Spain.", True) == (
        None,
        "unknown",
    )


def test_founded_and_based_in_country_is_unknown():
    assert extract_geo_restriction("Remote", "Founded in 2015 and based in Portugal.", True) == (
        None,
        "unknown",
    )


def test_ship_to_customers_country_only_is_unknown():
    # Market/shipping prose ("... in <country> only") is NOT a hiring restriction.
    assert extract_geo_restriction(
        "Remote", "We ship product to customers in France only.", True
    ) == (None, "unknown")


def test_support_clients_country_only_is_unknown():
    assert extract_geo_restriction("Remote", "We support clients in Canada only.", True) == (
        None,
        "unknown",
    )


def test_sell_to_country_only_is_unknown():
    assert extract_geo_restriction(
        "Remote", "We sell to Mexico only through our partners.", True
    ) == (None, "unknown")


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


# ── US-state ↔ ISO-2 collision (Task 1) ──────────────────────────────────────
def test_us_state_code_is_not_read_as_foreign_country():
    # "CO, US" is Colorado, not Colombia — scope must be just "us".
    assert extract_geo_restriction("Remote — CO, US", None, True) == ("Remote — CO, US", "us")
    assert extract_geo_restriction("Remote — PA, US", None, True) == ("Remote — PA, US", "us")
    assert extract_geo_restriction("Remote — DE, US", None, True) == ("Remote — DE, US", "us")


def test_full_country_name_next_to_us_is_kept():
    # "Canada; US" names Canada in full → ca survives even though CA is a state code.
    raw, scope = extract_geo_restriction("Remote, Canada; US", None, True)
    assert set(scope.split(",")) == {"ca", "us"}


def test_bare_state_code_without_us_is_left_alone():
    # No "us" anchor → we don't guess; a lone "CO" still reads as Colombia (rare, low-signal).
    assert extract_geo_restriction("Remote — CO", None, True) == ("Remote — CO", "co")


# ── Evidence priority + worldwide override (Task 2) ──────────────────────────
def test_worldwide_in_body_overrides_a_country_location():
    # "US" in the location but the body says work-from-anywhere → not a US restriction.
    raw, scope = extract_geo_restriction(
        "United States", "We're fully remote — work from anywhere.", True
    )
    assert scope == "worldwide"


def test_anywhere_in_the_us_is_not_worldwide():
    # The counter-case: "anywhere in the US" is a US restriction, not worldwide.
    raw, scope = extract_geo_restriction(
        "United States", "You can work from anywhere in the US.", True
    )
    assert scope == "us"


def test_explicit_residency_demand_beats_worldwide_mention():
    desc = "Remote worldwide vibes, but you must reside in the United States."
    raw, scope = extract_geo_restriction("Remote", desc, True)
    assert scope == "us"


def test_plain_country_location_still_wins_when_no_body_signal():
    assert extract_geo_restriction("Remote — MN, US", None, True) == ("Remote — MN, US", "us")
