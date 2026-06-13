# Plan 020: Server-side Origin/Referer checks on state-mutating POST routes

> **Executor instructions**: This is a **design spike + implementation** plan for
> future work (STATUS = TODO). Follow it step by step. Run every verification
> command and confirm the expected result before moving to the next step. If
> anything in the "STOP conditions" section occurs, stop and report — do not
> improvise. When done, update the status row for this plan in `plans/README.md`
> — unless a reviewer dispatched you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- dashboard/backend/main.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition. NOTE: the line numbers below were
> captured against `c3e2679`. If `git diff --stat` reports the files unchanged
> but the line numbers are off by one or two, re-locate the code by symbol name
> (function/route) rather than by line and proceed — but if the *content* of the
> excerpts differs, STOP.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `c3e2679`, 2026-06-13
- **Finding**: SECURITY-02 (MED)

## Why this matters

The Atlas dashboard backend is a localhost-only, single-user FastAPI app with no
authentication (it binds to `127.0.0.1` by design). Its state-mutating endpoints
(`POST /api/jobs/{id}/state`, `/applied`, `/prep`, `/messages/{id}/sent`) have
**zero server-side request-authenticity check**: any request that reaches a
handler is executed. Today this is largely mitigated in the browser — the
`CORSMiddleware` advertises only the two dev origins with no credentials, and the
`application/json` content type forces a CORS preflight that a cross-site page
cannot satisfy — but that defense lives entirely in the browser, not in the
server. If a request reaches a handler (a misconfigured proxy, a future change
that relaxes the content type, a non-browser client on the loopback interface),
there is nothing stopping it from flipping a job's state, marking it applied, or
triggering an expensive `prep` (CV + outreach generation). This plan adds a thin,
config-driven server-side defense: the mutating POSTs reject requests whose
`Origin`/`Referer` is not an expected localhost origin (returning 403), while
still allowing legitimate same-origin requests — including the production case
where the SPA is served from FastAPI itself and the browser may omit `Origin`.
After this lands, request authenticity is enforced at the server, not just
assumed from the browser.

## Current state

Files and their roles:

- `dashboard/backend/main.py` — the entire FastAPI backend. Declares the CORS
  middleware, the four state-mutating POST routes, the read-only GET routes, and
  (mounted last) the static frontend in production mode.
- `tests/test_engine.py` — the only test file; network-free unit tests over the
  engine. New API tests go here, modeled on the existing tests (same imports,
  `db`/`tmp_path` fixtures, plain `assert` style). It does **not** currently use
  FastAPI's `TestClient` — this plan introduces the first such test.

The relevant code as it exists today, at commit `c3e2679`.

**CORS middleware** — `dashboard/backend/main.py:23-27`. Note the allowed origins
are exactly the two dev origins, and `allow_credentials` is **not** set (so it
defaults to `False`):

```python
app = FastAPI(title="Atlas", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)
```

**The four state-mutating POST routes** — `dashboard/backend/main.py:69-106`.
None of them inspect `Origin` or `Referer`:

```python
@app.post("/api/jobs/{job_id}/state")
def api_set_state(job_id: str, body: StateBody):
    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        db.set_state(job_id, body.state, {"via": "dashboard"})
    return {"ok": True, "state": body.state}


@app.post("/api/jobs/{job_id}/applied")
def api_mark_applied(job_id: str):
    with DB() as db:
        db.set_state(job_id, "applied", {"via": "dashboard"})
    return {"ok": True}


@app.post("/api/jobs/{job_id}/prep")
def api_prep(job_id: str, body: PrepBody):
    from engine.cv.build import build_for_job
    from engine.outreach.build import build_outreach, write_package
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        cv = build_for_job(db, job_id, language=body.language)
        build_outreach(db, job_id, language=body.language)
        write_package(db, job_id, language=body.language)
    return {"ok": True, "coverage": cv.coverage, "parse_ok": cv.parse_ok}


@app.post("/api/messages/{message_id}/sent")
def api_mark_sent(message_id: int):
    with DB() as db:
        db.conn.execute("UPDATE messages SET state='sent', sent_at=? WHERE id=?",
                        (now_iso(), message_id))
        db.conn.commit()
    return {"ok": True}
```

