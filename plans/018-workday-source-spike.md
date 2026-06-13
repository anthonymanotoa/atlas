# Plan 018: [DIRECTION] Workday/Taleo/iCIMS direct-feed discovery source (design spike)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **This is a design spike, not a build-everything task.** The goal is to
> prototype ONE new ATS source (Workday) end-to-end, confirm a keyless path
> exists, define the `token`/`instance` contract, and write down the open
> questions — BEFORE anyone commits to Taleo/iCIMS. If the spike disproves the
> keyless assumption (Step 2), STOP and report findings rather than forcing a
> brittle integration.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- engine/config.py engine/discovery/runner.py engine/discovery/registry.py engine/discovery/ats/ engine/cv/tailor.py engine/outreach/build.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: direction
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Atlas's data model already anticipates Workday-class enterprise boards — `CompanyTarget`
reserves an `instance` field commented "workday tenant (unused in v1)", the CV tailoring
layer already classifies `myworkdayjobs`/`taleo`/`icims` URLs, and the outreach builder
already routes those three to the `ats_form` apply method. But **discovery cannot target
them**: the runner's `ATS_DISPATCH` only knows greenhouse/lever/ashby/smartrecruiters, and
the resolver's `PATTERNS` has no Workday host pattern, so `atlas resolve-ats` on a Workday
careers URL returns "No known ATS detected" and the user cannot seed `companies.yaml`.

Workday is the dominant enterprise ATS, so closing this gap is high value. But it also has
the strongest anti-bot posture of the major ATSs, which is the central risk to Atlas's
account-safe / $0 / keyless stance. This spike de-risks the decision: it prototypes the
Workday path behind a config gate, proves (or disproves) that a keyless public JSON endpoint
exists, and enumerates the unknowns (pagination, rate limits, anti-bot) so Taleo/iCIMS are
only attempted once the pattern is validated.

## Current state

The relevant files, each with one line on its role:

- `engine/config.py` — pydantic v2 `CompanyTarget` model; already reserves the `instance` field.
- `engine/discovery/runner.py` — discovery orchestrator; `ATS_DISPATCH` maps `ats` name → `fetch` fn (lines 20–25), iterated at lines 71–77.
- `engine/discovery/registry.py` — `resolve_ats()` careers-URL → `{ats, token, eu}` resolver; `PATTERNS` list (lines 16–22).
- `engine/discovery/ats/greenhouse.py` — exemplar keyless ATS source: single keyless JSON GET, returns `list[Job]`.
- `engine/discovery/ats/smartrecruiters.py` — exemplar two-tier (list + detail) keyless ATS source, with a per-run detail cap.
- `engine/discovery/http.py` — shared `make_client()` (browser-ish UA, follows redirects) + `get_json()` (429 backoff, raises on other HTTP errors).
- `engine/normalize.py` — the `Job` pydantic model every source returns and `compute_job_id` (sha1 16-char natural key).
- `engine/cv/tailor.py` — `detect_ats()` already classifies Workday/Taleo/iCIMS (unchanged by this plan; cited as evidence the model anticipates these).
- `engine/outreach/build.py` — `_apply_method()` already routes workday/taleo/icims to `"ats_form"` (unchanged by this plan; cited as evidence).
- `config/companies.example.yaml` — documents the per-ATS `token` meaning; the file `atlas resolve-ats` helps populate.
- `config/sources.yaml` — discovery source config; `ats.enabled` gate lives here.

Excerpts of the code as it exists today (verbatim, with `file:line` markers):

The reserved-but-dead field (`engine/config.py:69-75`):

```python
class CompanyTarget(BaseModel):
    company: str
    ats: str                                  # greenhouse | lever | ashby | smartrecruiters
    token: Optional[str] = None               # board token / site slug / job_board_name / companyIdentifier
    instance: Optional[str] = None            # workday tenant (unused in v1)
    eu: bool = False                          # lever EU host
    careers_url: Optional[str] = None         # for re-resolution
```

The dispatch table missing Workday (`engine/discovery/runner.py:16` and `:20-25`):

```python
from engine.discovery.ats import ashby, greenhouse, lever, smartrecruiters
...
ATS_DISPATCH: dict[str, Callable] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}
```

How the runner iterates the dispatch table (`engine/discovery/runner.py:71-77`):

