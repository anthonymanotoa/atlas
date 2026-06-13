# Atlas — Supervised social search (LinkedIn / X)

> **Supervised, human-in-the-loop, account-safe.** This flow is run by *you* in a
> Claude-in-Chrome session on your own browser — never unattended, never automated at
> speed. The brain (scheduled task) NEVER runs this and NEVER contacts anyone.

## When
You clicked **"Buscar reclutador"** on a job in the dashboard. That queued the job in
`pending_searches`. This skill helps you find who's hiring and add useful context —
then *you* decide whether/how to reach out.

## Steps
1. **Get the queue + queries.** `GET /api/pending-searches` lists queued jobs. For a job,
   `POST /api/jobs/{id}/start-social-search` returns ready-to-paste queries
   (`linkedin_recruiters`, `linkedin_posts`, `x`).
2. **Search slowly, by hand, in your own Chrome.** Open ONE query at a time. Read the
   page. Do **not** rapidly paginate, bulk-open profiles, or scrape lists.
   **Respect the guardrails in `docs/RATE_LIMITING.md`** (one search at a time,
   human-speed, randomized pauses, hard cap per session).
3. **Confirm what's real.** A recruiter/hiring-manager profile or a hiring post about
   *this* vacancy. Verify the full URL before trusting any link.
4. **Save it.** `POST /api/jobs/{id}/social_mentions` with
   `{platform, source_url, recruiter_name, recruiter_linkedin, recruiter_email,
   post_title, post_excerpt, context_type}`. It stores the mention and clears the queue.
5. **Reaching out is your call.** Draft a note if you want (use the outreach templates),
   but **you** send it manually (LinkedIn DM / InMail / the recruiter's channel). The
   system never sends or connects on your behalf.

## Hard rules
- Never log in *as automation* or drive LinkedIn at machine speed — guest/IP-throttle is
  recoverable; an account flag is not. Slower is always fine.
- Never auto-contact. Capture context; the human contacts.
- $0: no paid APIs, no proxies. Just your own browser + Claude-in-Chrome.
