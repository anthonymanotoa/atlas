# Plan 006: Wire the reply-aware follow-up cadence end-to-end

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record. It is written in the imperative as the spec that was executed.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/outreach/followups.py engine/db/models.py brain/run_brain.py dashboard/backend/main.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW-MED
- **Depends on**: plans/005-*.md
- **Category**: bug
- **Planned at**: commit `c3e2679`, 2026-06-13
- **Issue**: —

## Why this matters

Atlas documents a reply-aware follow-up cadence — Day 3 / 7 / 14 touches plus a
polite breakup at Day 21, all cancelled the instant a reply lands
(`engine/outreach/followups.py:1-6`). In production that whole system is **inert**.
The functions `schedule()` and `register_reply()` are called only from a unit test,
never from the brain pipeline or the dashboard, so `db.due_followups(...)` in the
brain always returns `[]` and no follow-up is ever drafted. Two further bugs would
break the cadence even if it were wired: the brain dedups follow-ups on `kind`
(which is the same string `"follow_up"` for touches 1–3), collapsing four touches to
two; and `schedule()`'s idempotency set is built from PENDING rows only, so a re-run
after a touch is done/cancelled resurrects it — pestering someone who already replied.
Landing this makes the documented cadence actually run: applying to a job arms the
schedule, replies cancel it, the brain drafts four distinct touches over time, and
re-runs never duplicate or resurrect a touch.

## Current state

The files and the exact code as of `c3e2679`:

- `engine/outreach/followups.py` — the cadence definition + scheduler. The public
  functions are dead code in production.
- `brain/run_brain.py` — the deterministic daily pipeline; the only production reader
  of `due_followups`. It never arms a schedule.
- `dashboard/backend/main.py` — FastAPI backend; `api_mark_applied` and `api_set_state`
  are the human-driven state transitions that should arm/cancel the cadence.
- `engine/db/models.py` — SQLite access layer; owns `has_message`, the `followups`
  table accessors, and `set_state`.
- `tests/test_engine.py` — the engine guarantee tests; new follow-up tests go here.

### `engine/outreach/followups.py:14-47` — CADENCE, schedule, register_reply

```python
# (touch_number, day_offset, is_breakup)
CADENCE = [(1, 3, False), (2, 7, False), (3, 14, False), (4, 21, True)]


def _parse(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return datetime.now(timezone.utc)


def schedule(db: DB, job_id: str, *, channel: str, message_id: int | None = None,
             base_iso: str | None = None) -> int:
    """Create the follow-up schedule for a sent message. Idempotent per job+channel."""
    existing = {f["touch_number"] for f in db.due_followups("9999")  # all pending
                if f["job_id"] == job_id and f["channel"] == channel}
    base = _parse(base_iso) if base_iso else datetime.now(timezone.utc)
    created = 0
    for touch, offset, _breakup in CADENCE:
        if touch in existing:
            continue
        due = (base + timedelta(days=offset)).isoformat()
        db.add_followup(job_id, channel=channel, touch_number=touch, due_at=due,
                        message_id=message_id)
        created += 1
    return created


def register_reply(db: DB, job_id: str) -> None:
    """A reply arrived — cancel pending follow-ups and advance the job to 'responded'."""
    db.cancel_followups_for_job(job_id)
    job = db.get_job(job_id)
    if job and job.get("state") in ("applied", "ready", "drafted", "tailored", "shortlisted"):
        db.set_state(job_id, "responded", {"trigger": "reply"})
```

Note bug 04: `existing` is built from `db.due_followups("9999")`, which is
PENDING-only (see `due_followups` below) — so a done/cancelled touch is invisible
and gets re-created on a re-run.

### `engine/outreach/followups.py:50-71` — followup_text (CORRECT — out of scope to change)

```python
def followup_text(job: dict, candidate: dict, touch_number: int, language: str = "en") -> Draft:
    company, role = job.get("company", ""), job.get("title", "")
    me = candidate.get("name", "")
    is_breakup = touch_number >= 4
    ...
    kind = "breakup" if is_breakup else "follow_up"
    return Draft(kind, "email", body, subject=f"Re: {role} at {company}",
                 variant=f"touch{touch_number}", language=language)
```

Touches 1–3 all return `kind="follow_up"` and differ only by
`variant="touch{n}"`. Touch 4 returns `kind="breakup"`, `variant="touch4"`.

