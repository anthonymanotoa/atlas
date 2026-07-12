# Atlas — one-time setup checklist

## 1. Guarantee $0 (do this once)
- [ ] **Disable usage credits / overage billing** in your Claude account settings. This makes
      Atlas fail *closed* — when the subscription window or any credit is exhausted, work stops
      instead of billing API rates. (Anthropic Help Center: "Manage usage credits".)
- [ ] Confirm no `ANTHROPIC_API_KEY` in your shell: `uv run atlas doctor` (it warns if found).
- [ ] In Claude Code, run `/status` and confirm it shows your **Max subscription**, not
      "API Usage Billing".

## 2. Keep the scheduled brain reliable
The brain (`atlas-job-brain`, daily 8:10am) only runs while your machine is **awake** and **Claude
Desktop is open**, and a missed day collapses to one catch-up run.
- [ ] Claude Desktop → Settings → enable **"Keep computer awake"**, and keep the app running.
- [ ] macOS: don't close the laptop lid during the scheduled window (clamshell sleeps the Mac).
- [ ] Windows: Settings → System → Power → set **Sleep: Never** while plugged in (the brain
      can't run on a sleeping PC), and note the brain command must enter WSL (section 5).
- [ ] The dashboard shows an **"Estuve sin correr ~Nh"** banner if a run was missed — that's your
      alarm. (Notifications are on; absence of a completion ping also signals downtime.)
- [ ] First run: open the task in Claude Desktop → **Run now** once, and "always allow" the tools
      it needs (Bash to the repo, the Gmail connector) so future runs don't stall on prompts.

## 3. Seed your data
- [ ] **Master CV:** `cp profile/master_cv.example.yaml profile/master_cv.yaml`, then use the
      `cv-linkedin-advisor` guide (`advisor/cv_linkedin_advisor.md`) — it reads your LinkedIn via
      Claude in Chrome + your Claude memories/projects and repositions toward AI/ML, truthfully.
      Replace every placeholder value with your own real data.
- [ ] **Criteria:** `cp config/criteria.example.md config/criteria.md` and adjust.
- [ ] **Companies:** `cp config/companies.example.yaml config/companies.yaml`; add your targets
      (use `uv run atlas resolve-ats <careers-url>` to find each one's ATS + token).
- [ ] **Referrals:** LinkedIn → Settings → Data privacy → *Get a copy of your data* →
      **Connections** → download `Connections.csv` into `data/inbox/`, then
      `uv run atlas import-connections data/inbox/Connections.csv`. (Account-safe; no scraping.)
- [ ] **(Optional) Adzuna:** free keys at developer.adzuna.com → put in `.env`.
- [ ] **PDF export:** nothing to install — `atlas tailor` renders the PDF natively via
      `reportlab`. (DOCX is the ATS-preferred default and is always produced too.)

## 4. Daily loop
1. The brain runs at ~8am and writes `data/outbox/MORNING_BRIEF.md` + per-job `package.md`s.
2. Open the dashboard (`uv run uvicorn dashboard.backend.main:app --port 8787`).
3. Work the **Acciones para hoy** rail: prefer referrals, then send applications. Each job's
   drawer has the apply link, the tailored CV (download), and every message draft (copy / mark
   sent). You send; Atlas tracks.
4. Follow-ups are scheduled automatically and **halt the moment you mark a reply**.

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
- [ ] Git line endings are enforced by `.gitattributes` (LF), so a fresh clone is always
      correct. If you cloned BEFORE that file existed and your `scripts/*.sh` already have CRLF,
      a plain re-checkout won't fix them (git leaves files it thinks are unchanged) — force a
      renormalization once: `git rm --cached -r . && git reset --hard`.