```python
    # 1. Direct ATS feeds (the reliable spine).
    if want("ats") and cfg.get("ats", {}).get("enabled", True):
        for t in companies:
            fn = ATS_DISPATCH.get(t.ats)
            if not fn:
                continue
            store(f"{t.ats}:{t.company}", lambda t=t, fn=fn: fn(t, client))
```

The resolver patterns with no Workday entry (`engine/discovery/registry.py:16-22`):

```python
# host/path patterns → (ats, regex capturing the token)
PATTERNS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([a-z0-9_-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)", re.I)),
]
```

The resolver's return contract (`engine/discovery/registry.py:25-26` and `:37-43`):

```python
def resolve_ats(careers_url: str, client: Optional[httpx.Client] = None) -> Optional[dict]:
    """Return {'ats':..., 'token':..., 'eu':bool} or None if no known ATS detected."""
...
                if m:
                    token = m.group(1)
                    eu = ats == "lever" and "eu.lever.co" in hay
                    if token.lower() in ("embed", "job_board"):
                        continue
                    return {"ats": ats, "token": token, "eu": eu}
```

The exemplar keyless source to MATCH (`engine/discovery/ats/greenhouse.py:15-36`):

```python
BASE = "https://boards-api.greenhouse.io/v1/boards"


def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    url = f"{BASE}/{target.token}/jobs"
    data = get_json(client, url, params={"content": "true"})
    jobs: list[Job] = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name")
        jobs.append(Job(
            source="greenhouse",
            source_job_id=str(j.get("id")),
            title=j.get("title", "").strip(),
            company=target.company,
            location=loc,
            url=j.get("absolute_url"),
            apply_url=j.get("absolute_url"),
            description=html_to_text(j.get("content")),
            date_posted=(j.get("updated_at") or "")[:10] or None,
            raw={"departments": [d.get("name") for d in j.get("departments", [])]},
        ))
    return jobs
```

The shared HTTP helper signature to reuse (`engine/discovery/http.py:31-33`):

```python
def get_json(client: httpx.Client, url: str, params: Optional[dict] = None,
             retries: int = 2) -> Any:
    """GET a URL and parse JSON, backing off briefly on 429. Raises on other HTTP errors."""
```

Evidence the data model already anticipates these boards (no edit here — context only):

- `engine/cv/tailor.py:36-44` — `detect_ats()` returns `"workday"` for `myworkdayjobs`, plus `"taleo"`/`"icims"`.
- `engine/outreach/build.py:33-39` — `_apply_method()` returns `"ats_form"` for `("greenhouse", "lever", "ashby", "smartrecruiters", "workday", "taleo", "icims")`.

Repo conventions that apply here (MATCH these — they are not optional):

- typer CLI (`engine/cli.py`; `resolve-ats` command at `engine/cli.py:264-269`).
- pydantic v2 models (`Job` in `engine/normalize.py:98`, `CompanyTarget` in `engine/config.py:69`).
- `rich.console` for CLI output (`console.print(...)` in `engine/cli.py`).
- `@dataclass` results (e.g. `TailorResult` in `engine/cv/tailor.py:24`).
- `from __future__ import annotations` is the first import in every module — keep it.
- sha1 16-char natural keys via `compute_job_id` (`engine/normalize.py:70-73`); every `Job` finalizes to one, so cross-source dedupe with greenhouse/indeed is automatic — do NOT hand-roll an id.
- UPSERT + COALESCE gap-fill is handled by `db.upsert_job` (see `tests/test_engine.py:36-44`); a source just returns `list[Job]`, nothing more.
- Each ATS source module exposes exactly `fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]` and uses `get_json` from `engine/discovery/http.py`. Never build a raw `httpx` request or a new client.
- Existing tests live in `tests/test_engine.py`; they are network-free (see the module docstring at `tests/test_engine.py:1-5`). Model any new test after those — do NOT make a network call in a test.

Design constraint from config docs the spike must honor (`config/sources.yaml:1`):

```
# Discovery source configuration. Tuned for $0, low-volume, account-safe, remote-first.
```

Workday's anti-bot posture is in direct tension with this line. The spike's job is to find out
whether a keyless, account-safe path exists at all — if it does not, the correct outcome is a
written "no-go" recommendation, not a forced integration.

## Commands you will need

| Purpose            | Command                                              | Expected on success            |
|--------------------|------------------------------------------------------|--------------------------------|
| Python tests       | `uv run --extra dev pytest`                          | `9 passed`                     |
| Single test file   | `uv run --extra dev pytest tests/test_engine.py`     | all pass                       |
| Filter one test    | `uv run --extra dev pytest -k workday`               | new test(s) pass               |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors              |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0                         |
| Git status         | `git status`                                         | only in-scope files modified   |

