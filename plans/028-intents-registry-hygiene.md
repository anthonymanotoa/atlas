# Plan 028: Remove the dead F3-compat shim in `engine/intents.py` and pin the four intent registries together

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 0ed8967..HEAD -- engine/intents.py tests/test_intents.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `0ed8967`, 2026-07-06

## Why this matters

Two small hygiene issues in the F4 intents module. (1) `_match_stories_safe` was written so "F4
lands even if F3 hasn't merged yet" — F3's story bank has long been merged (`engine/stories.py`
exists; `DB.list_stories` is defined at `engine/db/models.py:961`), so its `try/except
ImportError` + `hasattr` guards are dead code that can silently swallow a REAL future regression
(e.g. a broken import in `engine.stories`) by returning `[]` instead of failing loudly. (2) The
module keeps **four parallel registries** that must stay aligned by hand — `INTENT_TYPES`,
`PROMPT_FILES`, `_CONTEXT_BUILDERS`, `_RESULT_WRITERS` — and nothing checks they do: adding a new
intent type to `INTENT_TYPES` but forgetting `PROMPT_FILES` crashes later with a bare `KeyError`
in `context_for` (`engine/intents.py:162`), at runtime, when the brain asks for context. A
5-line test makes that drift a test failure instead.

## Current state

- `engine/intents.py:22-43` — the four registries:

  ```python
  INTENT_TYPES = (
      "cv_review", "legitimacy_batch", "upskill_report",
      "interview_prep_deep", "profile_expand", "cover_letter",
  )
  ...
  PROMPT_FILES = { ... one entry per type ... }
  _CONTEXT_BUILDERS: dict[str, Callable[[DB, dict], dict]] = {}
  _RESULT_WRITERS: dict[str, Callable[[DB, dict, dict], str]] = {}
  ```

  All six types register BOTH a builder and a writer inside this same file (assignments at
  lines 250-251, 297-298, 337-338, 395-396, 458-459, 502-503). Today all four registries agree;
  nothing enforces it.

- `engine/intents.py:405-416` — the dead shim, verbatim:

  ```python
  def _match_stories_safe(db: DB, query_text: str) -> list[dict]:
      """F3 story bank matcher, guarded so F4 lands even if F3 hasn't merged yet."""
      try:
          from engine.config import load_ontology
          from engine.stories import format_story, match_stories
      except ImportError:
          return []
      stories = db.list_stories() if hasattr(db, "list_stories") else []
      if not stories:
          return []
      ranked = match_stories(stories, query_text, load_ontology())
      return [{"story": format_story(s), "score": score} for s, score in ranked[:5]]
  ```

  Its only caller is `_ctx_interview_prep_deep` at `engine/intents.py:441`
  (`"matched_stories": _match_stories_safe(db, query)`).

- `context_for` at `engine/intents.py:162` does
  `"prompt_file": f"brain/prompts/{PROMPT_FILES[intent['type']]}"` — an unregistered type is a
  raw `KeyError` here (enqueue already rejects unknown types at line 47-48, so this only bites
  when the registries drift from each other).

- Conventions: `from __future__ import annotations`; tests live in `tests/test_intents.py`
  (629 lines — model new tests on its existing style: plain functions taking the `db` fixture
  from `tests/conftest.py`).

## Commands you will need

| Purpose      | Command                                      | Expected on success |
|--------------|----------------------------------------------|---------------------|
| Sync deps    | `uv sync`                                    | exit 0              |
| Python tests | `uv run pytest`                              | exit 0, all pass    |
| Focused      | `uv run pytest tests/test_intents.py -q`     | all pass            |
| Lint         | `uv run ruff check . && uv run ruff format --check .` | exit 0     |

## Scope

**In scope** (the only files you should modify):
- `engine/intents.py`
- `tests/test_intents.py`
- `plans/README.md` (status row)

**Out of scope** (do NOT touch, even though they look related):
- `engine/stories.py`, `engine/db/models.py` — the story bank itself is fine.
- `brain/prompts/*` — prompt contents are plan 027's territory.
- The validation logic inside each `_write_*` writer — deliberate per-contract code, do not
  "deduplicate" it (previously audited and rejected).

