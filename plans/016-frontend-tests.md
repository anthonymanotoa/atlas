# Plan 016: Add a frontend test harness (vitest + testing-library)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- dashboard/frontend/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none (plan 017 — `scripts/check.sh` — will wire the `test` script in once this lands; not a hard dependency here)
- **Category**: tests
- **Planned at**: commit `c3e2679`, 2026-06-13
- **Issue**: (none)

This plan is **future work / a design spike** for the first test batch. The
harness setup (Steps 1–3) is concrete and should be implemented as written. The
specific assertions in Steps 4–5 are a starting batch; expand them as the
component surface grows, but do not block this plan on exhaustive coverage.

## Why this matters

Finding **TEST-04 (MED)**: `dashboard/frontend/` has **no `test` script** and no
test runner, assertion library, or DOM environment installed. The only
automated gate today is `tsc --noEmit` (the `typecheck` script), which proves
types compile but never executes a single line of runtime logic. As a result
the data-access layer (`src/api.ts` — every backend call the UI makes) and the
stateful components (`Board.tsx` drag-and-drop, `DetailDrawer.tsx`,
`NeedsAction.tsx`) ship **unverified**: a wrong URL, a wrong HTTP method, a
mis-shaped request body, or a render crash on a given props payload would all
pass CI. Adding vitest + Testing Library gives a fast, additive safety net
(no production code changes) so regressions in fetch wiring and component
rendering are caught before merge. This mirrors the Python side, which already
has executable tests in `tests/test_engine.py`.

## Current state

Relevant files (role in one line each):

- `dashboard/frontend/package.json` — npm manifest; scripts and deps. **No
  `test` script; no vitest / jest / @testing-library / jsdom anywhere.**
- `dashboard/frontend/src/api.ts` — the entire typed client for the FastAPI
  backend; thin `get`/`post` fetch wrappers plus the `api` object that names
  every endpoint, method, URL, and request body.
- `dashboard/frontend/src/components/NeedsAction.tsx` — pure, props-driven
  component: takes `actions: Action[]` + `onOpen` and renders cards (or an
  empty state). The cleanest first render-test target.

### `dashboard/frontend/package.json` — scripts and deps (lines 5–33)

```json
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "audit:prod": "npm audit --omit=dev"
  },
  "dependencies": {
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0",
    "@dnd-kit/utilities": "^3.2.2",
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-tooltip": "^1.1.4",
    "clsx": "^2.1.1",
    "cmdk": "^1.0.4",
    "lucide-react": "^0.460.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
```