### `brain/run_brain.py:56-69` — the due-followup loop

```python
    # Due follow-ups → draft (never send), then mark done.
    candidate = {"name": (load_master_cv().get("basics", {}) or {}).get("name", "")}
    for f in db.due_followups(now_iso()):
        job = db.get_job(f["job_id"])
        if not job:
            db.mark_followup(f["id"], "cancelled")
            continue
        d = followup_text(job, candidate, f["touch_number"], language)
        if not db.has_message(f["job_id"], d.kind):
            db.add_message(f["job_id"], channel=d.channel, kind=d.kind, body=d.body,
                           subject=d.subject, variant=d.variant, language=d.language, state="draft")
        db.mark_followup(f["id"], "done")
        summary["followups"] += 1
```

Note bug 02: dedup is `db.has_message(f["job_id"], d.kind)`. Once touch 1 has
drafted a `"follow_up"` message, touches 2 and 3 skip the `add_message` call but are
still marked `done` unconditionally (`db.mark_followup(f["id"], "done")` runs every
iteration) — the cadence silently collapses to one follow-up + one breakup.

### `dashboard/backend/main.py:68-83` — api_set_state, api_mark_applied

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
```

Neither endpoint calls `followups.schedule` or `followups.register_reply` today.

### `engine/db/models.py:198-202` — has_message (to be extended for bug 02)

```python
    def has_message(self, job_id: str, kind: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM messages WHERE job_id=? AND kind=? LIMIT 1", (job_id, kind)
        ).fetchone()
        return row is not None