## Git workflow

- Branch: current session branch; conventional commit, e.g.
  `refactor(intents): drop dead F3-compat shim + registry consistency test`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Replace `_match_stories_safe` with an unguarded helper

In `engine/intents.py`, rewrite the function to drop the ImportError/hasattr guards but keep
its behavior (top-5, formatted) and its empty-input short-circuit:

```python
def _matched_stories(db: DB, query_text: str) -> list[dict]:
    """Top-5 F3 story-bank matches, formatted for the brain's context."""
    from engine.config import load_ontology
    from engine.stories import format_story, match_stories

    stories = db.list_stories()
    if not stories:
        return []
    ranked = match_stories(stories, query_text, load_ontology())
    return [{"story": format_story(s), "score": score} for s, score in ranked[:5]]
```

(Local import matches the module's existing lazy-import convention in `_ctx_*` builders.)
Update the single caller at line 441 to `_matched_stories(db, query)`. Update the module
docstring or comment above the function if it still says "guarded so F4 lands even if F3
hasn't merged yet".

**Verify**: `grep -n "_match_stories_safe\|hasattr(db" engine/intents.py` → no matches.
**Verify**: `uv run pytest tests/test_intents.py -q` → all pass.

### Step 2: Add the registry-alignment test

In `tests/test_intents.py`, add (match the file's existing plain-function style):

```python
def test_intent_registries_are_aligned():
    """INTENT_TYPES, PROMPT_FILES, builders and writers must cover exactly the same types —
    drift crashes context_for with a KeyError at runtime, so pin it here instead."""
    types = set(intents.INTENT_TYPES)
    assert set(intents.PROMPT_FILES) == types
    assert set(intents._CONTEXT_BUILDERS) == types
    assert set(intents._RESULT_WRITERS) == types
```

Also assert every `PROMPT_FILES` value exists on disk (the brain reads them):

```python
def test_intent_prompt_files_exist():
    root = Path(__file__).resolve().parents[1]
    for fname in intents.PROMPT_FILES.values():
        assert (root / "brain" / "prompts" / fname).is_file(), fname
```

(Import `Path` from `pathlib` at the top if the file doesn't already.)

**Verify**: `uv run pytest tests/test_intents.py -q` → all pass, including the 2 new tests.

### Step 3: Full gate + index row

**Verify**: `uv run pytest` → exit 0.
**Verify**: `uv run ruff check . && uv run ruff format --check .` → exit 0.
**Verify**: `git status --short` → only in-scope files modified.
Update this plan's row in `plans/README.md` to DONE.

## Test plan

- `test_intent_registries_are_aligned` — the drift guard (step 2).
- `test_intent_prompt_files_exist` — prompt files on disk (step 2).
- Existing interview-prep tests in `tests/test_intents.py` (e.g. around line 390-465) must stay
  green after step 1 — they exercise `_ctx_interview_prep_deep`, which now calls the unguarded
  helper.
- Verification: `uv run pytest` → all pass, 2 new tests included.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "_match_stories_safe\|ImportError\|hasattr(db" engine/intents.py` → 0 matches
- [ ] `uv run pytest` exits 0; the 2 new tests exist and pass
- [ ] `uv run ruff check .` and `uv run ruff format --check .` exit 0
- [ ] `git status --short` shows only in-scope files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `engine/intents.py:405-416` does not match the shim excerpt above (module drifted).
- Any existing test in `tests/test_intents.py` fails after step 1 — that means the guards were
  load-bearing (something in the F3 import chain is genuinely broken); report the failing
  import instead of re-adding the guards.
- The new registry test fails on the CURRENT code — that means the registries already drifted;
  report which type is missing where instead of "fixing" a registry you don't understand.

## Maintenance notes

- Adding intent type #7 now requires updating all four registries or the new test fails —
  that is the point. The error message will name the missing registry.
- Reviewer: check that `_matched_stories` kept the `[:5]` cap and the `format_story` mapping —
  losing either silently changes the brain's context shape.
