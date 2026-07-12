# Plan 030: Windows (WSL2) compatibility — remove the macOS hardcodes, make WSL a supported path

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c6875e3..HEAD -- engine/cli.py README.md AGENTS.md docs/SETUP.md .gitattributes tests/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: portability / docs
- **Planned at**: commit `c6875e3`, 2026-07-11

## Why this matters

Atlas is documented and coded as Mac-only ("corriendo 100% en tu Mac"), but the codebase is
already ~99% portable: paths resolve relative to the repo (`engine/paths.py`), there are no
hardcoded `/Users/...` paths, no plists/launchd, no macOS-only Python dependencies, and both
shell scripts are plain bash. A full audit (2026-07-11) found exactly **one** macOS-only code
path — `subprocess.run(["open", ...])` in `engine/cli.py:664` — plus three classes of
environmental hazard for a Windows user running Atlas under **WSL2** (the supported Windows
path; WSL2 is Linux, so everything POSIX already works):

1. **Line endings.** There is no `.gitattributes`. A user who clones on the Windows side with
   `core.autocrlf=true` gets CRLF in `scripts/*.sh`, which then fail under WSL bash
   (`/usr/bin/env bash\r: No such file or directory`).
2. **Repo location.** If the repo lives under `/mnt/c/...` (the Windows drive mounted via
   drvfs/9p), SQLite locking is unreliable and file IO / Vite watchers are extremely slow.
   Nothing warns about this today; `atlas doctor` is the natural home for that warning.
3. **Docs.** README, AGENTS.md and `docs/SETUP.md` say "Mac" everywhere and give
   Mac-only operational guidance (clamshell sleep, Claude Desktop on macOS). A Windows user
   has no setup path: how to install WSL2/uv/node, where to clone, how the scheduled brain
   invokes the repo through `wsl.exe`, and how to keep the PC awake.

Goal: after this plan, the same repo runs on macOS **and** on Windows via WSL2, with the docs
telling a Windows user exactly how to get there. Native Windows (no WSL) is explicitly out of
scope (see Scope).

## Current state

- `engine/cli.py:654-665` — the only macOS-only code path in the repo:

  ```python
  @portfolio_app.command("open")
  def portfolio_open() -> None:
      """Open the latest portfolio in your browser (local file)."""
      import subprocess

      with _db() as db:
          p = db.latest_portfolio()
      if not p:
          console.print("Sin portafolios. Corre `atlas portfolio generate`.")
          raise typer.Exit(1)
      subprocess.run(["open", p["path_html"]], check=False)  # noqa: S607 — local macOS open
      console.print(f"Abriendo {p['path_html']}")
  ```

- `engine/cli.py:70-107` — `doctor()` checks env vars and prints a manual checklist; it has
  no environment/filesystem checks. Lines 94-95 print the active profile and DB path — the
  new WSL warning slots naturally right after them.
- **No `.gitattributes`** at the repo root. `git ls-files` shows **no committed binary
  files** (no png/jpg/woff/pdf/docx tracked), so a blanket LF normalization is safe today;
  the binary patterns below are defensive for future assets.
- `README.md` Mac-specific wording (Spanish; keep the language and voice):
  - line 3: `**Tu centro de mando personal para la búsqueda de empleo**, corriendo 100% en tu Mac.`
  - line 274: `**Varias cuentas en la misma Mac (perfiles).** Atlas puede alojar varios perfiles`
  - line 318: `Atlas corre **enteramente en tu Mac**. Nada de lo personal sale de tu equipo ni se sube a`
  - line 324: `` `.gitignore`: lo personal vive solo en tu Mac y **nunca** debe commitearse. ``
- `AGENTS.md:5`: `everything in a local dashboard. It runs on the user's Mac at **$0** (subscription-funded).`
- `docs/SETUP.md` section 2 ("Keep the scheduled brain reliable") is Mac-only:

  ```
  The brain (`atlas-job-brain`, daily 8:10am) only runs while your Mac is **awake** and **Claude
  Desktop is open**, and a missed day collapses to one catch-up run.
  - [ ] Claude Desktop → Settings → enable **"Keep computer awake"**, and keep the app running.
  - [ ] Don't close the laptop lid during the scheduled window (clamshell sleeps the Mac).
  ```

- Already portable — verified, do NOT "fix": `engine/paths.py` (repo-relative, env
  overrides), `scripts/run.sh` / `scripts/check.sh` (plain bash, run fine under WSL),
  `brain/run_brain.py` (no subprocess), all Python deps in `pyproject.toml` (pure-python or
  manylinux wheels), the dashboard (binds `127.0.0.1`; WSL2 forwards localhost to Windows),
  no `fcntl`/`os.startfile`/platform-specific `strftime` anywhere.
