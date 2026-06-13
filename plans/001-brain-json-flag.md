# Plan 001: `atlas brain --json` works (daily runbook no longer fails on step 1)

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/cli.py`
> If `engine/cli.py` changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: docs/bug
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

The published daily runbook (`brain/SKILL.md:17`) is the first thing run every
morning and it invokes `uv run atlas brain --limit 8 --language en --json`. But
the `brain` Typer command never defined a `--json` option, so Typer exits
non-zero with `No such option: --json` and the entire pipeline produces nothing
— no discovery, no scoring, no morning brief. Step 1 of the runbook fails before
any work happens. Adding the flag (mirroring the sibling `advise` command, which
already has it) makes the documented command succeed and lets the brain emit a
machine-readable run summary for downstream tooling.

## Current state

Files involved:

- `engine/cli.py` — the Typer CLI. The `brain` command is the entry point the
  runbook calls (lines 198–216); the `advise` command right below it (lines
  218–226) is the in-repo exemplar for a `--json` flag.
- `brain/run_brain.py` — `run()` returns the summary dict that should be
  serialized (lines 32–75); its `main()` argparse path already supports `--json`
  (lines 109–121). **Out of scope** — only cited for context.
- `brain/SKILL.md` — the runbook; line 17 is the failing command. **Out of
  scope** — it becomes correct once the flag exists.

The `brain` command as it exists today (`engine/cli.py:198-216`) — note there is
NO `--json` option, only `limit` / `language` / `discover`:

```python
@app.command()
def brain(limit: int = typer.Option(8, help="Max jobs to fully prepare this run."),
          language: str = typer.Option("en", help="CV/outreach language: en | es"),
          discover: bool = typer.Option(True, help="Run discovery first.")) -> None:
    """Run the full daily pipeline: discover → score → prepare → brief. Sends nothing."""
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from brain.run_brain import run
    from engine.paths import OUTBOX_DIR
    with _db() as db:
        s = run(db, limit=limit, language=language, do_discover=discover)
    console.print(f"[bold green]Brain done[/] — new {s['discover'].get('new', 0)}, "
                  f"shortlisted {s['shortlisted']}, prepared {len(s['prepared'])}, "
                  f"follow-ups {s['followups']}.")
    if s.get("downtime_hours"):
        console.print(f"[yellow]⚠️ Was down ~{s['downtime_hours']:.0f}h[/] before this run.")
    console.print(f"Morning brief: {OUTBOX_DIR / 'MORNING_BRIEF.md'}")
```

The exemplar to MATCH — the `advise` command's `--json` pattern
(`engine/cli.py:218-226`):

```python
@app.command()
def advise(json_out: bool = typer.Option(False, "--json", help="Emit findings as JSON.")) -> None:
    """Audit your master CV against best practices (feeds the cv-linkedin-advisor skill)."""
    import json as _json
    from engine.advisor import audit_dict
    from engine.config import load_master_cv
    result = audit_dict(load_master_cv())
    if json_out:
        print(_json.dumps(result, indent=2, ensure_ascii=False))
        return
```

The dict to serialize is the value returned by `run()` (`brain/run_brain.py:32-35`
shows its shape, line 75 returns it):

```python
def run(db: DB, *, limit: int = 8, language: str = "en", do_discover: bool = True) -> dict:
    summary: dict = {"discover": {}, "scored": 0, "shortlisted": 0,
                     "prepared": [], "prepare_errors": [], "followups": 0,
                     "downtime_hours": None}
    ...
    return summary