Do NOT run a bare `pytest`: the global interpreter is missing `docx`/`rapidfuzz`/`reportlab`
and will falsely fail 2 tests. Always use `uv run --extra dev pytest`.

This plan touches no frontend code; the frontend commands are listed only so the executor can
confirm nothing leaked across the stack (`git status` should already show that).

## Suggested executor toolkit

- This is a network-touching spike. The probe in Step 2 needs outbound HTTPS to a public
  Workday tenant. If the environment is offline, that step's verification cannot run — treat
  it as a STOP condition and report "offline: cannot validate keyless CXS path".
- Reference, before starting: read `engine/discovery/ats/greenhouse.py` (single-call exemplar)
  and `engine/discovery/ats/smartrecruiters.py` (two-tier list+detail exemplar, with its
  `DETAIL_CAP = 40` per-run bound) — your Workday prototype mirrors one of these shapes.

## Scope

**In scope** (the only files you should modify or create):

- `engine/discovery/ats/workday.py` (create) — the prototype `fetch()`.
- `engine/discovery/runner.py` (edit) — import `workday` and add it to `ATS_DISPATCH`.
- `engine/discovery/registry.py` (edit) — add ONE Workday host pattern to `PATTERNS`.
- `tests/test_engine.py` (edit) — add a network-free parse test for `workday.fetch` against a fixture payload, plus a `resolve_ats` host-pattern test.
- `config/companies.example.yaml` (edit) — document the Workday `token`/`instance` contract.

**Out of scope** (do NOT touch, even though they look related):

- `engine/cv/tailor.py` — `detect_ats()` already returns `"workday"`; no change needed.
- `engine/outreach/build.py` — `_apply_method()` already routes `"workday"` to `ats_form`; no change needed.
- `engine/config.py` — `CompanyTarget.instance` already exists; the spike USES it, it does not redefine the model. (You MAY update the inline comment on `instance` if it still says "unused in v1" after this lands — but only that one comment, nothing structural.)
- Taleo and iCIMS sources — explicitly deferred until the Workday spike proves the pattern. Do NOT create `taleo.py` or `icims.py`.
- Any frontend file under `dashboard/frontend/`.
- `config/sources.yaml` beyond confirming the existing `ats.enabled` gate already covers the new source (it does — the runner loops `ATS_DISPATCH` under that one gate). Do not add a Workday-specific toggle there.

## Git workflow

- Branch: `advisor/018-workday-source-spike` (from latest `master`/`origin/main`).
- Commit per logical unit (e.g. one commit for the prototype source + dispatch, one for the resolver pattern + docs, one for tests). Match the repo's short imperative commit style — recent history examples: `advisor: surface [confirma] gaps in CV audit`, `Add light/dark theme toggle + native PDF export (reportlab)`.
- Do NOT push or open a PR. The operator merges to `master` explicitly.

## Steps

### Step 1: Prototype `engine/discovery/ats/workday.py` (the keyless CXS path)

Create `engine/discovery/ats/workday.py` mirroring the greenhouse exemplar's shape. Workday's
public careers site is backed by a keyless "CXS" JSON endpoint:

```
POST https://{tenant}.{host}/wday/cxs/{tenant}/{site}/jobs
```

where (per the `CompanyTarget` contract this spike defines):

- `target.instance` = the Workday **tenant** (the subdomain, e.g. `nvidia` in
  `nvidia.wd5.myworkdayjobs.com`). This is exactly the field reserved at `engine/config.py:73`.
- `target.token` = the **site** (the careers-site slug in the path after the tenant, e.g.
  `NVIDIAExternalCareerSite`). Reusing `token` keeps the per-ATS-meaning convention documented
  in `config/companies.example.yaml`.

The module MUST:

- Start with `from __future__ import annotations`.
- Expose exactly `def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:`.
- Use the shared HTTP layer. The CXS jobs endpoint is a POST with a JSON body
  (`{"limit": 20, "offset": 0, "searchText": "", "appliedFacets": {}}`) and is paginated via
  `offset`/`limit` with a `total` field in the response. `get_json` in
  `engine/discovery/http.py` is GET-only, so for the spike pick ONE of:
  - (preferred) add a sibling `post_json(client, url, json=...)` helper to `engine/discovery/http.py`
    mirroring `get_json`'s 429 backoff and `raise_for_status`, and use it; OR
  - if you do not want to touch `http.py`, call `client.post(url, json=body)` directly inside
    `workday.py` and `.raise_for_status()` — but document in a module comment that this bypasses
    the shared 429 backoff (a known spike shortcut to revisit).