Note: this is a **Vite 6 + React 19** project, so the test runner must be
**vitest** (shares Vite's transform pipeline; no separate Babel/jest config).

### `dashboard/frontend/src/api.ts` — fetch wrappers + endpoint map (lines 66–91)

```ts
async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}
async function post<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export const api = {
  overview: () => get<{ overview: Overview; needs_action: Action[] }>("/api/overview"),
  board: () => get<{ columns: string[]; jobs: Record<string, Job[]> }>("/api/board"),
  job: (id: string) => get<JobDetail>(`/api/jobs/${id}`),
  setState: (id: string, state: string) => post(`/api/jobs/${id}/state`, { state }),
  markApplied: (id: string) => post(`/api/jobs/${id}/applied`),
  prep: (id: string, language = "en") => post(`/api/jobs/${id}/prep`, { language }),
  markSent: (mid: number) => post(`/api/messages/${mid}/sent`),
  brief: () => get<{ markdown: string }>("/api/brief"),
  cvDownload: (jobId: string, vid: number, fmt = "docx") => `/api/cv/${jobId}/${vid}/download?fmt=${fmt}`,
};
```

Behaviors a test must pin (read directly from the code above):
- `get` calls `fetch(url)` with no options and throws `Error("<url> → <status>")`
  when `!r.ok`, otherwise returns `r.json()`.
- `post` always sends `method: "POST"` and header
  `"Content-Type": "application/json"`; the body is `JSON.stringify(body)` when
  `body` is truthy, else `undefined`.
- `api.setState("abc", "applied")` → POST `/api/jobs/abc/state` with body
  `{"state":"applied"}`.
- `api.markApplied("abc")` → POST `/api/jobs/abc/applied` with **no body**.
- `api.prep("abc")` → POST `/api/jobs/abc/prep` with body `{"language":"en"}`
  (default arg).
- `api.cvDownload("abc", 3)` returns the **string**
  `/api/cv/abc/3/download?fmt=docx` (a URL builder — it does **not** call
  `fetch`).

### `dashboard/frontend/src/components/NeedsAction.tsx` — full component

```tsx
import { ExternalLink } from "lucide-react";
import type { Action } from "../api";
import { ACTION_META } from "../lib";

export function NeedsAction({ actions, onOpen }: { actions: Action[]; onOpen: (id: string) => void }) {
  if (actions.length === 0) {
    return (
      <div className="card px-5 py-6 text-center fade-up">
        <div className="text-lg">🎉 Todo al día</div>
        <div className="text-[var(--color-muted)] text-sm mt-1">No hay nada pendiente ahora mismo.</div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-wide">Acciones para hoy</h2>
        <span className="chip">{actions.length}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {actions.map((a, i) => {
          const meta = ACTION_META[a.type] || { icon: "•", tone: "var(--color-muted)" };
          return (
            <div
              key={`${a.job_id}-${i}`}
              className="card px-4 py-3 min-w-[290px] max-w-[290px] fade-up cursor-pointer hover:border-[var(--color-accent)] transition"
              style={{ borderLeft: `3px solid ${meta.tone}` }}
              onClick={() => onOpen(a.job_id)}
            >
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: meta.tone }}>
                <span>{meta.icon}</span>
                <span>{a.label}</span>
              </div>
              <div className="text-[0.95rem] mt-1.5 truncate font-medium">{a.title}</div>
              <div className="text-[0.8rem] text-[var(--color-muted)]">{a.company}</div>
              {a.link && (
                <a href={a.link} target="_blank" rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="btn mt-2 !py-1 !px-2 text-xs">
                  <ExternalLink size={13} /> Abrir
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Behaviors a render test can assert (props → DOM, no network):
- `actions={[]}` → renders the empty-state text `Todo al día` and
  `No hay nada pendiente ahora mismo.`; renders **no** action cards.
- A non-empty `actions` array → renders the heading `Acciones para hoy`, a chip
  showing the count, and one card per action containing `a.label`, `a.title`,
  and `a.company`.
- Clicking a card calls `onOpen(a.job_id)` with that action's `job_id`.
- `Action` is the type imported from `../api` (defined at `api.ts:24-33`:
  `{ type, priority, job_id, title, company, label, link?, contact? }`).
- The component imports `ACTION_META` from `../lib`; the test renders the real
  component, so `dashboard/frontend/src/lib` must resolve (it already exists —
  do not mock it unless an import error forces it; if so, that is a STOP
  condition to report, not a workaround to invent).

### Repo conventions to match

- **Test runner = vitest**, because the project already builds on Vite 6
  (`vite": "^6.0.3"`). Vitest reuses the existing Vite config and the
  `@vitejs/plugin-react` transform already in devDependencies — no extra Babel
  setup. Do **not** introduce jest (it would need a parallel transform config).
- **Test file location & naming**: co-locate as `*.test.ts` / `*.test.tsx` next
  to the file under test, under `dashboard/frontend/src/`. (There are no
  existing frontend tests to mirror; this convention is the vitest default and
  keeps tests beside source.)
- The Python side keeps its executable tests in `tests/test_engine.py` and runs
  them via `uv run --extra dev pytest` (expects `9 passed`). The frontend
  harness is the JS-side analogue; keep it equally runnable from one command.
- TypeScript strict types are the existing gate (`tsc --noEmit`). New test files
  must type-check cleanly under the same `tsconfig`.

## Commands you will need

All commands assume the repo root
`/Users/anthonymanotoa/dev/personal/atlas/.claude/worktrees/magical-spence-26136c`
and use the `--prefix dashboard/frontend` form so they run from root without
`cd`.

| Purpose            | Command                                                  | Expected on success                       |
|--------------------|----------------------------------------------------------|-------------------------------------------|
| Install deps       | `npm --prefix dashboard/frontend install`                | exit 0                                     |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`          | exit 0, no errors                          |
| Frontend tests     | `npm --prefix dashboard/frontend test`                   | all test files pass (see Test plan counts) |
| Frontend build     | `npm --prefix dashboard/frontend run build`              | exit 0, `dist/` produced                   |
| Python tests       | `uv run --extra dev pytest`                              | `9 passed` (sanity: backend unaffected)    |

Do **not** run a bare `pytest` — the global interpreter lacks `docx`,
`rapidfuzz`, and `reportlab` and will falsely fail 2 tests. Always use
`uv run --extra dev pytest`.

## Suggested executor toolkit

- Vitest docs (test runner config + `vi.fn`/`vi.spyOn` for mocking `fetch`):
  https://vitest.dev/guide/
- Testing Library React (render + queries + `fireEvent`/`userEvent`):
  https://testing-library.com/docs/react-testing-library/intro/
- jsdom is the DOM environment vitest will use for component tests
  (`environment: "jsdom"`).

## Scope

**In scope** (the only files you should create or modify):
- `dashboard/frontend/package.json` — add devDeps + `test` script (modify).
- `dashboard/frontend/vitest.config.ts` — vitest config (create).
- `dashboard/frontend/src/test/setup.ts` — Testing Library jest-dom setup
  (create).
- `dashboard/frontend/src/api.test.ts` — fetch-wrapper / endpoint tests
  (create).
- `dashboard/frontend/src/components/NeedsAction.test.tsx` — render test
  (create).
- `dashboard/frontend/package-lock.json` — will change as a side effect of
  install; commit it (expected, not a violation).

**Out of scope** (do NOT touch, even though they look related):
- Any source under `dashboard/frontend/src/` **except** the two new test files
  above. Do **not** modify `api.ts`, `NeedsAction.tsx`, `Board.tsx`,
  `DetailDrawer.tsx`, `lib.ts`, or any component to "make it testable" — this
  plan is additive only. If a component cannot be tested without changing it,
  that is a STOP condition.
- `dashboard/frontend/tsconfig*.json` — do not edit unless a test type-error
  *requires* adding `vitest/globals` types; if so, prefer importing `describe`/
  `it`/`expect`/`vi` explicitly from `vitest` in the test files instead of
  touching tsconfig.
- `dashboard/frontend/vite.config.ts` — leave the build config alone; put test
  config in a separate `vitest.config.ts`.
- Anything outside `dashboard/frontend/` (engine/, brain/, dashboard/backend/,
  `scripts/`). Wiring the `test` script into `scripts/check.sh` is **plan 017**,
  not this one.

## Git workflow

- Branch: `advisor/016-frontend-tests` (created from latest `master`).
- Commit per logical unit (one for harness setup, one per test file is fine);
  short imperative messages consistent with repo history, e.g. the existing log
  uses lines like `Add one-command dashboard launcher (scripts/run.sh)` and
  `advisor: surface [confirma] gaps in CV audit`.
- Stage only the in-scope files **by name** (never `git add .` / `git add -A`):
  `git add dashboard/frontend/package.json dashboard/frontend/package-lock.json
  dashboard/frontend/vitest.config.ts dashboard/frontend/src/test/setup.ts
  dashboard/frontend/src/api.test.ts
  dashboard/frontend/src/components/NeedsAction.test.tsx`.
- Do **NOT** push or open a PR. The operator merges to `master` explicitly.

## Steps

### Step 1: Add the test toolchain to `package.json`

Add a `test` script and the dev dependencies. Use these packages (pinned to
versions compatible with Vite 6 / React 19 — verify they install cleanly in
Step 2):

In `"scripts"`, add (keep the existing scripts):
```json
    "test": "vitest run"
```
(Use `vitest run` — single-pass, CI-friendly, exits non-zero on failure. Watch
mode is `vitest` without `run`; do not make watch the default.)

In `"devDependencies"`, add:
```json
    "vitest": "^2.1.0",
    "jsdom": "^25.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/user-event": "^14.5.0"
```

**Verify**: file parses as JSON and contains the new keys —
`node -e "const p=require('./dashboard/frontend/package.json'); if(!p.scripts.test) throw 'no test script'; for(const d of ['vitest','jsdom','@testing-library/react','@testing-library/jest-dom']) if(!p.devDependencies[d]) throw 'missing '+d; console.log('ok')"`
→ prints `ok`.

### Step 2: Install dependencies

Run `npm --prefix dashboard/frontend install`.

**Verify**: `npm --prefix dashboard/frontend install` → exit 0, and
`test -d dashboard/frontend/node_modules/vitest && test -d dashboard/frontend/node_modules/jsdom && echo present`
→ prints `present`.

If install fails because a pinned version above does not exist or conflicts with
React 19 / Vite 6 peer ranges, this is a STOP condition — report the exact npm
error (do not silently downgrade React or Vite).

### Step 3: Add vitest config and the test setup file

Create `dashboard/frontend/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

Create `dashboard/frontend/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom";
```

(`globals: true` lets tests use `describe`/`it`/`expect` without imports; if a
type error appears for those globals, import them explicitly from `vitest`
rather than editing tsconfig — see Scope.)

**Verify**: `npm --prefix dashboard/frontend test` → exits 0 with a "no test
files found" (or equivalent "0 passed") message — confirms vitest loads the
config and jsdom environment without crashing. Then proceed to write tests.

### Step 4: Write `src/api.test.ts` — fetch wrappers & endpoint shapes

Create `dashboard/frontend/src/api.test.ts`. Mock the global `fetch` with
`vi.fn()`; reset it between tests (`beforeEach(() => { vi.restoreAllMocks(); })`).
A reusable helper for an OK response:
`const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });`

Cover at minimum these cases (assert against the exact behaviors quoted in
"Current state"):
- `api.overview()` → calls `fetch` once with first arg `"/api/overview"`;
  returns the mocked JSON.
- `api.job("abc")` → `fetch` called with `"/api/jobs/abc"`.
- `api.setState("abc", "applied")` → `fetch` called with `"/api/jobs/abc/state"`
  and a second-arg object whose `method` is `"POST"`, `headers["Content-Type"]`
  is `"application/json"`, and `body` is `JSON.stringify({ state: "applied" })`.
- `api.markApplied("abc")` → `fetch` called with `"/api/jobs/abc/applied"` and
  request-options `body` is `undefined` (no body).
- `api.prep("abc")` → POST `"/api/jobs/abc/prep"`, body
  `JSON.stringify({ language: "en" })` (default arg).
- **Error path**: when `fetch` resolves `{ ok: false, status: 404 }`,
  `api.job("x")` rejects with an `Error` whose message contains `→ 404`
  (use `await expect(...).rejects.toThrow("404")`).
- `api.cvDownload("abc", 3)` → returns the string
  `"/api/cv/abc/3/download?fmt=docx"` and `fetch` is **not** called.

**Verify**: `npm --prefix dashboard/frontend test` → all `api.test.ts` cases
pass (target ≥ 7 assertions across the cases above).

### Step 5: Write `src/components/NeedsAction.test.tsx` — render & interaction

Create `dashboard/frontend/src/components/NeedsAction.test.tsx`. Use
`render` and `screen` from `@testing-library/react` and
`userEvent`/`fireEvent` for the click. Build a sample `Action` matching the type
at `api.ts:24-33`, e.g.:
```ts
const sample = {
  type: "follow_up", priority: 1, job_id: "job-1",
  title: "Senior Engineer", company: "Acme", label: "Follow up",
};
```

Cover:
- Empty state: `render(<NeedsAction actions={[]} onOpen={() => {}} />)` →
  `screen.getByText("Todo al día")` (text appears, accept emoji prefix via a
  substring/`/Todo al día/` matcher) is in the document; no element with text
  `"Acciones para hoy"`.
- Populated state: render with `actions={[sample]}` →
  `screen.getByText("Acciones para hoy")` present, and `sample.title`,
  `sample.company`, and `sample.label` all appear in the document.
- Click: render with `onOpen={onOpen}` (a `vi.fn()`), click the card containing
  `sample.title`, assert `onOpen` was called once with `"job-1"`.

If rendering the real component fails because `../lib` (`ACTION_META`) cannot be
imported under vitest, STOP and report — do not stub `lib` to force a pass
(that would test a fake).

**Verify**: `npm --prefix dashboard/frontend test` → all
`NeedsAction.test.tsx` cases pass (target 3 cases).

### Step 6: Confirm the build and types are still clean

The harness must not break the existing gates.

**Verify (all three)**:
- `npm --prefix dashboard/frontend run typecheck` → exit 0, no errors.
- `npm --prefix dashboard/frontend run build` → exit 0, `dist/` produced.
- `uv run --extra dev pytest` → `9 passed` (backend untouched; sanity check).

## Test plan

- **New files**:
  - `dashboard/frontend/src/api.test.ts` — covers `api.ts` fetch wrappers:
    happy path (correct URL/method/headers/body per endpoint), the regression
    this guards (wrong method/URL/body shape), the error path (`!r.ok` throws
    with status in the message), and the URL-builder edge case
    (`cvDownload` returns a string, no fetch). Target ≥ 7 assertions.
  - `dashboard/frontend/src/components/NeedsAction.test.tsx` — covers the
    props→render contract: empty state, populated state (label/title/company),
    and the `onOpen(job_id)` click callback. Target 3 cases.
- **Structural pattern to follow**: there are no existing frontend tests; use
  the vitest + Testing Library defaults described in Steps 4–5. (The Python
  analogue is `tests/test_engine.py`, run via `uv run --extra dev pytest` — same
  spirit: one command, executable assertions.)
- **Verification**: `npm --prefix dashboard/frontend test` → all pass, with the
  new `api.test.ts` and `NeedsAction.test.tsx` files reporting green.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `npm --prefix dashboard/frontend install` exits 0; `node_modules/vitest`
      and `node_modules/jsdom` exist.
- [ ] `package.json` has a `"test": "vitest run"` script and devDeps `vitest`,
      `jsdom`, `@testing-library/react`, `@testing-library/jest-dom` present
      (the Step 1 `node -e` check prints `ok`).
- [ ] `npm --prefix dashboard/frontend test` exits 0; `api.test.ts` and
      `NeedsAction.test.tsx` both run and pass.
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] `uv run --extra dev pytest` prints `9 passed` (backend unaffected).
- [ ] No files outside the in-scope list are modified —
      `git status --porcelain` shows only `dashboard/frontend/package.json`,
      `dashboard/frontend/package-lock.json`,
      `dashboard/frontend/vitest.config.ts`,
      `dashboard/frontend/src/test/setup.ts`,
      `dashboard/frontend/src/api.test.ts`, and
      `dashboard/frontend/src/components/NeedsAction.test.tsx`.