**Production static mount** — `dashboard/backend/main.py:138-142`. This is the
"served-from-FastAPI" mode the new check must NOT break: when the SPA is served
from the same FastAPI origin, the browser issues **same-origin** requests, which
may omit the `Origin` header entirely:

```python
# ── Serve the built frontend (if present) ────────────────────────────────────
# Mounted LAST so it never shadows the /api/* routes.
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
```

**Imports already present** at the top of the file (`dashboard/backend/main.py:7-21`):
`from __future__ import annotations`; `from fastapi import FastAPI, HTTPException`;
`from fastapi.middleware.cors import CORSMiddleware`; `from pydantic import BaseModel`.
There is **no** `Request` or `Depends` import yet — Step 1 adds them.

The run command in the module docstring (`dashboard/backend/main.py:5`) shows the
default bound port: `uv run uvicorn dashboard.backend.main:app --port 8787 --reload`.

Conventions this plan must match (state and follow them):

- `from __future__ import annotations` at the top of every backend/engine module
  (see `dashboard/backend/main.py:7`).
- pydantic v2 `BaseModel` for request bodies (`dashboard/backend/main.py:30,34`).
- API validation/authorization failures raise `fastapi.HTTPException` with a
  status + message (see `dashboard/backend/main.py:72`, `raise HTTPException(400, ...)`,
  and `:65,75`, `raise HTTPException(404, ...)`). Use the same pattern for the
  403 here: `raise HTTPException(403, "<message>")`.
- Tests live in `tests/test_engine.py`; model new tests after the existing ones
  there (same imports, `db`/`tmp_path` fixtures, plain `assert` style — see
  `tests/test_engine.py:17-19,30-45`).
- The frontend already only calls these endpoints same-origin or via the Vite
  dev proxy; no frontend change is needed.

## Commands you will need