- Bound the work like smartrecruiters does (`DETAIL_CAP = 40`): cap total pages/jobs per
  company per run (e.g. `MAX_JOBS = 100`, stop paginating past it) so a 5,000-req giant board
  can never blow up a $0/account-safe run. State this cap as a module constant with a comment.
- Map each posting in `response["jobPostings"]` into a `Job`: `source="workday"`,
  `source_job_id` from the posting's `bulletFields`/`externalPath`, `title` from `title`,
  `company=target.company`, `location` from `locationsText`, and construct
  `url`/`apply_url` as `https://{tenant}.{host}/{site}{externalPath}`. Leave `description=""`
  if the list payload has no body (Workday list rows usually don't; a detail fetch is a
  documented open question — see Step 5). Do NOT fabricate fields.
- Return `list[Job]` without calling `compute_job_id` yourself — `db.upsert_job` finalizes the
  id, exactly as greenhouse/lever do.

Add a one-line module docstring naming the endpoint, matching the style of
`engine/discovery/ats/greenhouse.py:1-5`.

**Verify**: `uv run --extra dev pytest -q` → `9 passed` (no regressions; the new file imports
cleanly and is not yet exercised by a test). Then
`uv run --extra dev python -c "from engine.discovery.ats import workday; print(workday.fetch.__doc__ or 'ok')"`
→ prints `ok` (or the docstring) with no ImportError.

### Step 2: Probe a real public Workday tenant to confirm the keyless path (spike gate)

This is the load-bearing spike question: **does a keyless CXS path actually return jobs?**
Probe one real public tenant (e.g. a tenant like `*.myworkdayjobs.com`) using the shared
client, exactly as the runner would call it.

Run (substitute a real public tenant/site you can find from any company's "View all jobs"
careers page — the URL pattern is `https://{tenant}.{host}/{site}`):

```
uv run --extra dev python -c "
from engine.config import CompanyTarget
from engine.discovery.http import make_client
from engine.discovery.ats import workday
c = make_client(timeout=30)
t = CompanyTarget(company='Probe', ats='workday', instance='<tenant>', token='<site>')
jobs = workday.fetch(t, c)
c.close()
print('fetched', len(jobs))
print(jobs[0].title if jobs else 'NONE')
"
```

**Verify**: prints `fetched N` with `N > 0` and a real job title.

- If `N > 0`: the keyless path is confirmed. Record the exact tenant/site you used and the
  observed `total` in your handoff notes. Proceed.
- If it returns `403`/`429`/a CAPTCHA/anti-bot HTML body, or `N == 0` on a tenant you know has
  open roles: **STOP**. The keyless assumption is disproved. Report the exact status
  code/body snippet and recommend a no-go (or a documented manual-token-only fallback) for
  Workday — do NOT proceed to wire it into the runner, and do NOT escalate to Taleo/iCIMS.

### Step 3: Register Workday in the runner dispatch

In `engine/discovery/runner.py`, add `workday` to the ATS import at line 16 and to
`ATS_DISPATCH` (lines 20–25):

```python
from engine.discovery.ats import ashby, greenhouse, lever, smartrecruiters, workday
...
ATS_DISPATCH: dict[str, Callable] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
}
```

No other runner change is needed: the loop at lines 71–77 already dispatches by `t.ats`, the
existing `ats.enabled` gate in `config/sources.yaml` already covers it, and the per-source
try/except + health log already isolates a failing Workday tenant from the rest of the run.

**Verify**: `uv run --extra dev pytest -q` → `9 passed`. Then
`uv run --extra dev python -c "from engine.discovery.runner import ATS_DISPATCH; print(sorted(ATS_DISPATCH))"`
→ output includes `'workday'` (list of 5 keys).

### Step 4: Add a Workday host pattern to the resolver + document the contract

In `engine/discovery/registry.py`, add ONE entry to `PATTERNS` (lines 16–22) that matches
Workday careers hosts and captures the tenant. Workday hosts look like
`https://{tenant}.{wdN}.myworkdayjobs.com/{locale?}/{site}`:

```python
    ("workday", re.compile(r"https?://([a-z0-9-]+)\.[a-z0-9]+\.myworkdayjobs\.com", re.I)),
```

