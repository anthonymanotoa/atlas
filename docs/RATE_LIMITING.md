# Atlas — pacing & anti-ban posture

Guiding principle: **"slower is fine, never get my IP banned."** Atlas trades speed for
safety everywhere it touches a third party. There are **two distinct paths**, paced
differently — don't confuse them.

## 1. httpx discovery path (ATS feeds + free APIs)

Covers Greenhouse / Lever / Ashby / SmartRecruiters / Himalayas / Adzuna via
`engine/discovery/http.py` (`get_json` / `post_json`).

- **Per-domain pacing** (`engine/discovery/rate_limiter.py`): a minimum spacing between
  requests to the same domain, with **±20% jitter** so the cadence isn't robotic.
  Configured in `config/sources.yaml` → `rate_limits` (per-domain `min_delay_ms`).
- **429 backoff**: on HTTP 429, honor `Retry-After` (or exponential `2^attempt·3s`,
  capped) before retrying. Other transport errors get a short linear backoff.
- **No proxies, browser-ish User-Agent, generous timeouts.** Low volume by design.

Tune `min_delay_ms` up if a source ever 429s; there's no downside but wall-clock time.

## 2. LinkedIn (the real ban risk) — two sub-paths

**a) JobSpy guest scraping (`engine/discovery/jobspy_source.py`).** Logged-OUT guest, so
the worst case is a temporary IP throttle, never an *account* ban. Hard-capped
(`linkedin_cap`, default 200, well under the ~250 wall) and **paced between scrape calls**
(`linkedin_delay_ms`, default 2500ms, ±20% jitter).

**b) Supervised Claude-in-Chrome (social search, interviewer & peer research).** This uses
your **logged-in** session, so it carries real account/IP risk. The httpx RateLimiter does
**NOT** protect this path. Guardrails (enforced by you + the supervised skills):

- **One search / one profile at a time.** No bulk tab-opening, no rapid pagination.
- **Human speed + randomized pauses.** Read the page like a person; don't fire actions
  back-to-back.
- **Hard cap per session** (a handful of profiles), then stop. Spread work across days.
- **Never auto-contact.** Capture context; *you* send any message manually.
- Verify the full destination URL before following any link.

If LinkedIn ever shows a checkpoint/challenge: **stop**, don't retry in a loop.

## $0 invariant
No paid APIs, no proxy services, no API keys for pacing. `GITHUB_TOKEN` (portfolio
enrichment) is optional and unrelated to the Anthropic $0 rule.