```

The failing runbook command (`brain/SKILL.md:17`):

```bash
cd /Users/anthonymanotoa/dev/personal/atlas && uv run atlas brain --limit 8 --language en --json
```

Repo conventions that apply here (match them):

- **Typer CLI** — every command is an `@app.command()` function; boolean flags use
  `typer.Option(False, "--flag", help="...")` with an explicit long-name string
  so the dashed flag is exposed (see `advise`'s `json_out` above).
- **Local `import json as _json`** inside the command body, matching `advise`.
- **`from __future__ import annotations`** is the module convention; do not remove it.
- **pydantic v2 models / `rich.console` output** — keep the existing `console.print`
  rich path untouched for the non-JSON case.
- Existing tests live in `tests/test_engine.py`; model any new test after those.

## Commands you will need

| Purpose            | Command                                                   | Expected on success                  |
|--------------------|-----------------------------------------------------------|--------------------------------------|
| Python tests       | `uv run --extra dev pytest`                               | `9 passed` (do NOT use bare pytest)  |
| CLI help (probe)   | `uv run atlas brain --help`                               | exit 0; `--json` listed in options   |
| Git status         | `git status`                                              | only `engine/cli.py` modified        |

Note: a bare `pytest` hits a global interpreter missing `docx`/`rapidfuzz`/
`reportlab` and falsely fails 2 tests — always use `uv run --extra dev pytest`.

## Scope

**In scope** (the only file you should modify):
- `engine/cli.py` — add the `--json` option to the `brain` command.

**Out of scope** (do NOT touch):
- `brain/run_brain.py` — its `run()` already returns the summary dict and its
  `main()` argparse already supports `--json`; no change needed.
- `brain/SKILL.md` — the documented command becomes correct the moment the flag
  exists; editing it is unnecessary and out of scope.
- The non-JSON `console.print` rich output — leave it exactly as is.

## Git workflow

- Branch: `advisor/001-brain-json-flag` (created from latest `origin/main`).
- One commit for this single-file change.
- Do NOT push or open a PR — the operator does that explicitly.

## Steps

### Step 1: Add a `--json` option to the `brain` command

In `engine/cli.py`, extend the `brain` command signature with a JSON flag that
mirrors `advise`, and emit `json.dumps(summary, ...)` when it is set instead of
the rich summary. Keep the rich `console.print` block for the non-JSON path.

Target shape:

```python
@app.command()
def brain(limit: int = typer.Option(8, help="Max jobs to fully prepare this run."),
          language: str = typer.Option("en", help="CV/outreach language: en | es"),
          discover: bool = typer.Option(True, help="Run discovery first."),
          json_out: bool = typer.Option(False, "--json", help="Emit the run summary as JSON.")) -> None:
    """Run the full daily pipeline: discover → score → prepare → brief. Sends nothing."""
    import sys
    import json as _json
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from brain.run_brain import run
    from engine.paths import OUTBOX_DIR
    with _db() as db:
        s = run(db, limit=limit, language=language, do_discover=discover)
    if json_out:
        print(_json.dumps(s, indent=2, ensure_ascii=False))
        return
    console.print(f"[bold green]Brain done[/] — new {s['discover'].get('new', 0)}, "
                  f"shortlisted {s['shortlisted']}, prepared {len(s['prepared'])}, "
                  f"follow-ups {s['followups']}.")
    if s.get("downtime_hours"):
        console.print(f"[yellow]⚠️ Was down ~{s['downtime_hours']:.0f}h[/] before this run.")
    console.print(f"Morning brief: {OUTBOX_DIR / 'MORNING_BRIEF.md'}")
```

Notes:
- The `summary` dict is JSON-serializable as-is (str/int/None/list/dict only —
  see its construction at `brain/run_brain.py:32-35`), so `json.dumps` needs no
  custom encoder.
- The JSON branch returns early so the morning brief is still written by `run()`
  (the brief write happens inside `run()` at `brain/run_brain.py:74`, before the
  CLI ever prints) but no rich text contaminates stdout.

**Verify**: `uv run atlas brain --help` → exit 0 and the options list includes a
`--json` entry with help text "Emit the run summary as JSON."

### Step 2: Confirm the test suite still passes

No behavior in the existing pipeline changed; the existing suite must stay green.

**Verify**: `uv run --extra dev pytest` → `9 passed`.

## Test plan

- A dedicated automated test for the `--json` flag is **not required** (the change
  is a thin CLI option mirroring an already-tested sibling, and a full `brain`
  run touches discovery/network). The flag is exercised by the `--help` probe in
  Step 1 and the existing suite guards against regressions.
- If you choose to add one cheaply, model it after the command-level tests in
  `tests/test_engine.py`: invoke the CLI via Typer's `CliRunner` against
  `brain --help` and assert `"--json"` appears in `result.output`. Do not write a
  test that performs a real `brain` run (it hits discovery and external sources).
- Verification: `uv run --extra dev pytest` → `9 passed` (or `10 passed` if you
  added the optional `--help` test).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run atlas brain --help` exits 0 and lists `--json` in its options.
- [ ] `uv run --extra dev pytest` → `9 passed` (no regressions).
- [ ] `git status` shows only `engine/cli.py` modified (no other source files).
- [ ] `plans/README.md` status row for plan 001 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The `brain` command in `engine/cli.py` does not match the "Current state"
  excerpt (e.g. it already has a `--json`/`json_out` option, or its signature
  differs) — the codebase has drifted since this plan was written.
- `uv run atlas brain --help` still errors after the edit, or the options list
  does not show `--json`.
- `uv run --extra dev pytest` reports anything other than `9 passed` after the
  change (a bare `pytest` showing 2 failures is the documented false negative —
  re-run with `uv run --extra dev pytest` before concluding).
- The fix appears to require editing `brain/run_brain.py` or `brain/SKILL.md` —
  it should not; both are already correct.

## Maintenance notes

For the human/agent who owns this code after the change lands:

- If the shape of the `summary` dict returned by `run()`
  (`brain/run_brain.py:32-35`) ever gains a non-JSON-serializable value, the
  `json.dumps(s, ...)` call in `brain` will raise; keep the summary primitives-only.
- A reviewer should confirm: (a) the rich/non-JSON output path is byte-for-byte
  unchanged, (b) the JSON branch returns early so stdout stays parse-clean, and
  (c) the flag name/help matches the `advise` exemplar for consistency.
- The argparse `main()` in `brain/run_brain.py:109-121` is now redundant with the
  Typer command for the `--json` use case but is left in place; consolidating the
  two entry points is explicitly deferred (out of scope here).