| Purpose            | Command                                                                              | Expected on success |
|--------------------|--------------------------------------------------------------------------------------|---------------------|
| Python tests       | `uv run --extra dev pytest`                                                          | exit 0, "9 passed" (more after new tests are added — see Test plan) |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`                                      | exit 0, no errors   |
| Frontend build     | `npm --prefix dashboard/frontend run build`                                          | exit 0              |
| Drift check        | `git diff --stat c3e2679..HEAD -- dashboard/backend/main.py tests/test_engine.py`    | (drift check, see header) |

Do NOT run bare `pytest`: the global interpreter is missing `docx`, `rapidfuzz`,
and `reportlab`, so it falsely fails 2 tests. Always go through
`uv run --extra dev pytest`. The clean-checkout baseline before your changes is
exactly **"9 passed"**.

## Scope

**In scope** (the only files you should modify):

- `dashboard/backend/main.py`
- `tests/test_engine.py`

**Out of scope** (do NOT touch, even though they look related):

- The GET routes (`/api/overview`, `/api/jobs`, `/api/board`, `/api/jobs/{id}`,
  `/api/brief`, `/api/cv/.../download`, `/api/health`) — they are read-only (and
  the download path is already confined by plan 004). Do NOT add the Origin check
  to them; doing so risks breaking the read path and the in-browser API docs.
- `dashboard/frontend/` — the SPA already calls these endpoints same-origin / via
  the dev proxy and sets no special header by default. Only add a custom-header
  requirement if Step 1 explicitly chooses that variant (see Step 1); otherwise
  the frontend stays untouched. Typecheck/build are run only as regression gates.
- The `CORSMiddleware` configuration (`:24-27`) — leave it as-is. This plan adds a
  per-route check; it does not change CORS. (CORS preflight and this check are
  complementary layers.)
- `engine/` — no engine change is needed.

## Git workflow

- Branch: `advisor/020-post-route-origin-checks` (created from latest `main`).
- Commit per logical unit (e.g. one commit for the dependency + route wiring, one
  for the tests), or a single squashed commit — match the repo's style.
- Stage only the in-scope files by name
  (`git add dashboard/backend/main.py tests/test_engine.py`). Never `git add .` /
  `git add -A`.
- Do NOT push or open a PR. The merge to `main` is decided by the operator.

## Steps

### Step 0 (spike — decide the variant before writing code)

This finding was **deferred because of mode risk**: the production "served from
FastAPI" mode issues same-origin requests that may omit `Origin`, so a naive
"require an allowed `Origin`" check would 403 legitimate production traffic.
Before implementing, decide between two equivalent-strength approaches and record
the choice in the PR description:

- **Variant A (Origin/Referer allowlist, recommended)**: allow the request if it
  has **no** `Origin` and **no** cross-origin `Referer` (same-origin / non-browser
  case), OR if its `Origin` (falling back to the scheme+host+port of `Referer`)
  is in a config-driven allowlist of localhost origins. Reject (403) only when an
  `Origin`/`Referer` is present **and** not allowlisted. This is the lowest-risk
  option for the production same-origin case and needs **no** frontend change.
- **Variant B (custom same-origin header)**: require the SPA to send a custom
  header (e.g. `X-Atlas-Client: 1`) on the mutating POSTs; reject (403) if absent.
  A custom header cannot be set cross-site without a CORS preflight that the
  server already refuses. This is simple server-side but **requires a frontend
  change** (adding the header to the four POST calls), which widens scope — only
  pick it if you also bring `dashboard/frontend/` into scope explicitly.

**This plan implements Variant A** in Steps 1–3. If a reviewer directs you to
Variant B instead, STOP and get the frontend brought into scope first.

**Verify** (spike has no code yet): confirm the baseline is clean —
`uv run --extra dev pytest` → exit 0, "9 passed".

### Step 1: Add a config-driven allowlist and an Origin-check dependency

In `dashboard/backend/main.py`:

1. Extend the imports: `from fastapi import FastAPI, HTTPException, Request, Depends`
   (add `Request` and `Depends`). Add `import os` and `from urllib.parse import urlsplit`
   at the top with the other stdlib imports.

2. Define the allowlist near the top of the module (after `app` is created),
   **config-driven** so it tracks the bound host/port. Default it to the
   loopback origins for the documented default port (`8787`) plus the Vite dev
   origins, and allow an env override. The host/port the server actually binds to
   is operator-controlled (uvicorn `--port`), so read an env var to keep the
   allowlist in sync:

   ```python
   # Origins permitted to make state-mutating requests. Config-driven so it can
   # track the actual bound host/port (set ATLAS_ALLOWED_ORIGINS as a comma-list
   # to override; defaults cover the loopback backend + the Vite dev server).
   _DEFAULT_ALLOWED_ORIGINS = (
       "http://127.0.0.1:8787", "http://localhost:8787",
       "http://localhost:5173", "http://127.0.0.1:5173",
   )
   ALLOWED_ORIGINS = frozenset(
       o.strip() for o in os.environ.get(
           "ATLAS_ALLOWED_ORIGINS", ",".join(_DEFAULT_ALLOWED_ORIGINS)
       ).split(",") if o.strip()
   )
   ```

3. Add the dependency function. It must **allow** the same-origin / non-browser
   case (no `Origin` and no cross-origin `Referer`) and reject only a present,
   non-allowlisted origin:

   ```python
   def require_trusted_origin(request: Request) -> None:
       """Reject state-mutating requests from an untrusted browser origin (403).

       Localhost-only, single-user app: same-origin and non-browser requests omit
       Origin and are allowed; a present Origin/Referer must be in ALLOWED_ORIGINS.
       """
       origin = request.headers.get("origin")
       if origin is None:
           referer = request.headers.get("referer")
           if referer is None:
               return  # same-origin / non-browser request: nothing to verify
           parts = urlsplit(referer)
           origin = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None
           if origin is None:
               return
       if origin not in ALLOWED_ORIGINS:
           raise HTTPException(403, "origin not allowed")
   ```

   Keep `HTTPException(403, ...)` to match the existing error-raising convention.

**Verify**: `uv run --extra dev pytest` → exit 0, still "9 passed" (the new code
is defined but not yet wired into routes, so behavior is unchanged).

### Step 2: Attach the dependency to the four mutating POST routes only

Add `dependencies=[Depends(require_trusted_origin)]` to the decorator of each of
the four state-mutating POSTs in `dashboard/backend/main.py`, and **only** those
four. For example:

```python
@app.post("/api/jobs/{job_id}/state", dependencies=[Depends(require_trusted_origin)])
def api_set_state(job_id: str, body: StateBody):
    ...