```

### `engine/db/models.py:241-266` — followups accessors

```python
    def add_followup(self, job_id: str, *, channel: str, touch_number: int,
                     due_at: str, message_id: Optional[int] = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO followups (job_id, message_id, channel, touch_number, due_at, created_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, message_id, channel, touch_number, due_at, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def due_followups(self, as_of_iso: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM followups WHERE state='pending' AND due_at<=? ORDER BY due_at",
            (as_of_iso,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_followup(self, followup_id: int, state: str = "done") -> None:
        self.conn.execute("UPDATE followups SET state=? WHERE id=?", (state, followup_id))
        self.conn.commit()

    def cancel_followups_for_job(self, job_id: str) -> None:
        """Called when a reply lands — never pester after a response."""
        self.conn.execute(
            "UPDATE followups SET state='cancelled' WHERE job_id=? AND state='pending'", (job_id,))
        self.conn.commit()
```

`due_followups` filters `state='pending'`, which is why `schedule()`'s idempotency
set (bug 04) misses done/cancelled rows.

### `engine/db/models.py:137-148` — set_state (centralization candidate)

```python
    def set_state(self, job_id: str, new_state: str, detail: Optional[dict] = None) -> None:
        """Advance a job's state and stamp the per-stage timestamp + an event."""
        sets = ["state=?"]
        params: list[Any] = [new_state]
        col = STAGE_TIMESTAMP_COLS.get(new_state)
        if col:
            sets.append(f"{col}=COALESCE({col}, ?)")
            params.append(now_iso())
        params.append(job_id)
        self.conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", params)
        self.log_event(job_id, "stage_change", {"to": new_state, **(detail or {})})
        self.conn.commit()
```

### Conventions this plan must match

- `from __future__ import annotations` at the top of every module (already present in
  all in-scope files).
- pydantic v2 `BaseModel` for request bodies (see `StateBody`/`PrepBody` in
  `dashboard/backend/main.py:29-34`).
- `typer`/`argparse` CLI, `rich.console` — not touched here.
- All SQLite access is **parameterized** (`?` placeholders, never f-string interpolation
  of values) with `self.conn.commit()` after writes, under WAL — match
  `add_followup`/`cancel_followups_for_job` exactly.
- `sqlite3.Row` rows are converted via `dict(r)` / `[dict(r) for r in ...]` before return.
- Idempotency is a hard invariant (`engine/db/models.py:6-9`): a catch-up run must never
  duplicate jobs, drafts, or follow-ups.
- New tests live in `tests/test_engine.py`; model them after `test_followups_halt_on_reply`
  (`tests/test_engine.py:102-111`) — same `db` fixture, same `Job(...)` + `set_state` setup,
  same `due_followups("9999")` length assertions.

## Commands you will need

| Purpose             | Command                                              | Expected on success                          |
|---------------------|------------------------------------------------------|----------------------------------------------|
| Python tests        | `uv run --extra dev pytest`                          | `9 passed` (before changes); after Step 5, all pass including the new tests |
| Frontend typecheck  | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors                            |
| Frontend build      | `npm --prefix dashboard/frontend run build`          | exit 0, build succeeds                       |
| Git status          | `git status`                                         | only in-scope files modified                 |
| Drift check         | `git diff --stat c3e2679..HEAD -- <in-scope paths>`  | no unexpected changes                        |

Do NOT run bare `pytest` — the global interpreter is missing `docx`, `rapidfuzz`, and
`reportlab` and will falsely fail 2 tests. Always use `uv run --extra dev pytest`.

## Scope

**In scope** (the only files you should modify):
- `engine/outreach/followups.py`
- `engine/db/models.py`
- `brain/run_brain.py`
- `dashboard/backend/main.py`
- `tests/test_engine.py`

**Out of scope** (do NOT touch, even though they look related):
- `engine/outreach/followups.py:50-71` `followup_text` wording and the breakup
  semantics — the copy is correct and the `kind`/`variant` contract is what the
  dedup fix keys on. Do not change `kind` for touches 1–3.
- The frontend (`dashboard/frontend/`) — this is a backend/engine wiring fix; no UI
  change is required. (Typecheck/build are run only to prove nothing regressed.)
- `engine/db/schema.sql` — the `followups` table already has `job_id`, `channel`,
  `touch_number`, `state`; no migration is needed.

## Git workflow

- Branch: `advisor/006-followup-cadence` (based on the latest `main`/`master`).
- Commit per logical unit; message style matches the repo's plain imperative subject
  lines (e.g. `git log` shows `advisor: surface [confirma] gaps in CV audit`,
  `Security: force patched esbuild ...`). Prefix this work `advisor: wire follow-up cadence ...`.
- Do NOT push or open a PR. The operator decides the merge.

## Steps

### Step 1: Add `followups_for_job` to the DB layer (fixes bug 04 foundation)

In `engine/db/models.py`, in the followups section (after `cancel_followups_for_job`,
around line 266), add a state-agnostic accessor that returns all follow-up rows for a
job (optionally scoped to a channel), so `schedule()` can dedup against done/cancelled
touches, not just pending ones:

```python
    def followups_for_job(self, job_id: str, channel: Optional[str] = None) -> list[dict]:
        """All follow-up rows for a job (any state), optionally scoped to a channel.

        Used by schedule() to stay idempotent across done/cancelled touches, not just
        pending ones (due_followups is pending-only).
        """
        q = "SELECT * FROM followups WHERE job_id=?"
        params: list[Any] = [job_id]
        if channel is not None:
            q += " AND channel=?"; params.append(channel)
        q += " ORDER BY touch_number"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]
```

Match the parameterized style and `dict(r)` conversion used by the neighbouring
methods. No `commit()` needed (read-only).

**Verify**: `uv run --extra dev pytest -q` → `9 passed` (no regression; new method
is not yet exercised).

### Step 2: Extend `has_message` with an optional `variant` (fixes bug 02 foundation)

In `engine/db/models.py:198-202`, extend `has_message` to optionally match on
`variant` as well as `kind`, so the brain can dedup per (job, kind, variant) instead
of per (job, kind):

```python
    def has_message(self, job_id: str, kind: str, variant: Optional[str] = None) -> bool:
        q = "SELECT 1 FROM messages WHERE job_id=? AND kind=?"
        params: list[Any] = [job_id, kind]
        if variant is not None:
            q += " AND variant=?"; params.append(variant)
        q += " LIMIT 1"
        return self.conn.execute(q, params).fetchone() is not None
```

The default behaviour (no `variant`) is unchanged, so existing callers (e.g. the
outreach builder) keep working.

**Verify**: `uv run --extra dev pytest -q` → `9 passed`.

### Step 3: Make `schedule()` idempotent against all states (fixes bug 04)

In `engine/outreach/followups.py:25-39`, replace the PENDING-only existing-set with
the state-agnostic `followups_for_job` added in Step 1:

```python
def schedule(db: DB, job_id: str, *, channel: str, message_id: int | None = None,
             base_iso: str | None = None) -> int:
    """Create the follow-up schedule for a sent message. Idempotent per job+channel."""
    existing = {f["touch_number"] for f in db.followups_for_job(job_id, channel=channel)}
    base = _parse(base_iso) if base_iso else datetime.now(timezone.utc)
    created = 0
    for touch, offset, _breakup in CADENCE:
        if touch in existing:
            continue
        due = (base + timedelta(days=offset)).isoformat()
        db.add_followup(job_id, channel=channel, touch_number=touch, due_at=due,
                        message_id=message_id)
        created += 1
    return created
```

This guarantees a re-run after touch 1 is `done` (or after a reply cancelled the rest)
never re-creates that touch.

**Verify**: `uv run --extra dev pytest -q` → `9 passed` (existing
`test_followups_halt_on_reply` still passes).

### Step 4: Fix the brain dedup to be per-variant and only mark done on real work (fixes bug 02)

In `brain/run_brain.py:56-69`, change the dedup to key on `(kind, variant)` and only
mark a follow-up `done` when a draft was actually created (or already existed) — never
mark done after silently skipping. Target shape:

```python
    # Due follow-ups → draft (never send), then mark done.
    candidate = {"name": (load_master_cv().get("basics", {}) or {}).get("name", "")}
    for f in db.due_followups(now_iso()):
        job = db.get_job(f["job_id"])
        if not job:
            db.mark_followup(f["id"], "cancelled")
            continue
        d = followup_text(job, candidate, f["touch_number"], language)
        if not db.has_message(f["job_id"], d.kind, d.variant):
            db.add_message(f["job_id"], channel=d.channel, kind=d.kind, body=d.body,
                           subject=d.subject, variant=d.variant, language=d.language, state="draft")
        db.mark_followup(f["id"], "done")
        summary["followups"] += 1
```

The only change is the dedup key: `db.has_message(f["job_id"], d.kind, d.variant)`.
Because `variant` is `touch{n}` and unique per touch, each touch drafts exactly one
distinct message; a re-draft of the same touch is a no-op, and marking `done` after a
no-op re-draft is still correct (the message already exists). Touches 2 and 3 are no
longer suppressed by touch 1's `"follow_up"` kind.

**Verify**: `uv run --extra dev pytest -q` → `9 passed` (no new test yet; behaviour
locked by Step 5's tests).

### Step 5: Wire schedule() / register_reply() into the applied & responded transitions (fixes bug 01)

Two production entry points must arm and cancel the cadence. Keep both idempotent and
do not double-draft.

**(a) Arm on "applied" — `dashboard/backend/main.py:79-83` `api_mark_applied`:**

```python
@app.post("/api/jobs/{job_id}/applied")
def api_mark_applied(job_id: str):
    from engine.outreach import followups
    with DB() as db:
        db.set_state(job_id, "applied", {"via": "dashboard"})
        followups.schedule(db, job_id, channel="email")
    return {"ok": True}
```

`schedule()` is idempotent (Step 3), so re-marking applied does not duplicate touches.

**(b) Arm/cancel via `api_set_state` — `dashboard/backend/main.py:68-76`:** the kanban
board also moves jobs to `applied` and to `responded` through this endpoint. Centralize
the trigger here so both paths behave the same:

```python
@app.post("/api/jobs/{job_id}/state")
def api_set_state(job_id: str, body: StateBody):
    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    from engine.outreach import followups
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        if body.state == "responded":
            followups.register_reply(db, job_id)        # cancels pending + sets responded
        else:
            db.set_state(job_id, body.state, {"via": "dashboard"})
            if body.state == "applied":
                followups.schedule(db, job_id, channel="email")
    return {"ok": True, "state": body.state}
```

`register_reply` already calls `db.set_state(job_id, "responded", ...)` internally
(`engine/outreach/followups.py:42-47`), so do NOT also call `set_state` for the
`responded` branch — that would double-stamp the event.

Do not wire `schedule()` into `brain/run_brain.py`'s prepare loop or
`engine/outreach/build.py:write_package`: those run on `shortlisted` jobs that are not
yet applied, and arming there would draft follow-ups for jobs the human never sent. The
"applied" transition is the correct trigger.

**Verify**: `uv run --extra dev pytest -q` → all existing pass; then proceed to the
new tests in the Test plan.

## Test plan

Add integration tests to `tests/test_engine.py`, modelled structurally after
`test_followups_halt_on_reply` (`tests/test_engine.py:102-111`) — same `db` fixture,
same `Job(...)` + `db.set_state` setup, `due_followups("9999")` for "all scheduled".

Cover these cases:

1. **Applied arms the cadence (bug 01).** Build a job, call
   `followups.schedule(db, jid, channel="email")` (the call the dashboard now makes on
   the applied transition), then assert `len(db.due_followups("9999")) == 4`.

2. **Brain drafts 4 distinct touches over advancing time (bugs 01+02).** Import
   `brain.run_brain` and `engine.outreach.followups`. Arm the cadence with
   `base_iso` in the past (e.g. `schedule(db, jid, channel="email", base_iso="2020-01-01T00:00:00+00:00")`)
   so all four touches are due. Run the brain's follow-up loop (call
   `run_brain.run(db, do_discover=False, limit=0)`, or factor the loop and call it),
   then assert `db.messages_for(jid)` contains 4 follow-up/breakup messages with
   distinct `variant` values `{"touch1","touch2","touch3","touch4"}` and that exactly
   one has `kind == "breakup"`. (This fails on `master` today: the old `has_message`
   dedup yields only touch1 + breakup.)

3. **Responded cancels pending (bug 01).** After arming, call
   `followups.register_reply(db, jid)` and assert `len(db.due_followups("9999")) == 0`
   and `db.get_job(jid)["state"] == "responded"`.

4. **Re-running schedule after touch1 done does NOT duplicate touch1 (bug 04).** Arm
   the cadence, mark the touch-1 row `done` via `db.mark_followup(<id>, "done")`, then
   call `followups.schedule(db, jid, channel="email")` again and assert it returns `0`
   and that `[f["touch_number"] for f in db.followups_for_job(jid, channel="email")]`
   has exactly one entry per touch (no duplicate `1`).

Verification: `uv run --extra dev pytest` → all pass, including the new tests.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0; the new follow-up tests (cases 1–4 above)
      exist in `tests/test_engine.py` and pass.
- [ ] `grep -n "db.has_message(f\[.job_id.\], d.kind)" brain/run_brain.py` returns no
      matches (the per-variant dedup replaced the per-kind one).
- [ ] `grep -n "followups_for_job" engine/db/models.py engine/outreach/followups.py`
      shows the new method defined and used by `schedule()`.
- [ ] `grep -n "followups.schedule\|followups.register_reply" dashboard/backend/main.py`
      shows both wired (schedule on applied, register_reply on responded).
- [ ] `grep -n 'due_followups("9999")' engine/outreach/followups.py` returns no matches
      (the pending-only idempotency set is gone).
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (the codebase
  has drifted since this plan was written — the drift check flagged a change).
- Wiring `schedule()` into the applied transition makes any existing test double-draft
  or duplicate follow-ups (the existing idempotency invariant breaks) — reconsider the
  trigger point before forcing the change.
- `register_reply` plus an explicit `set_state(..., "responded")` end up logging two
  `stage_change` events for one transition — you wired the responded branch wrong; the
  `register_reply` call already sets the state.
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (e.g. `engine/db/schema.sql`,
  `engine/outreach/build.py`, or any frontend file) — the schema and copy are assumed
  sufficient; if they are not, that assumption is false and you should report.
- The `followups` table lacks a `variant` link or `due_followups`/`messages_for` do not
  return the fields the tests assert on — report rather than reshaping the schema.

## Maintenance notes

For the human/agent who owns this code after the change lands:

- The cadence is armed on the **applied** transition only. If a new state is introduced
  between `ready` and `applied` (or if the brain begins auto-marking jobs applied),
  revisit where `followups.schedule` fires so it still arms exactly once per real
  application.
- Dedup now keys on `(kind, variant)`. If `followup_text` ever changes its `variant`
  scheme (currently `touch{n}`), the brain's `has_message(..., d.variant)` dedup and
  test case 2's `{"touch1".."touch4"}` assertion must be updated together.
- `followups_for_job` is intentionally state-agnostic for idempotency. A reviewer should
  confirm `schedule()` uses it (not `due_followups`) and that no caller relies on the old
  pending-only behaviour of `has_message`.
- Reviewer focus: that `register_reply` is the sole state-setter in the responded branch
  of `api_set_state` (no double `set_state`), and that the brain still marks each due
  follow-up `done` so the loop terminates.
- Deferred out of this plan: the breakup semantics and `followup_text` wording (correct
  as-is), and any UI surfacing of the scheduled cadence on the dashboard.
