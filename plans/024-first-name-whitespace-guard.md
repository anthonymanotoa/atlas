# Plan 024: Guard `_first_name()` against whitespace-only names

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 413ae10..HEAD -- engine/outreach/templates.py tests/test_templates.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `413ae10`, 2026-07-06

## Why this matters

`_first_name()` extracts a contact's first name for outreach drafts. For a
whitespace-only name (`" "` — importable from a malformed `Connections.csv` row or a
hand-edited contact), the truthiness guard passes but `.split()` returns `[]`, so
`[0]` raises `IndexError` and the whole draft-generation batch for that job dies on one
bad contact row. One-line fix plus a pinning test.

## Current state

`engine/outreach/templates.py:27-28`:

```python
def _first_name(name: str | None) -> str:
    return (name or "").split()[0] if name else ""
```

The bug: `name = " "` is truthy → takes the first branch → `" ".split()` → `[]` →
`[][0]` → `IndexError`. Callers (the draft builders in this module) pass contact names
straight from DB rows.

Repo conventions: pure helpers in this module are tested in `tests/test_templates.py`
with small, direct asserts — see `tests/test_templates.py:36-41`
(`test_skills_phrase_forms`) for the structural pattern to follow.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| This test file | `uv run pytest tests/test_templates.py -q` | all pass |
| Full suite | `uv run pytest` | all pass |
| Lint + format | `uv run ruff check . && uv run ruff format --check .` | exit 0 |

## Scope

**In scope** (the only files you should modify):

- `engine/outreach/templates.py` (the `_first_name` function only)
- `tests/test_templates.py` (add one test)

**Out of scope** (do NOT touch):

- Any other helper in `templates.py` (the EN/ES template pair is by design).
- Contact import/validation in `engine/referrals/` — defensive fix at the use site is
  the decided scope; upstream validation is a different discussion.

## Git workflow

- Branch: `advisor/024-first-name-whitespace-guard`.
- One commit: `fix(outreach): _first_name no longer crashes on whitespace-only names`.
- Never `git add .` — add the two files by name.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Fix the helper

Replace `engine/outreach/templates.py:27-28` with:

```python
def _first_name(name: str | None) -> str:
    words = (name or "").split()
    return words[0] if words else ""
```

**Verify**: `uv run pytest tests/test_templates.py -q` → existing tests pass.

### Step 2: Pin it with a test

Add to `tests/test_templates.py` (import `_first_name` alongside the existing imports
at line 9):

```python
def test_first_name_handles_missing_and_whitespace():
    assert _first_name(None) == ""
    assert _first_name("") == ""
    assert _first_name("   ") == ""  # whitespace-only: used to raise IndexError
    assert _first_name("Ada Lovelace") == "Ada"
```

**Verify**: `uv run pytest tests/test_templates.py -q` → all pass, including the new one.

## Test plan

- The new test above covers: `None`, empty string, whitespace-only (the regression),
  and the happy path. Modeled on `test_skills_phrase_forms` in the same file.
- Full suite: `uv run pytest` → green.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run pytest` exits 0; `test_first_name_handles_missing_and_whitespace` exists and passes
- [ ] `uv run ruff check .` and `uv run ruff format --check .` exit 0
- [ ] Only the two in-scope files are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `_first_name` at `templates.py:27-28` no longer matches the excerpt (drift).
- The fix breaks any existing test (it must not — the change is behavior-preserving for
  every non-pathological input).

## Maintenance notes

- If contact names ever get validated at import time (referrals), this guard stays —
  belt and suspenders on a crash-in-a-batch path is cheap.
