# Atlas

A personal, local job-search cockpit. Discovers remote roles, scores fit, tailors a
CV per job, drafts outreach, detects referrals, and surfaces — in one dashboard — what's
**done**, what's **pending**, and **exactly what to send**. Runs on your Mac at **$0**
beyond an existing Claude Max subscription. Nothing is ever sent without your approval.

> Codename "Atlas" — deliberately bland. Nothing on screen advertises a job search.

## Cost model (read this first)

The recurring "brain" runs as a **Claude Cowork / Desktop scheduled task**, which draws
from your **subscription** usage — not metered API billing. As of **June 15, 2026**,
`claude -p` / the Agent SDK / Claude Code GitHub Actions moved to a *separate metered
credit*, so Atlas deliberately **never** uses those. Three safeguards keep it at $0:

1. Brain = Cowork/Desktop scheduled task (not `claude -p`).
2. **Disable usage-credits / overage billing** in your Claude account → fails *closed*.
3. **No `ANTHROPIC_API_KEY`** in your shell. Run `atlas doctor` to check.

## Quick start

```bash
uv sync                       # create the venv + install deps
uv run atlas doctor           # environment + $0 safeguards check
uv run atlas discover         # pull jobs into data/atlas.db
uv run atlas score            # score fit, shortlist
uv run atlas tailor <job_id>  # generate a parse-safe tailored CV (DOCX)
# dashboard:
uv run uvicorn dashboard.backend.main:app --port 8787
cd dashboard/frontend && npm install && npm run dev
```

See `docs` sections at the bottom of this file (added during build) for the full
architecture, the scheduled-task setup, and the keep-awake / fail-closed checklist.
