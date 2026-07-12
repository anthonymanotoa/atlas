# Geo-eligibility gate — design

**Date:** 2026-07-12
**Status:** approved
**Problem:** Remote postings hard-restricted to a country the candidate does not live in
(e.g. "Remote — MN, US" for a candidate in Ecuador) reach the shortlist and even the
"ready to send" set with fit 100. In the owner profile, 68 of ~110 shortlisted/ready jobs
were US-restricted and unusable.

## Root causes (verified against the live owner DB)

1. **Config conflation.** `acceptable_regions` shipped as `[worldwide, latam, na, eu]`,
   so a `us`-scoped posting *covers* the candidate and factor 2c never fires. "I'd work
   for a US company" was conflated with "I can reside in the US".
2. **Clamp absorption.** Strong postings accumulate ~122 pre-clamp points; the −12
   `geo_penalty` leaves them at 110, which still clamps to 100. The penalty is invisible
   exactly on the best matches.
3. **US-state ↔ ISO-2 collision.** `_LOC_CODE_RE` reads "CO, US" as Colombia, "PA, US"
   as Panama, "DE, US" as Germany — those false tokens map into latam/eu regions and make
   US-only jobs pass as candidate-covered.

## Decision (user-approved)

A remote posting whose **confirmed** geo restriction does not cover the candidate is
**disqualified** — same mechanism as deal-breakers: score hard-capped at 12, never
shortlisted, never selected by the brain, still browsable at the bottom with a visible
knockout label (`remoto solo US`). Ambiguous or partial restrictions keep their full
score. No `geo_hard` flag: the behavior is unconditional (YAGNI); `geo_penalty` is
retired.

## Design

### 1. Scorer — `engine/scoring/fit.py` factor 2c

When `criteria.candidate_country` is set, the job is remote, `geo_scope` is a confident
restriction (not `""`/`worldwide`/`unknown`) and `geo_scope_covers(...)` is False:

- `disq = True` (existing hard-cap at 12 applies post-clamp — fixes root cause 2).
- Knockout: `remoto solo {SCOPE}` (e.g. `remoto solo US`).
- Factor entry with `delta 0` (like `deal_breaker`) so the breakdown records WHY.
- `criteria.geo_penalty` is no longer read and the `Criteria` field is dropped. Verified:
  the pydantic model ignores unknown keys, so existing `criteria.md` files that still
  carry `geo_penalty` keep loading.

Covered / worldwide / unknown scopes: unchanged (no penalty on missing signal).

### 2. Extraction — `engine/normalize.py` `extract_geo_restriction`

Evidence priority (new): **explicit residency demand in description** > **explicit
worldwide in description** > **location-derived scope** > `unknown`.

- **US-state collision fix:** track alias-derived and `_LOC_CODE_RE`-derived tokens
  separately. If `us` is among the location scopes, drop code-derived tokens that are
  also US state abbreviations (CO, PA, DE, IN, CA, AR, ID, MT, …: the intersection of
  `COUNTRY_TO_REGION` keys uppercased and USPS state codes). Full-name aliases
  ("Colombia") are always kept.
- **Worldwide override (the "partial" case):** if the description matches
  `_WORLDWIDE_DESC_RE` and NO explicit residency-demand pattern matched, the scope is
  `worldwide` even when the location yielded a country. Tighten the regex so
  "work from anywhere **in the US**" / "**within**" does NOT match (negative lookahead).
- Explicit residency demands (`must reside in…`, `only open to…`, `eligible/authorized
  to work in…`) beat both the location and the worldwide reassurance.

### 3. Config

- Owner profile (`profiles/owner/config/criteria.md`, gitignored — never in a PR):
  `acceptable_regions: [worldwide, latam]`; remove `geo_penalty`.
- Repo defaults and seed packs: audit every criteria template/seed that lists
  `acceptable_regions` and remove misleading `na`/`eu` defaults so new profiles don't
  inherit the conflation. Keep `worldwide` (+ the profile's own region where obvious).

### 4. Re-score with cleanup — `atlas score --rescore`

- Rescore now **re-extracts** `geo_restriction`/`geo_scope` from the stored
  location/description before scoring each job, and persists the corrected values
  (repairs the false `us,co` / `us,pa` / `us,de` rows already in the DB).
- Rescore also visits `tailored`/`ready`(/`prepped`) jobs — but ONLY to demote the ones
  that come out **newly disqualified**: they move back to `scored` (labels visible, out
  of shortlist/ready). Non-disqualified late-stage jobs are never touched (the existing
  "never regress tailored work" rule stays for score changes).
- After running it on the owner profile, re-run prep selection so the shortlist and the
  ready set refill with eligible jobs (latam / worldwide / unknown / covered).

### 5. UI / brain

No changes. Knockout labels already render on cards and job detail; the board and the
brain already exclude disqualified jobs via threshold + `disqualified`.

### 6. Testing

TDD per task; full suite (~643 backend + 126 frontend) stays green. New coverage:

- state-collision: "CO, US" → `us` only; "Remote — Colombia" → `co` kept.
- worldwide override: location "US" + "work from anywhere" → `worldwide`; counter-case
  "work from anywhere in the US" → `us`; explicit "must reside in the US" beats a
  "remote worldwide" mention.
- scorer: non-covered confident scope → disqualified, capped ≤12, knockout label; covered
  / unknown / worldwide → unchanged; no `geo_penalty` factor remains.
- rescore: re-extraction repairs stored scopes; newly-disqualified ready job demotes to
  `scored`; non-disqualified ready job untouched.
- seeds/templates: no `na`/`eu` in shipped `acceptable_regions`.

## Expected impact (owner profile)

Most of the 68 US-scoped shortlisted/ready jobs drop to the bottom with a
`remoto solo US` label; `unknown` (Ramp, GitLab Bangalore), `latam`, `br`, `mx`,
`worldwide` postings rise to fill the shortlist and ready set.