- Conventions: `from __future__ import annotations` in engine modules; ruff line-length 100;
  tests live flat in `tests/test_*.py` and use `monkeypatch` (see `tests/test_f3_*.py`).

## Commands you will need

| Purpose      | Command                                              | Expected on success |
|--------------|------------------------------------------------------|---------------------|
| Sync deps    | `uv sync`                                            | exit 0              |
| Python tests | `uv run pytest`                                      | exit 0, all pass    |
| Lint         | `uv run ruff check . && uv run ruff format --check .`| exit 0              |
| Renormalize  | `git add --renormalize . && git status --short`      | no unexpected changes |
| Full gate    | `./scripts/check.sh`                                 | exit 0              |

## Scope

**In scope** (the only files you should modify/create):
- `engine/cli.py` (cross-platform open helper; WSL warning in `doctor`)
- `.gitattributes` (new)
- `docs/SETUP.md` (Windows/WSL2 section; per-OS keep-awake bullets)
- `README.md` (de-Mac the wording; pointer to the WSL2 section)
- `AGENTS.md` (line 5 wording)
- `tests/test_cli_open.py` (new)
- `.github/workflows/ci.yml` (new — **optional Step 6 only**)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch, even though it looks related):
- **Native Windows (no WSL) support.** `uvicorn[standard]` pulls uvloop (POSIX-only), the
  launcher scripts are bash, and nothing here is tested on win32. WSL2 is the supported
  Windows path; say so in the docs instead of chasing win32.
- `engine/paths.py`, `scripts/run.sh`, `scripts/check.sh` — already portable; no speculative
  refactors.
- The brain SKILL/prompts, dashboard backend/frontend code — no platform assumptions found.
- Rewriting SETUP.md beyond the additions described here (plan 022/026 own doc accuracy).

## Git workflow

- Branch: current session branch; conventional commits, e.g.
  `feat(compat): cross-platform portfolio open + WSL-aware doctor` and
  `docs(setup): Windows via WSL2 supported path`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Cross-platform `_open_local_file` in `engine/cli.py`

Add a module-level helper near the portfolio commands (~line 650), and route
`portfolio_open` through it:

```python
def _open_local_file(path: str) -> bool:
    """Open a local file with the platform's default handler (best-effort).

    macOS → `open`; Linux/WSL → `wslview` (WSL bridge to the Windows browser,
    from the `wslu` package) or `xdg-open`, whichever exists. Returns False when
    no opener is available so the caller can print the path instead.
    """
    import shutil
    import subprocess
    import sys

    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)  # noqa: S607 — local macOS open
        return True
    for cmd in ("wslview", "xdg-open"):
        if shutil.which(cmd):
            subprocess.run([cmd, path], check=False)
            return True
    return False
```

In `portfolio_open`, replace the `import subprocess` + `subprocess.run(["open", ...])` pair with:

```python
    if _open_local_file(p["path_html"]):
        console.print(f"Abriendo {p['path_html']}")
    else:
        console.print(f"No encontré con qué abrirlo — ábrelo manualmente: {p['path_html']}")
```

