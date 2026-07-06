# Plan 025: Vitest coverage for the two untested mutating components — SettingsModal and OnboardingGate

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 413ae10..HEAD -- dashboard/frontend/src/components/SettingsModal.tsx dashboard/frontend/src/components/OnboardingGate.tsx`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `413ae10`, 2026-07-06

## Why this matters

The vitest harness (plan 016) exists, but coverage stopped at Board/DetailDrawer/
NeedsAction/api. Since then the frontend grew several components; the two that **mutate
user state** with zero tests are `SettingsModal` (persists the download folder, the CSV
column design, and the profile display name) and `OnboardingGate` (marks onboarding
complete — the gate that reveals the whole board). A regression in either is silent
until a user loses a setting or gets locked in/out of the board. Both are small,
prop-driven, and cheap to test with the patterns already in the repo.

## Current state

Files:

- `dashboard/frontend/src/components/SettingsModal.tsx` — settings dialog; loads
  current values on open, saves via `api.*` calls.
- `dashboard/frontend/src/components/OnboardingGate.tsx` — pre-board checklist; the
  "complete" action calls `api.completeOnboarding()` then `onComplete()`.
- `dashboard/frontend/src/components/NeedsAction.test.tsx` — the structural exemplar
  for prop-driven tests (render → assert → userEvent → assert callback).
- `dashboard/frontend/src/components/DetailDrawer.test.tsx` — the exemplar for mocking
  the `api` module and `sonner` toasts.

Key excerpts:

`SettingsModal.tsx:15-35` — props and the on-open loads (four api calls):

```tsx
export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  ...
  useEffect(() => {
    if (!open) return;
    api.settings().then((s) => setDownloadDir(s.download_dir || ""));
    api.cvLibrary().then((l) => setCvLib({ dir: l.dir, count: l.count }));
    api.profiles().then((p) => { ... });
    api.csvColumns().then((c) => { setAvailable(c.available); setSelected(c.selected); });
  }, [open]);
