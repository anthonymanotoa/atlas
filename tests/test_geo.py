"""Geo gazetteer + the coverage predicate the scorer uses (F2 geo-scoring)."""

from __future__ import annotations

from engine.geo import (
    COUNTRY_TO_REGION,
    GEO_ALIASES,
    STATE_CODE_COLLISIONS,
    US_STATE_CODES,
    geo_scope_covers,
    region_of,
)


def test_state_collision_set_is_the_country_state_intersection():
    assert STATE_CODE_COLLISIONS == {c for c in COUNTRY_TO_REGION if c in US_STATE_CODES}
    # The eight ISO-2 country codes that are also USPS state codes.
    assert STATE_CODE_COLLISIONS == {"ar", "ca", "co", "de", "id", "in", "mt", "pa"}


def test_map_has_the_four_regions_and_a_sane_size():
    assert set(COUNTRY_TO_REGION.values()) == {"latam", "eu", "na", "apac"}
    assert 60 <= len(COUNTRY_TO_REGION) <= 90


def test_region_of_common_countries():
    assert region_of("ec") == "latam"
    assert region_of("us") == "na"
    assert region_of("de") == "eu"
    assert region_of("sg") == "apac"
    assert region_of("zz") is None


def test_aliases_normalize_to_scope_tokens():
    assert GEO_ALIASES["united states"] == "us"
    assert GEO_ALIASES["usa"] == "us"
    assert GEO_ALIASES["uk"] == "gb"
    assert GEO_ALIASES["latin america"] == "latam"
    assert GEO_ALIASES["worldwide"] == "worldwide"


def test_covers_worldwide_unknown_and_blank():
    assert geo_scope_covers("worldwide", "ec", []) is True
    assert geo_scope_covers("unknown", "ec", []) is True
    assert geo_scope_covers("", "ec", []) is True


def test_covers_own_country_and_own_region():
    assert geo_scope_covers("ec", "ec", []) is True  # exact country
    assert geo_scope_covers("latam", "ec", []) is True  # candidate's region
    assert geo_scope_covers("us,ca", "ec", []) is False  # neither


def test_covers_acceptable_regions():
    # Region token in scope intersects acceptable_regions…
    assert geo_scope_covers("eu", "ec", ["eu"]) is True
    # …and a country token inside an acceptable region also covers ("br" ⊂ latam).
    assert geo_scope_covers("br", "ec", ["latam"]) is True
    # "worldwide" in acceptable_regions does NOT whitelist restricted scopes.
    assert geo_scope_covers("us", "ec", ["worldwide"]) is False


def test_covers_emea_region_for_eu_countries():
    # EMEA scope covers EU-region candidates (Germany is in EU region).
    assert geo_scope_covers("emea", "de", []) is True
    # EMEA does NOT cover non-EU regions (Mexico is latam, not covered by EMEA).
    assert geo_scope_covers("emea", "mx", []) is False
    # EMEA does NOT cover NA (US/Canada).
    assert geo_scope_covers("emea", "us", []) is False
    # EMEA does NOT cover APAC.
    assert geo_scope_covers("emea", "sg", []) is False
    # EMEA in acceptable_regions works as before (explicit intersection).
    assert geo_scope_covers("emea", "ec", ["emea"]) is True