**Verify**: `grep -n '\["open"' engine/cli.py` → 0 matches.
**Verify**: `uv run atlas portfolio open` on the dev Mac still opens (or prints "Sin
portafolios" if none exist — either proves the command imports and runs).

### Step 2: Pin the helper with tests

Create `tests/test_cli_open.py` (match the repo's monkeypatch style). Three cases:

1. **darwin dispatch** — `monkeypatch.setattr(sys, "platform", "darwin")`, monkeypatch
   `subprocess.run` with a recorder; assert `_open_local_file("/x.html")` returns True and
   the recorded argv is `["open", "/x.html"]`.
2. **linux + wslview** — `monkeypatch.setattr(sys, "platform", "linux")`, monkeypatch
   `shutil.which` to return a path only for `"wslview"`, record `subprocess.run`; assert
   argv is `["wslview", "/x.html"]`.
3. **linux, no opener** — `shutil.which` always None; assert the helper returns `False`
   and `subprocess.run` was never called.

(The helper imports `sys`/`shutil`/`subprocess` locally, but monkeypatching the modules'
attributes globally — `sys.platform`, `shutil.which`, `subprocess.run` — reaches them.)

**Verify**: `uv run pytest tests/test_cli_open.py -q` → 3 passed.

### Step 3: `.gitattributes` + renormalize check

Create `.gitattributes` at the repo root:

```gitattributes
# LF everywhere, on every platform. A Windows-side clone with core.autocrlf=true would
# otherwise checkout CRLF and break scripts/*.sh under WSL bash.
* text=auto eol=lf
*.sh text eol=lf

# Defensive: keep future binary assets untouched (none are tracked today).
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.woff binary
*.woff2 binary
*.ttf binary
*.otf binary
*.pdf binary
*.docx binary
```

**Verify**: `git add --renormalize . && git status --short` → shows ONLY the files this plan
already touched plus `.gitattributes` itself. Any *other* file appearing here means it had
CRLF endings — STOP condition.

### Step 4: Docs — Windows (WSL2) setup path

**4a. `docs/SETUP.md`** — replace the two Mac-only bullets in section 2 with per-OS bullets:

```markdown
- [ ] Claude Desktop → Settings → enable **"Keep computer awake"**, and keep the app running.
- [ ] macOS: don't close the laptop lid during the scheduled window (clamshell sleeps the Mac).
- [ ] Windows: Settings → System → Power → set **Sleep: Never** while plugged in (the brain
      can't run on a sleeping PC), and note the brain command must enter WSL (section 5).
```

Also reword the section-2 intro `only runs while your Mac is **awake**` →
`only runs while your machine is **awake**`.

Then append a new section at the end of the file:

```markdown
## 5. Windows — supported via WSL2

Atlas on Windows runs **inside WSL2** (it is Linux; everything below happens in the WSL
terminal unless noted). Native Windows (no WSL) is not supported.

- [ ] Install WSL2 + Ubuntu (PowerShell, admin): `wsl --install -d Ubuntu`, reboot, create
      your Linux user.
- [ ] **Clone inside the Linux filesystem** (e.g. `~/dev/atlas`) — **never under `/mnt/c`**:
      SQLite locking and file watchers are unreliable/slow on the Windows-drive mount.
      `atlas doctor` warns if it detects this.
- [ ] Install tooling inside WSL: `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
      and Node 20+ (e.g. via `nvm`). Then the normal flow works as-is:
      `./scripts/check.sh`, `./scripts/run.sh`.
- [ ] Dashboard: `./scripts/run.sh` inside WSL, then open http://127.0.0.1:8787 in your
      **Windows** browser (WSL2 forwards localhost automatically).
- [ ] (Optional) `sudo apt install wslu` so `atlas portfolio open` can open files in the
      Windows browser via `wslview`; without it the CLI prints the path for you to open.
- [ ] **Scheduled brain:** Claude Desktop for **Windows** runs the task, but the repo lives
      in WSL — the task's shell command must enter WSL, e.g.:
      `wsl.exe -e bash -lc 'cd ~/dev/atlas && uv run atlas --profile owner brain --limit 8 --json'`
      (adapt the inner command to whatever the task runs today).
- [ ] Git line endings are enforced by `.gitattributes` (LF). If you cloned before that file
      existed, run `git config core.autocrlf input` and re-checkout.
```

**4b. `README.md`** — minimal wording pass (keep Spanish, keep voice):
- line 3: `corriendo 100% en tu Mac.` → `corriendo 100% en tu máquina (macOS, o Windows vía WSL2).`
- line 274: `**Varias cuentas en la misma Mac (perfiles).**` → `**Varias cuentas en la misma máquina (perfiles).**`
- line 318: `Atlas corre **enteramente en tu Mac**.` → `Atlas corre **enteramente en tu máquina**.`
- line 324: `lo personal vive solo en tu Mac` → `lo personal vive solo en tu máquina`
- Near the existing pointer to `docs/SETUP.md` (line ~92), add one sentence:
  `En Windows, Atlas corre dentro de WSL2 — ver la sección "Windows" de docs/SETUP.md.`

**4c. `AGENTS.md:5`** — `It runs on the user's Mac at **$0**` →
`It runs on the user's machine (macOS, or Windows via WSL2) at **$0**`.

**Verify**: `grep -rniE "tu mac\b|la misma mac|user's mac" README.md AGENTS.md docs/SETUP.md` → 0 matches.
**Verify**: `grep -n "WSL2" docs/SETUP.md README.md AGENTS.md` → matches in all three.

### Step 5: WSL-aware `atlas doctor`

In `engine/cli.py`, add a helper near `doctor()`:

```python
def _wsl_repo_warning() -> str | None:
    """On WSL, warn when the repo lives on a Windows drive (/mnt/*): drvfs breaks SQLite
    locking and slows IO — the repo belongs in the Linux filesystem (e.g. ~/dev/atlas)."""
    try:
        osrelease = Path("/proc/sys/kernel/osrelease").read_text()
    except OSError:
        return None  # not Linux/WSL
    if "microsoft" not in osrelease.lower():
        return None
    if str(paths.REPO_ROOT).startswith("/mnt/"):
        return (
            f"WSL detectado y el repo vive en {paths.REPO_ROOT} (disco de Windows). "
            "Muévelo al filesystem de Linux (p. ej. ~/dev/atlas): SQLite y los watchers "
            "no son confiables sobre /mnt/*."
        )
    return None
```

In `doctor()`, right after the `DB path` line (line ~95):

```python
    wsl_warn = _wsl_repo_warning()
    if wsl_warn:
        console.print(f"[yellow]![/] {wsl_warn}")
```

(Warning only — do not flip `ok` to False; a `/mnt` repo still runs, just badly.)
Check `Path` is already imported in `engine/cli.py` (it is used elsewhere; if not, import it).

**Verify**: `uv run atlas doctor` on the dev Mac → output unchanged (no WSL line), exit code
unchanged.
**Verify**: `uv run pytest` → all pass.

### Step 6 (OPTIONAL — confirm with the operator first): Linux CI as a standing WSL-parity gate

"Works on WSL" ≈ "works on Linux". The cheapest durable guarantee is a GitHub Actions job on
`ubuntu-latest` running the existing full gate. The repo is public, so Actions is free. If
the operator declines CI, skip this step cleanly and note it in the index row.

Create `.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [master]
  pull_request:
jobs:
  linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: ./scripts/check.sh
```

**Verify** (if executed): push the branch, `rtk gh run list` → the `ci` run for this branch
completes green. If any test fails on Linux but passes on macOS, that IS the plan's payoff —
report the failing test as a finding (STOP condition below), don't patch around it.

### Step 7: Full gate + index row

**Verify**: `./scripts/check.sh` → exit 0.
**Verify**: `git status --short` → only in-scope files modified.
Update this plan's row in `plans/README.md`.

## Test plan

- 3 new unit tests for `_open_local_file` (Step 2) — darwin dispatch, WSL/linux `wslview`
  dispatch, graceful no-opener fallback.
- `_wsl_repo_warning` is exercised implicitly (returns `None` on macOS — doctor output
  unchanged); a dedicated unit test is optional: monkeypatch `Path.read_text` to return
  `"5.15.microsoft-standard-WSL2"` and `paths.REPO_ROOT` to `/mnt/c/x`, assert a warning
  string is returned. Add it if cheap in the file from Step 2.
- Existing suite (`uv run pytest`, 508+ tests) is the regression net; frontend untouched
  except via `check.sh`.
- The optional CI job (Step 6) is the ongoing verification that the whole stack stays green
  on Linux/WSL.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n '\["open"' engine/cli.py` → 0 matches; `grep -n "_open_local_file" engine/cli.py` → ≥2 matches
- [ ] `grep -n "_wsl_repo_warning" engine/cli.py` → ≥2 matches
- [ ] `.gitattributes` exists; `git add --renormalize .` introduces no changes beyond this plan's files
- [ ] `grep -rniE "tu mac\b|la misma mac|user's mac" README.md AGENTS.md docs/SETUP.md` → 0 matches
- [ ] `grep -c "WSL2" docs/SETUP.md` → ≥3 (the new section exists)
- [ ] `uv run pytest` exits 0 including the new tests; `uv run ruff check .` and `uv run ruff format --check .` exit 0
- [ ] `./scripts/check.sh` exits 0
- [ ] `git status --short` shows only in-scope files
- [ ] `plans/README.md` status row updated (noting whether Step 6 ran)

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts in "Current state" don't match the live code (drift).
- Step 3's renormalize shows changes in files this plan did NOT touch — some tracked file
  has CRLF endings; report which, don't blanket-commit a whitespace storm.
- Any EXISTING test fails after Steps 1/5 — the helper or doctor change broke an assumed
  contract; report the failing test.
- Step 6's Linux CI run fails on a test that passes on macOS — that's a real
  Linux-portability bug this plan was designed to surface; report it as a finding rather
  than patching test or code ad hoc.
- You find another `subprocess` call or macOS-only invocation not listed here
  (`grep -rn "subprocess\|os.system\|os.startfile" engine/ brain/ dashboard/backend/ --include="*.py"`
  should show only `engine/cli.py`) — the audit missed something; report it.

## Maintenance notes

- New code that opens files/URLs must go through `_open_local_file` (or `webbrowser` for
  http URLs) — reviewers should flag any fresh `subprocess.run(["open", ...])`.
- WSL2 is the supported Windows story. If native win32 is ever wanted: uvloop
  (`uvicorn[standard]`) is POSIX-only, `scripts/*.sh` need PowerShell twins, and the whole
  suite needs a win32 CI leg — treat that as its own plan.
- If binary assets (images/fonts/docs) are ever committed, confirm their extension is in
  `.gitattributes`' binary list before merging.