- [ ] `plans/README.md` status row for plan 016 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The Drift check shows any file under `dashboard/frontend/` changed since
  `c3e2679`, **and** the live code no longer matches the "Current state"
  excerpts (e.g. `api.ts` wrappers changed signatures/URLs, or
  `NeedsAction.tsx` changed its props or rendered text). The tests in this plan
  assert the exact strings/shapes quoted above.
- `npm install` cannot resolve the pinned tool versions against React 19 / Vite
  6 peer ranges (report the exact npm peer-dependency error).
- A test cannot be made to pass **without editing a source file** (api.ts,
  NeedsAction.tsx, lib.ts, tsconfig, vite.config.ts) — this plan is additive;
  changing source to fit a test is out of scope.
- Rendering `NeedsAction` requires stubbing `../lib`/`ACTION_META` to avoid an
  import crash (means the import graph changed — report it).
- Any verification command fails twice after a reasonable fix attempt.

## Maintenance notes

For whoever owns this code after the change lands:

- **Plan 017** (`scripts/check.sh`) should add
  `npm --prefix dashboard/frontend test` to the project check gate so the new
  tests actually run in CI/local checks — until then the harness exists but is
  not enforced.
- This is the **first batch only**. The audit flagged `Board.tsx` (drag-and-drop
  via `@dnd-kit`) and `DetailDrawer.tsx` as the other unverified stateful
  components; add render/interaction tests for them next, following the
  `NeedsAction.test.tsx` pattern. Drag-and-drop will need `@dnd-kit` test
  helpers or simulated pointer events — scope that as its own follow-up.
- A reviewer should scrutinize: (1) that no production source under
  `dashboard/frontend/src/` was modified, (2) that `vitest run` (not watch) is
  the script so CI exits, and (3) that the api.test.ts assertions match the
  real endpoint URLs/methods in `api.ts` rather than a copied-but-stale list.
- If `api.ts` adds or changes endpoints later, `api.test.ts` must be updated in
  lockstep — these tests are the contract for the backend call shapes.