```

Apply the identical change to:
- `@app.post("/api/jobs/{job_id}/state")` (`:69`)
- `@app.post("/api/jobs/{job_id}/applied")` (`:80`)
- `@app.post("/api/jobs/{job_id}/prep")` (`:87`)
- `@app.post("/api/messages/{message_id}/sent")` (`:100`)

Do NOT add the dependency to any GET route or to the static mount. Do not change
the function bodies.

**Verify**: `uv run --extra dev pytest` → exit 0, still "9 passed" (no existing
test exercises these POSTs, so the count is unchanged until Step 3).

### Step 3: Add FastAPI TestClient tests for the Origin check

In `tests/test_engine.py`, add tests using `fastapi.testclient.TestClient`
against the real `app`. This is the **first** TestClient usage in the suite;
import inside the test function (matching the file's pattern of local imports,
e.g. `tests/test_engine.py:48,73,89`). The mutating routes hit the real `DB()`
(no DB injection seam exists), so drive the test on the cheapest route to verify
the *dependency* fires before the body runs — the **foreign-origin** case must
403 **before** any DB work, so it needs no fixture data; the **same-origin** case
should reach the handler.

Add at minimum these two tests:

1. **Foreign origin → 403** (the dependency rejects before the handler runs):

   ```python
   def test_mutating_post_rejects_foreign_origin():
       from fastapi.testclient import TestClient
       from dashboard.backend.main import app
       client = TestClient(app)
       resp = client.post(
           "/api/jobs/anyjob/applied",
           headers={"origin": "https://evil.example.com"},
       )
       assert resp.status_code == 403
   ```

2. **Same-origin / no Origin → not 403** (the dependency allows it through; the
   handler may then succeed or 404, but must NOT be blocked by the origin check):

   ```python
   def test_mutating_post_allows_same_origin_no_origin_header():
       from fastapi.testclient import TestClient
       from dashboard.backend.main import app
       client = TestClient(app)
       # No Origin header → treated as same-origin / non-browser → allowed past the
       # origin check (handler runs against the real DB).
       resp = client.post("/api/jobs/anyjob/applied")
       assert resp.status_code != 403
   ```

   If `api_mark_applied` against a missing job behaves non-deterministically in
   the test environment, switch this assertion to a route whose origin-check pass
   is observable without DB state, or assert specifically that the response is not
   403 (the point is the origin check, not the handler outcome). Do NOT relax the
   403 test.

   Optionally add a third test asserting an **allowlisted** explicit origin
   (e.g. `headers={"origin": "http://localhost:8787"}`) is also `!= 403`.

If `TestClient` is unavailable under `uv run --extra dev` (it ships with
`starlette`/`fastapi`, which the backend already depends on), STOP and report —
do not add a new dependency without operator sign-off.

**Verify**: `uv run --extra dev pytest` → exit 0, with **2 more** tests passing
than the baseline (was "9 passed" → now "11 passed", or "9 passed" plus the count
of tests you actually added).

### Step 4: Frontend regression gate

No frontend change is expected under Variant A. Confirm the frontend still
typechecks and builds (guards against accidental coupling).

**Verify**:
- `npm --prefix dashboard/frontend run typecheck` → exit 0, no errors
- `npm --prefix dashboard/frontend run build` → exit 0

## Test plan

- New tests in `tests/test_engine.py` (first TestClient usage in the suite):
  1. **Foreign origin rejected**: a `POST` to a mutating route with
     `Origin: https://evil.example.com` returns HTTP **403** (dependency fires
     before the handler / any DB work).
  2. **Same-origin allowed**: a `POST` with **no** `Origin` header is **not** 403
     (same-origin / non-browser path passes the check).
  3. (Optional) **Allowlisted origin allowed**: a `POST` with
     `Origin: http://localhost:8787` is **not** 403.
