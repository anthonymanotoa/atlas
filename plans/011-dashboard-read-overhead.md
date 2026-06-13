# Plan 011: Reduce dashboard read overhead (overview scans, board query, referral rescans)

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/analytics.py engine/db/models.py engine/referrals/connections.py dashboard/backend/main.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S-M
- **Risk**: LOW
- **Depends on**: none (note: relies on `list_jobs(states=...)` already supporting an IN-list — see plan 005's generator fix, already merged)
- **Category**: perf
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Three read paths on the hottest dashboard endpoints do far more database work than they need to. The absolute cost is tiny today (small SQLite DB), but the waste is gratuitous and scales badly: `overview()` issues ~14 full-table scans where 2 queries suffice; `/api/board` fires 7 separate `list_jobs` queries where 1 does the job; and `match_referrals` re-reads the entire `contacts` table once per ready job (and again in the morning brief, `referrals_for_jobs`, and `job_detail`), making referral matching O(jobs × contacts) in full scans. All three are read-only and the observable behavior (counts, ordering, returned shapes) must stay identical. Collapsing them keeps the code honest and removes an O(N×M) trap before the dataset grows.

## Current state

Files and their roles:

- `engine/analytics.py` — analytics + "what to do next" layer powering the dashboard; contains `overview()` and `needs_action()`.
- `dashboard/backend/main.py` — FastAPI endpoints; `api_board` is the kanban board endpoint.
- `engine/db/models.py` — the `DB` data-access class; `list_jobs`, `counts_by_state`, `contacts_for_company` live here.
- `engine/referrals/connections.py` — fuzzy referral matching; `match_referrals` and `referrals_for_jobs`.
- `tests/test_engine.py` — existing engine test suite; new tests are modeled after the tests already here.

### PERF-02 — `overview()` over-scans (`engine/analytics.py:21-54`)

```python
21	def _count_notnull(db: DB, col: str) -> int:
22	    return db.conn.execute(f"SELECT COUNT(*) n FROM jobs WHERE {col} IS NOT NULL").fetchone()["n"]
...
34	def overview(db: DB) -> dict[str, Any]:
35	    funnel = [{"stage": name, "count": _count_notnull(db, col)} for name, col in FUNNEL]
36	    total = db.conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
37	    applied = _count_notnull(db, "applied_at")
38	    responded = _count_notnull(db, "responded_at")
39	    interview = _count_notnull(db, "interview_at")
40	    response_rate = round(responded / applied, 3) if applied else None
41	    interview_rate = round(interview / applied, 3) if applied else None
42	    return {
43	        "total_jobs": total,
44	        "counts": db.counts_by_state(),
45	        "funnel": funnel,
46	        "response_rate": response_rate,        # benchmark bands (frontend): 0.02–0.05 typical, 0.10–0.18 strong
47	        "interview_rate": interview_rate,
48	        "applied": applied,
49	        "ready": db.counts_by_state().get("ready", 0),
50	        "last_run": db.meta_get("last_run"),
51	        "last_success": db.meta_get("last_success_ts"),
52	        "downtime_hours": heartbeat.downtime_hours(db),
53	        "source_health": db.latest_source_health(),
54	    }
```

`FUNNEL` (lines 12-17) has 9 stages, so the list comprehension at line 35 runs 9 `_count_notnull` queries; line 36 adds the total; lines 37-39 add 3 more `_count_notnull` calls that **overlap** the funnel (`applied_at`, `responded_at`, `interview_at` are already in `FUNNEL`). `counts_by_state()` is called **twice** — line 44 and again line 49, the second only to read `.get("ready")`. That is ~14 round-trips.

`FUNNEL` definition (lines 12-17) for reference:

```python
12	FUNNEL = [
13	    ("discovered", "discovered_at"), ("scored", "scored_at"),
14	    ("shortlisted", "shortlisted_at"), ("tailored", "tailored_at"),
15	    ("ready", "ready_at"), ("applied", "applied_at"),
16	    ("responded", "responded_at"), ("interview", "interview_at"), ("offer", "offer_at"),
17	]
```

### REFERRAL RESCAN — `needs_action()` loop (`engine/analytics.py:57-94`)

```python
57	def needs_action(db: DB) -> list[dict]:
58	    """The action-first rail: concrete next steps, highest-leverage first."""
59	    actions: list[dict] = []
60	
61	    # 1. Ready to send (referrals first — highest conversion).
62	    ready = db.list_jobs(state="ready")
63	    ready_ref, ready_cold = [], []
64	    for j in ready:
65	        refs = match_referrals(db, j.get("company", ""))
66	        (ready_ref if refs else ready_cold).append((j, refs))
...
93	    actions.sort(key=lambda a: a["priority"])
94	    return actions
```

Line 65 calls `match_referrals(db, ...)` once **per ready job**, and each call re-reads the entire `contacts` table (see `contacts_for_company` below). The priority ordering produced (priority 0 reply, 1 ask_referral, 2 send_application, 3 follow_up, sorted ascending at line 93) must be preserved exactly.

### PERF-03 — `api_board` 7 queries (`dashboard/backend/main.py:50-56`)

```python
50	@app.get("/api/board")
51	def api_board():
52	    """Jobs grouped by the columns shown on the kanban board."""
53	    columns = ["shortlisted", "tailored", "ready", "applied", "responded", "interview", "offer"]
54	    with DB() as db:
55	        return {"columns": columns,
56	                "jobs": {c: db.list_jobs(state=c) for c in columns}}
```

Line 56 calls `db.list_jobs(state=c)` once per column (7 queries). The returned shape is `{"columns": [...], "jobs": {col: [job, ...]}}` and must not change.

### `list_jobs` already supports an IN-list (`engine/db/models.py:113-128`)

```python
113	    def list_jobs(self, state: Optional[str] = None, states: Optional[Iterable[str]] = None,
114	                  limit: Optional[int] = None) -> list[dict]:
115	        q, params = "SELECT * FROM jobs", []
116	        clauses = []
117	        if state:
118	            clauses.append("state=?"); params.append(state)
119	        if states:
120	            states = list(states)  # materialize once: a generator would be consumed by the count below
121	            placeholders = ",".join("?" * len(states))
122	            clauses.append(f"state IN ({placeholders})"); params.extend(states)
123	        if clauses:
124	            q += " WHERE " + " AND ".join(clauses)
125	        q += " ORDER BY COALESCE(fit_score,-1) DESC, discovered_at DESC"
126	        if limit:
127	            q += f" LIMIT {int(limit)}"
128	        return [dict(r) for r in self.conn.execute(q, params).fetchall()]
```

The `ORDER BY COALESCE(fit_score,-1) DESC, discovered_at DESC` (line 125) is the canonical board ordering and must be preserved when grouping in Python.

### `counts_by_state` (`engine/db/models.py:151-154`)

```python
151	    def counts_by_state(self) -> dict[str, int]:
152	        rows = self.conn.execute(
153	            "SELECT state, COUNT(*) n FROM jobs GROUP BY state").fetchall()
154	        return {r["state"]: r["n"] for r in rows}
```

One GROUP BY scan; safe to call once and reuse for both `counts` and `ready`.

### `contacts_for_company` (`engine/db/models.py:224-226`)

```python
224	    def contacts_for_company(self, company_norm: str) -> list[dict]:
225	        rows = self.conn.execute("SELECT * FROM contacts").fetchall()
226	        return [dict(r) for r in rows]  # fuzzy matching happens in referrals layer
```

It **ignores** its `company_norm` argument and returns ALL contacts every call. The fuzzy filter lives in the referrals layer (below). So every `match_referrals` call is a full `contacts` scan.

### `match_referrals` / `referrals_for_jobs` (`engine/referrals/connections.py:47-62`)

```python
47	def match_referrals(db: DB, company: str, threshold: int = MATCH_THRESHOLD) -> list[dict]:
48	    """Return 1st-degree contacts whose company fuzzy-matches `company`, best first."""
49	    target = norm_company(company)
50	    if not target:
51	        return []
52	    out = []
53	    for c in db.contacts_for_company(target):
54	        score = fuzz.token_sort_ratio(target, norm_company(c.get("company") or ""))
55	        if score >= threshold:
56	            out.append({**c, "_match": score})
57	    return sorted(out, key=lambda c: c["_match"], reverse=True)
58	
59	
60	def referrals_for_jobs(db: DB, jobs: list[dict]) -> dict[str, list[dict]]:
61	    """Map job_id -> matching 1st-degree contacts (for the dashboard/brain)."""
62	    return {j["id"]: match_referrals(db, j.get("company", "")) for j in jobs}
```

`match_referrals` takes `(db, company, threshold=...)`. Existing callers pass it positionally as `match_referrals(db, company)`. The signature change in this plan must keep that two-arg form working (the new param is optional and keyword-only).

### Conventions this plan matches

- `from __future__ import annotations` at the top of every engine module (see `engine/analytics.py:2`).
- typer CLI, pydantic v2 models, `rich.console` elsewhere in the engine — not touched here, but do not break imports.
- All SQLite access is parameterized (`?` placeholders, see `list_jobs`) with WAL; the DB uses sha1 16-char natural keys and UPSERT + COALESCE gap-fill (`add_contact` lines 214-218). Preserve this — no string interpolation of user values into SQL. The one exception already in the file is `_count_notnull`, which interpolates a **column name** drawn from the fixed `FUNNEL` constant (never user input); the replacement keeps column names hard-coded, never interpolating values.
- `@dataclass` result objects are used elsewhere for structured returns; the analytics layer returns plain `dict`s and that stays.
- Existing tests live in `tests/test_engine.py`; model new tests after those (same fixtures/style).

## Commands you will need

| Purpose            | Command                                              | Expected on success         |
|--------------------|------------------------------------------------------|-----------------------------|
| Python tests       | `uv run --extra dev pytest`                          | `9 passed` before changes; `11 passed` (or more) after new tests added |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors           |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0, build succeeds      |
| Drift check        | `git diff --stat c3e2679..HEAD -- engine/analytics.py engine/db/models.py engine/referrals/connections.py dashboard/backend/main.py tests/test_engine.py` | no in-scope drift           |

> Do NOT run a bare `pytest`. The global interpreter is missing `docx`, `rapidfuzz`, and `reportlab`, which makes 2 tests falsely fail. ALWAYS use `uv run --extra dev pytest`, which uses the project venv with those deps installed. (This is also faithful to the workspace rule of running tests through the project's tooling, never the global one.)

## Scope

**In scope** (the only files modified):
- `engine/analytics.py`
- `engine/db/models.py`
- `engine/referrals/connections.py`
- `dashboard/backend/main.py`
- `tests/test_engine.py` (add tests)

**Out of scope** (do NOT touch):
- The shape of any endpoint response (`/api/board`, `/api/overview`, `/api/jobs/{id}`) — the dashboard frontend depends on the exact keys and the funnel/board ordering.
- The `MATCH_THRESHOLD` value and fuzzy-matching scoring in `connections.py` — behavior must be byte-for-byte identical.
- Any DB schema, migration, or index change — this is a read-path refactor only.
- The frontend (`dashboard/frontend/`) — typecheck/build are run only as a regression gate, not modified.

## Git workflow

- Branch: `advisor/011-dashboard-read-overhead` (off the latest `main`).
- Commit per logical unit (one per step is fine); add only the files this session touched by name (never `git add .`).
- Do NOT push or open a PR — the operator merges explicitly.

## Steps

### Step 1: Collapse `overview()` to 2 queries

In `engine/analytics.py`, rewrite `overview()` so it:

1. Computes the funnel counts in ONE `SELECT` using `COUNT(col)` (which skips NULLs — equivalent to the old `COUNT(*) WHERE col IS NOT NULL`), aliasing each stage column. Build the SELECT from the `FUNNEL` constant's columns (hard-coded names from the constant — never user input), e.g.:

   ```python
   cols = ", ".join(f"COUNT({col}) AS {name}" for name, col in FUNNEL)
   row = db.conn.execute(f"SELECT COUNT(*) AS _total, {cols} FROM jobs").fetchone()
   total = row["_total"]
   funnel = [{"stage": name, "count": row[name]} for name, _ in FUNNEL]
   ```
   `applied`, `responded`, `interview` are then read from `row` (they are funnel stages — `row["applied"]`, `row["responded"]`, `row["interview"]`), removing the 3 overlapping `_count_notnull` calls.
2. Calls `db.counts_by_state()` **once**, stores it, and uses it for both `"counts"` and `"ready"` (`counts.get("ready", 0)`).

The `_count_notnull` helper (lines 21-22) becomes unused after this; remove it (it has no other callers — confirm with grep in Done criteria). Keep `response_rate`/`interview_rate` math and all other returned keys identical.

**Verify**: `uv run --extra dev pytest` → `9 passed` (no regression; behavior identical). Also `grep -rn "_count_notnull" engine/` → no matches.

### Step 2: Add an optional preloaded-contacts param to `match_referrals`

In `engine/referrals/connections.py`, change the signature to accept an optional, keyword-only preloaded contacts list so callers can load contacts once and reuse them:

```python
def match_referrals(db: DB, company: str, threshold: int = MATCH_THRESHOLD,
                    *, contacts: Optional[list[dict]] = None) -> list[dict]:
    target = norm_company(company)
    if not target:
        return []
    rows = contacts if contacts is not None else db.contacts_for_company(target)
    out = []
    for c in rows:
        ...
```

Add `from typing import Optional` if not already imported (check the top of the file). The two-arg form `match_referrals(db, company)` MUST keep working unchanged — `contacts` defaults to `None`, in which case it falls back to `db.contacts_for_company(target)` exactly as before. Do not change the scoring or sort.

**Verify**: `uv run --extra dev pytest` → still `9 passed` (the default path is unchanged).

### Step 3: Load contacts once in `needs_action()`

In `engine/analytics.py`, in `needs_action()` (the loop at lines 64-66), load contacts a single time before the loop and pass them into each `match_referrals` call:

```python
ready = db.list_jobs(state="ready")
all_contacts = db.contacts_for_company("")  # one scan, reused below
ready_ref, ready_cold = [], []
for j in ready:
    refs = match_referrals(db, j.get("company", ""), contacts=all_contacts)
    (ready_ref if refs else ready_cold).append((j, refs))
```

(`contacts_for_company` ignores its argument and returns all contacts, so `""` is fine and explicit.) The rest of `needs_action` — the priority assignments and the `actions.sort(key=lambda a: a["priority"])` at line 93 — stays untouched, so the output ordering is identical.

**Verify**: `uv run --extra dev pytest` → still `9 passed`.

### Step 4: Collapse `api_board` to one query

In `dashboard/backend/main.py`, replace the per-column loop with a single `list_jobs(states=columns)` call and group by state in Python, preserving the DB ordering (the rows come back already ordered by `COALESCE(fit_score,-1) DESC, discovered_at DESC`, so appending in iteration order preserves it per column):

```python
@app.get("/api/board")
def api_board():
    """Jobs grouped by the columns shown on the kanban board."""
    columns = ["shortlisted", "tailored", "ready", "applied", "responded", "interview", "offer"]
    with DB() as db:
        grouped: dict[str, list[dict]] = {c: [] for c in columns}
        for job in db.list_jobs(states=columns):
            grouped[job["state"]].append(job)
        return {"columns": columns, "jobs": grouped}
```

Pre-seed every column key (the dict comprehension above) so empty columns still appear as `[]` — matching the old behavior where each column always had a (possibly empty) list. The response shape is unchanged.

**Verify**: `uv run --extra dev pytest` → still `9 passed`.

### Step 5: Add assertion tests

In `tests/test_engine.py`, add two tests modeled after the existing tests in that file (reuse the same DB fixture / seeding helpers already present):

1. **`overview()` counts match a seeded DB** — seed a known set of jobs across stages, call `analytics.overview(db)`, and assert `total_jobs`, each `funnel` stage `count`, `counts`, `ready`, `applied`, `response_rate`, and `interview_rate` equal the expected values. This locks the 2-query rewrite to the old behavior.
2. **`needs_action()` priority ordering unchanged** — seed jobs in `ready`/`responded`/`applied` states (with at least one ready job that matches a seeded contact and one that does not, plus one stale applied job ≥ `STALE_APPLIED_DAYS` old), call `analytics.needs_action(db)`, and assert the returned `priority` values come out sorted ascending and the action `type`s are in the expected order (`reply` first, then `ask_referral`, then `send_application`, then `follow_up`).

**Verify**: `uv run --extra dev pytest` → `11 passed` (the original 9 + 2 new). Then `npm --prefix dashboard/frontend run typecheck` → exit 0 and `npm --prefix dashboard/frontend run build` → exit 0 (board/overview consumers still typecheck and build against the unchanged response shapes).

## Test plan

- New tests in `tests/test_engine.py`:
  - `overview()` count assertions against a seeded DB (happy path + the regression this plan fixes: the collapsed single-SELECT funnel must equal the old per-column counts; `ready` from the single `counts_by_state` call equals the old double-call value).
  - `needs_action()` priority-ordering assertion (covers: referral-backed ready job → priority 1, cold ready job → priority 2, responded → priority 0, stale applied → priority 3; final sort ascending). This guards the preloaded-contacts refactor against changing ordering.
- Structural pattern: model both after the existing tests already in `tests/test_engine.py` (same fixtures, same `DB` setup style).
- Verification: `uv run --extra dev pytest` → all pass, including the 2 new tests (`11 passed`).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports `11 passed` (original 9 + 2 new); new `overview()`/`needs_action()` tests exist in `tests/test_engine.py` and pass.
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] `grep -rn "_count_notnull" engine/` returns no matches (helper removed).
- [ ] `grep -n "db.counts_by_state()" engine/analytics.py` returns exactly ONE line (called once in `overview`).
- [ ] `grep -n "list_jobs(state=" dashboard/backend/main.py` shows no per-column board loop in `api_board` (the only remaining `state=` use is in `api_jobs`, line ~47).
- [ ] `match_referrals(db, company)` two-arg call still works: grep confirms the default `contacts=None` param exists in `engine/referrals/connections.py`, and `engine/referrals/connections.py` `referrals_for_jobs` is unchanged.
- [ ] No files outside the in-scope list are modified (`git status` shows only the 5 in-scope files).
- [ ] `plans/README.md` status row for plan 011 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (drift since `c3e2679`).
- Changing `match_referrals`' signature breaks any existing caller — if `grep -rn "match_referrals" engine/ dashboard/ brain/` reveals a caller relying on a positional third argument or on the old exact signature, keep the old single-/two-arg form working (the new param MUST be optional and keyword-only); if it cannot stay backward-compatible, STOP.
- `overview()` counts in the new test do not equal the values the old per-column code would have produced (the `COUNT(col)`-skips-NULL equivalence is wrong for some column) — STOP rather than adjusting expectations to match buggy output.
- `needs_action()` returns a different priority ordering or different action set than before the change.
- Any step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (schema, frontend, endpoint shape).

## Maintenance notes

For the human/agent who owns this code after the change lands:

- If `contacts_for_company` is ever made to actually filter by company in SQL (today it ignores its arg and returns all contacts), the "load once and reuse" optimization in `needs_action` (Step 3) and the preloaded-`contacts` path in `match_referrals` (Step 2) must be revisited — a SQL-side filter would make the preloaded full list wrong. The `company_norm`-ignoring behavior is load-bearing for this plan.
- If pagination or new columns are added to the kanban board, the single `list_jobs(states=columns)` grouping (Step 4) must keep pre-seeding every column key so empty columns still serialize as `[]`.
- A reviewer should scrutinize: (a) that the `COUNT(col)` funnel SELECT produces identical numbers to the old `COUNT(*) WHERE col IS NOT NULL` per stage, and (b) that the board ordering per column is still `fit_score DESC, discovered_at DESC` after Python grouping.
- Deferred out of this plan: adding DB indexes on the stage-timestamp / `state` columns. Not needed at current data volume; revisit if the funnel SELECT or board query shows up in profiling.
