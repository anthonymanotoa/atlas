# Atlas

A personal, local **job-search cockpit**. It discovers remote roles, scores fit, tailors a
CV per job (ATS-optimized), drafts outreach, detects referrals, and surfaces — in one
dashboard — what's **done**, what's **pending**, and **exactly what to send**. Runs on your
Mac at **$0** beyond an existing Claude Max subscription. **Nothing is ever sent without your
approval.**

> Codename "Atlas" — deliberately bland. Nothing on screen advertises a job search.

---

## Cost model — how this stays at $0 (read first)

The recurring "brain" runs as a **Claude Cowork / Desktop scheduled task**, which draws from
your **subscription** usage — not metered API billing. As of **June 15, 2026**, `claude -p`,
the Agent SDK, and Claude Code GitHub Actions moved to a *separate metered Agent SDK credit*,
so Atlas deliberately **never** uses those. Three safeguards make $0 a guarantee, not a hope:

1. **Brain = a Cowork/Desktop scheduled task** (already created as `atlas-job-brain`), never
   `claude -p` / Agent SDK / cloud Routines.
2. **Disable usage-credits / overage billing** in your Claude account → the system fails
   *closed* (work stops instead of billing).
3. **No `ANTHROPIC_API_KEY`** in your shell. `uv run atlas doctor` checks this.

Everything else — JobSpy, the ATS/Himalayas/Adzuna APIs, SQLite, the local dashboard, Claude
in Chrome — is $0. See [docs/SETUP.md](docs/SETUP.md) for the one-time checklist.

---

## How it works

```
┌── Claude Code (you, interactive) ── builds + maintains the machinery
│
├── data store (the brain reads/writes):
│     profile/master_cv.yaml · config/criteria.md · config/companies.yaml · data/atlas.db
│
├── engine/ (deterministic Python, no LLM):
│     discovery → scoring → CV tailoring → outreach → referrals → SQLite tracker
│
├── brain/  ── daily Cowork scheduled task (subscription): runs the engine, drafts, NEVER sends
│
└── dashboard/ ── local web app (FastAPI + React): Needs-Action · Kanban · "exactly what to send"
```

**Discovery** spine is direct keyless ATS feeds (Greenhouse/Lever/Ashby/SmartRecruiters) +
Indeed, with LinkedIn-guest (account-safe, capped) and Himalayas/Adzuna as a stable baseline.
**Sending** is always human-in-the-loop: company forms via Claude-in-Chrome (you submit),
email as Gmail drafts (the connector can't send by design), LinkedIn semi-manual.

---

## Quick start

```bash
uv sync                                   # create venv + install deps
uv run atlas doctor                       # check the $0 safeguards
uv run atlas discover                     # pull jobs into data/atlas.db
uv run atlas score                        # score fit + shortlist
uv run atlas prep <job_id>                # tailor CV + draft outreach + build the send package
uv run atlas brain                        # the full daily pipeline (what the scheduled task runs)

# dashboard (two terminals, or build once and serve from FastAPI):
npm --prefix dashboard/frontend install && npm --prefix dashboard/frontend run build
uv run uvicorn dashboard.backend.main:app --port 8787   # → http://127.0.0.1:8787
# dev mode: npm --prefix dashboard/frontend run dev      # → http://localhost:5173 (proxies /api)
```

## Commands

| Command | Does |
|---|---|
| `atlas doctor` | Environment + $0 safeguard check |
| `atlas discover [--only ats,jobspy,…]` | Pull jobs (idempotent) |
| `atlas score [--rescore]` | Score fit, shortlist |
| `atlas tailor <id> [--language es]` | Parse-safe tailored CV (DOCX + optional PDF) |
| `atlas outreach <id>` | Draft cover/recruiter/HM/referral/cold/note |
| `atlas prep <id>` | tailor + outreach + send-ready `package.md` |
| `atlas brain [--limit N]` | Full daily pipeline + Spanish morning brief |
| `atlas referrals` | Jobs where you have a 1st-degree connection |
| `atlas import-connections <csv>` | Import LinkedIn `Connections.csv` |
| `atlas advise [--json]` | Audit your CV; pairs with the `cv-linkedin-advisor` skill |
| `atlas top [--n] [--state]` · `atlas status` | Inspect the pipeline |

## Configure it for you

- `config/criteria.md` — roles, remote, seniority, salary floor, deal-breakers (YAML frontmatter
  + prose). Copy from `criteria.example.md`.
- `config/companies.yaml` — target companies + their ATS (`atlas resolve-ats <careers-url>` helps).
- `profile/master_cv.yaml` — your structured CV (seed it via the `cv-linkedin-advisor` skill /
  Claude in Chrome). Copy from `master_cv.example.yaml`.
- `config/sources.yaml` — search terms + source toggles. `.env` — optional free Adzuna keys.

## Privacy

Your CV, contacts, drafts and `tracker.db` live under `profile/` and `data/` and are
**gitignored** — only code is pushed to GitHub (private repo). LinkedIn is never logged into by
the scraper (guest only); referral detection uses your own `Connections.csv` export.

See [docs/SETUP.md](docs/SETUP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