- Structural pattern: model after the existing tests in `tests/test_engine.py`
  (local imports, plain `assert`); use `fastapi.testclient.TestClient(app)`.
- Verification: `uv run --extra dev pytest` → all pass, including the new tests
  (count rises from "9 passed" to "11 passed", or +N for N tests added).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports at least 2 more passing tests than the pre-change "9 passed" baseline (i.e. "11 passed" or more).
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] `grep -n "require_trusted_origin" dashboard/backend/main.py` returns the function definition **and** exactly 4 `Depends(require_trusted_origin)` usages (one per mutating POST): `grep -c "Depends(require_trusted_origin)" dashboard/backend/main.py` returns `4`.
- [ ] `grep -n "ALLOWED_ORIGINS" dashboard/backend/main.py` returns a match (the config-driven allowlist exists).
- [ ] No `Depends(require_trusted_origin)` appears on any `@app.get(` route: `grep -n '@app.get' dashboard/backend/main.py` shows none carry the dependency.
- [ ] No files outside the in-scope list are modified (`git status` shows only `dashboard/backend/main.py` and `tests/test_engine.py`).
- [ ] `plans/README.md` status row for plan 020 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" does not match the quoted excerpts
  (the codebase has drifted since commit `c3e2679` — the drift-check `git diff`
  shows in-scope files changed, or the `CORSMiddleware`/route bodies differ).
- `uv run --extra dev pytest` does not report "9 passed" on a clean checkout
  before your changes — the baseline is wrong; investigate before editing.
- The same-origin test (Step 3, test 2) returns **403** — that means the check is
  rejecting legitimate same-origin / no-`Origin` requests, which would break
  production "served-from-FastAPI" mode (`main.py:138-142`). Do NOT loosen the
  403 path to make it pass; the `Origin is None → allow` branch is the fix.
- The bound host/port for the deployment is something other than the documented
  default and you cannot determine the correct allowlist — report rather than
  guessing origins (a wrong allowlist 403s real traffic). The allowlist is
  overridable via `ATLAS_ALLOWED_ORIGINS`.
- A reviewer directs you to Variant B (custom header) — that requires a frontend
  change; STOP and get `dashboard/frontend/` explicitly brought into scope.
- `fastapi.testclient.TestClient` cannot be imported under `uv run --extra dev`.
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (the GET routes, the
  CORS config, the frontend under Variant A, or `engine/`).

## Maintenance notes

For the human/agent who owns this code after the change lands:

- **Allowlist drift is the main risk** (this is why Risk is LOW-MED, not LOW). The
  allowlist must stay in sync with the host/port uvicorn actually binds to. The
  documented default is `--port 8787` (`main.py:5`); if the operator changes the
  port, set `ATLAS_ALLOWED_ORIGINS` accordingly, or the dashboard's own requests
  could be 403'd. A reviewer should confirm the default allowlist still matches
  the documented run command and the Vite dev origin in the `CORSMiddleware`
  config (`main.py:24-27`).
- This is **defense-in-depth on a localhost-only app**, not a primary control. The
  CORS preflight + loopback bind remain the first line; this check is the
  server-side backstop for when a request reaches a handler anyway. Do not remove
  the CORS config thinking this replaces it — they are complementary.
- The Origin check is intentionally **only** on the four state-mutating POSTs. If
  new mutating routes are added (POST/PUT/PATCH/DELETE), they must also get
  `dependencies=[Depends(require_trusted_origin)]`. Consider, as deferred
  follow-up, applying it via a router/sub-app or middleware filtered to unsafe
  methods so new routes are covered by default — left out here to keep the blast
  radius minimal and the change easy to review.
- The same-origin "allow when `Origin` is absent" branch is load-bearing for
  production mode. Any future change that starts serving the SPA cross-origin from
  the backend must revisit this assumption.
- Deferred out of this plan: tightening `CORSMiddleware` (e.g. explicit
  `allow_methods`/`allow_headers` instead of `"*"`), and any rate-limiting on the
  expensive `prep` route. Out of scope here.