Note the existing `resolve_ats` return shape is `{"ats", "token", "eu"}` (registry.py:26, 43).
The captured group here is the **tenant**, which this spike maps to `instance`, not `token`.
For the spike, the simplest faithful change is: when `ats == "workday"`, return the tenant in
`token` AND copy it (or leave a `# TODO` to extract the site) — but the cleaner option, and
the one to prefer, is to extend the return dict with an `instance` key for the Workday branch
so the resolver output mirrors the `CompanyTarget` fields. If you extend the return shape, keep
the existing greenhouse/lever/ashby/smartrecruiters branches returning their current 3-key
dict unchanged (a 4th optional key is additive and safe). Whichever you choose, the resolver
must no longer return `None`/"No known ATS detected" for a Workday URL. Document the site-vs-tenant
split as a known gap in your notes (resolving the **site** slug reliably from the careers HTML
is an open question — see Step 5).

Then update `config/companies.example.yaml` to document the Workday row contract, matching the
existing per-ATS comment block (`config/companies.example.yaml:7-10`). Add a line like:

```
#   ats: workday         instance = tenant in <tenant>.<wdN>.myworkdayjobs.com; token = site slug after the tenant
```

**Verify**: `uv run --extra dev python -c "from engine.discovery.registry import resolve_ats; print(resolve_ats('https://example.wd5.myworkdayjobs.com/ExampleCareers'))"`
→ prints a dict with `'ats': 'workday'` and the tenant captured (NOT `None`). This call hits
the network (the resolver does a GET); if offline, instead assert the pattern matches with:
`uv run --extra dev python -c "from engine.discovery.registry import PATTERNS; import re; print(any(a=='workday' and rx.search('https://example.wd5.myworkdayjobs.com/x') for a,rx in PATTERNS))"`
→ prints `True`.

### Step 5: Add network-free tests + write up the spike findings

In `tests/test_engine.py`, add (model after the existing tests; keep them network-free per
`tests/test_engine.py:1-5`):

1. `test_workday_parses_fixture_payload` — build a small dict mimicking the CXS response
   (`{"total": 1, "jobPostings": [{"title": "Senior Data Scientist", "externalPath": "/job/123", "locationsText": "Remote, US", "bulletFields": ["123"]}]}`),
   monkeypatch `engine.discovery.http.get_json` (or `post_json`/`client.post`, whichever Step 1
   used) to return it, call `workday.fetch(CompanyTarget(company="Acme", ats="workday", instance="acme", token="AcmeCareers"), <stub client>)`, and assert: one `Job` returned,
   `job.source == "workday"`, `job.title == "Senior Data Scientist"`, and `job.url` contains
   the tenant + externalPath. Use `monkeypatch` (already a pytest builtin) — no real HTTP.
2. `test_resolve_ats_detects_workday_host` — call `resolve_ats` is network-touching, so instead
   assert the `PATTERNS` regex matches a Workday host (mirror the offline check from Step 4):
   import `PATTERNS`, find the `"workday"` entry, assert it captures `acme` from
   `https://acme.wd5.myworkdayjobs.com/AcmeCareers`.

These two new tests raise the suite from 9 to 11 passing.

Then write the spike findings into your final handoff report (NOT a committed `.md` file —
return them as text):

- Confirmed: does a keyless CXS path exist? (from Step 2, with the tenant probed and observed `total`).
- The `token`/`instance` contract as implemented.
- Open questions enumerated, at minimum: (a) **pagination** — does `offset`/`limit` reliably
  page the full board, and what is the right per-run cap? (b) **rate limits / 429 behavior** —
  did the probe ever throttle? (c) **anti-bot** — any CAPTCHA/Cloudflare interstitial, and does
  it persist across runs/IPs? (d) **site-slug resolution** — can the careers-page HTML yield
  the site slug automatically, or must the user supply it manually? (e) **descriptions** — does
  a list row carry a usable body, or is a per-posting detail fetch (N+1, capped like
  smartrecruiters) required?
- Go/no-go recommendation for proceeding to Taleo and iCIMS.

**Verify**: `uv run --extra dev pytest -q` → `11 passed` (the original 9 plus the 2 new tests).
Then `uv run --extra dev pytest -k workday` → the new test(s) pass.

## Test plan