```

`SettingsModal.tsx:37-63` — the three mutating actions: `saveProfileName()` →
`api.renameProfile(...)` + success/error toast; `saveDir()` → `api.setSetting("download_dir", ...)`;
`saveColumns()` → `api.setSetting("csv_columns", JSON.stringify(selected))`.

`OnboardingGate.tsx:34-53` — props `{ status, onComplete, onRefresh }`; the action:

```tsx
async function complete() {
  await api.completeOnboarding();
  onComplete();
}
```

`OnboardingGate.tsx:15-29` — `linkedinChecklist(target)` renders target-aware copy
(`hacia <target_label>` vs. neutral fallback) — a cheap behavior to pin.

Mocking convention (`DetailDrawer.test.tsx:8-30`): `vi.hoisted` for the mock objects,
then module mocks — follow it exactly:

```tsx
// vi.hoisted so the mocks exist before vi.mock's hoisted factories reference them.
...
vi.mock("sonner", () => ({ toast }));
vi.mock("../api", () => ({ api }));
```

Test runner config: `dashboard/frontend/vitest.config.ts` (jsdom + testing-library,
setup in `src/test/setup.ts`). Tests are colocated: `<Component>.test.tsx`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| FE tests | `npm --prefix dashboard/frontend test` | all pass (11 existing + new) |
| FE typecheck | `npm --prefix dashboard/frontend run typecheck` | exit 0 |
| FE lint | `npm --prefix dashboard/frontend run lint` | exit 0 (`--max-warnings 0`) |
| Full gate | `./scripts/check.sh` | `✓ All checks passed.` |

## Suggested executor toolkit

- Read `dashboard/frontend/DESIGN_SYSTEM.md` only if you must render assertions on
  styling — you should not need it (assert on text/roles, not classes).

## Scope

**In scope** (files to create; plus reading the components):

- `dashboard/frontend/src/components/SettingsModal.test.tsx` (create)
- `dashboard/frontend/src/components/OnboardingGate.test.tsx` (create)

**Out of scope** (do NOT touch):

- The components themselves — this is a characterization plan. If a test reveals a real
  bug, STOP and report; do not fix the component in this plan.
- `PortfolioViewer.tsx`, `InterviewPanel.tsx`, `CommandPalette.tsx`, `HelpGuide.tsx` —
  also untested but read-only/lower stakes; deliberately deferred.
- `src/test/setup.ts`, `vitest.config.ts` — the harness works; don't tune it.

## Git workflow

- Branch: `advisor/025-frontend-tests-settings-onboarding`.
- One commit per component test file, conventional style:
  `test(frontend): characterize SettingsModal save flows` /
  `test(frontend): characterize OnboardingGate completion`.
- Never `git add .` — add the new test files by name.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: SettingsModal tests

Create `dashboard/frontend/src/components/SettingsModal.test.tsx`, mocking `../api` and
`sonner` per the `DetailDrawer.test.tsx` pattern. The `api` mock must provide:
`settings`, `cvLibrary`, `profiles`, `csvColumns`, `setSetting`, `renameProfile` —
all `vi.fn()` returning resolved promises with minimal shapes (read the component's
usage at `SettingsModal.tsx:23-35` for the exact fields: `{ download_dir }`,
`{ dir, count }`, `{ active, profiles: [{ id, label }] }`, `{ available, selected }`).

Cases (4):

1. **loads current values on open** — render with `open={true}`, `await screen.findByDisplayValue(...)`
   for the mocked `download_dir`; assert the four load calls happened.
2. **does not load when closed** — render with `open={false}`; assert `api.settings`
   not called.
3. **saves the download dir** — type into the folder input, click its save button,
   assert `api.setSetting` called with `("download_dir", <typed value>)`.
4. **saves the profile name** — edit the profile-name input, click save, assert
   `api.renameProfile` called with the active id and trimmed label.

(Identify buttons/inputs by their accessible text/labels in the component JSX — read
the full file first; if a control has no accessible name, prefer `getByLabelText`/
`getByRole` over test-ids, matching the existing tests.)

**Verify**: `npm --prefix dashboard/frontend test` → new file passes.

### Step 2: OnboardingGate tests

Create `dashboard/frontend/src/components/OnboardingGate.test.tsx`, mocking `../api`
(`completeOnboarding: vi.fn().mockResolvedValue(...)`). Build a minimal
`OnboardingStatus` fixture from the type in `src/api.ts` (read it first — it needs at
least `audit.summary.high`, `audit.findings`, `cv_present`, `target_label`).

Cases (3):

1. **renders target-aware copy** — `target_label: "Arquitectura"` → text matches
   `/hacia Arquitectura/`; with `target_label: ""` → `/hacia tu rol objetivo/`.
2. **complete flow** — click the completion button; assert `api.completeOnboarding`
   called once and `onComplete` called after it resolves.
3. **refresh callback** — click the refresh control; assert `onRefresh` called
   (and `completeOnboarding` NOT called).

**Verify**: `npm --prefix dashboard/frontend test` → all pass.

### Step 3: Full gate

**Verify**: `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend run lint` →
exit 0; then `./scripts/check.sh` → passes.

## Test plan

This plan IS the test plan — 7 new tests across 2 files, modeled on
`NeedsAction.test.tsx` (structure) and `DetailDrawer.test.tsx` (mocking).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `npm --prefix dashboard/frontend test` exits 0 with ≥7 more tests than before
- [ ] Both new files exist and contain no `test.skip` / `it.skip`
- [ ] `npm --prefix dashboard/frontend run typecheck` and `run lint` exit 0
- [ ] No component source files modified (`git status` shows only the two new test files)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- A test reveals real component misbehavior (e.g. `saveProfileName` silently swallowing
  an error case you can trigger) — report the bug; do not fix the component here.
- The `api` mock shapes in `src/api.ts` have drifted from the component usage excerpts.
- You need to modify `setup.ts`/`vitest.config.ts` to make anything pass — that signals
  a harness assumption this plan didn't account for.

## Maintenance notes

- When SettingsModal grows a new persisted setting, its test file is now the place a
  reviewer should expect a matching case.
- Deferred (explicitly): PortfolioViewer/InterviewPanel/CommandPalette tests — read-only
  components; add them opportunistically when one of them next changes behavior.