- New tests in `tests/test_engine.py`:
  - `test_workday_parses_fixture_payload` — happy path: a CXS payload parses into a `Job` with
    correct `source`, `title`, and `url`; no network (monkeypatched fetch). This is the
    regression guard for the parser this spike introduces.
  - `test_resolve_ats_detects_workday_host` — the new `PATTERNS` entry matches a
    `*.myworkdayjobs.com` host and captures the tenant (the gap this spike closes:
    `resolve-ats` no longer returns "No known ATS detected" for Workday).
- Structural pattern to model after: the existing network-free tests in `tests/test_engine.py`
  (e.g. `test_upsert_idempotent_and_gapfills` at lines 36–44 for `Job` construction;
  `test_tailor_never_fabricates...` at 72–86 for the no-fabrication discipline).
- Verification: `uv run --extra dev pytest` → `11 passed`, including the 2 new tests.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports `11 passed` (original 9 + 2 new).
- [ ] `uv run --extra dev python -c "from engine.discovery.runner import ATS_DISPATCH; assert 'workday' in ATS_DISPATCH"` exits 0.
- [ ] `uv run --extra dev python -c "from engine.discovery.ats import workday; assert callable(workday.fetch)"` exits 0.
- [ ] `uv run --extra dev python -c "from engine.discovery.registry import PATTERNS; import re; assert any(a=='workday' and rx.search('https://x.wd5.myworkdayjobs.com/y') for a,rx in PATTERNS)"` exits 0.
- [ ] `grep -n workday engine/discovery/ats/workday.py` matches (file exists and references workday).
- [ ] `git status` shows ONLY these modified/created: `engine/discovery/ats/workday.py`, `engine/discovery/runner.py`, `engine/discovery/registry.py`, `tests/test_engine.py`, `config/companies.example.yaml`, and optionally `engine/discovery/http.py` (if Step 1 added `post_json`) — and NO Taleo/iCIMS files, no frontend files.
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0 (confirms no cross-stack leakage).
- [ ] The spike findings (keyless-path confirmation, token/instance contract, the 5 open questions, go/no-go for Taleo/iCIMS) are recorded in the executor's final report.
- [ ] `plans/README.md` status row for plan 018 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts above — e.g.
  `ATS_DISPATCH` already contains `workday`, `PATTERNS` already has a Workday entry, or
  `CompanyTarget.instance` no longer exists (the codebase drifted since `c3e2679`).
- **Step 2's probe disproves the keyless assumption** — a real public Workday tenant returns
  403/429/CAPTCHA/anti-bot HTML, or 0 jobs for a board you know has open roles. This is the
  spike's central risk; report the status code/body snippet and recommend no-go. Do NOT force
  a brittle integration and do NOT proceed to Step 3+.
- The environment is offline so Step 2 cannot run at all — report "offline: cannot validate
  keyless CXS path" rather than declaring success on the parser alone.
- A step's verification fails twice after a reasonable fix attempt.
- The work appears to require touching an out-of-scope file — especially `engine/cv/tailor.py`,
  `engine/outreach/build.py`, or any frontend file (these already handle Workday or are
  unrelated; needing them signals the approach drifted).
- You find yourself about to create `taleo.py` or `icims.py` — those are explicitly deferred
  until this spike proves the pattern.

## Maintenance notes

For the human/agent who owns this code after the change lands:

- This is a **spike**: the `workday.py` source is a prototype gated behind the existing
  `ats.enabled` flag and only active for companies whose row has `ats: workday`. It ships no
  Workday rows in `companies.example.yaml` by default — only documentation of the contract — so
  it is dormant until a user adds a tenant.
- The reviewer should scrutinize: (a) the per-run job/pagination cap (does it actually bound a
  giant enterprise board?), (b) whether the probe in Step 2 was against a *real* public tenant
  and what it observed about rate limits / anti-bot, and (c) if Step 1 added `post_json` to
  `engine/discovery/http.py`, that it mirrors `get_json`'s 429 backoff and `raise_for_status`.
- Explicitly deferred out of this plan, pending the spike's go/no-go: Taleo and iCIMS sources;
  automatic site-slug resolution from careers HTML; per-posting detail fetches for full
  descriptions (would be an N+1, cap it like `smartrecruiters.DETAIL_CAP = 40`).
- If Workday's anti-bot posture later forces headers/proxies/login, that breaks the
  `$0 / account-safe / keyless` invariant stated at `config/sources.yaml:1` — at that point the
  correct move is to drop the source, not to compromise the invariant.
- When this lands, update the `# workday tenant (unused in v1)` comment at `engine/config.py:73`
  so it no longer says "unused".
