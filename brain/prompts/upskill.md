# Upskill / gap analysis — study plan from your real pipeline

Two passes produce this report. Pass 1 is DONE for you (deterministic): the context's
`hard_gaps` is the weighted inventory of skills your CV does not evidence across the jobs in
scope, where jobs you fit WORST weigh most (`score = Σ (100 − fit_score)/100`). Your job is
pass 2: turn that inventory into a prioritized, personalized study plan.

Read `brain/prompts/style_rules.md` first (Tier 1 applies — this is a report, not outreach).

## Inputs

From `uv run atlas --profile <p> intents context <id>`:
- `hard_gaps.skills` — `[{skill, score, occurrences, worst_fit, jobs}]`, already ranked. The
  `score` is the ONLY ranking signal; do not re-rank by gut feeling. `occurrences` is how many
  in-scope jobs demanded it; `worst_fit` is the worst fit_score among those jobs.
- `hard_gaps.jobs_considered` — how many jobs the pass ran over. If it is 0, there is nothing
  to analyze: say so honestly and stop (still emit valid JSON with an empty heatmap).
- `previous_report` — the last report (or null). Use it for the diff section below.
- Read `master_cv_path` if you need to judge adjacency ("they already know Docker").

## What to produce

Synthesize gaps into FOUR buckets, each gap tagged by kind: **domain** (a field/industry),
**soft** (leadership, comms), **tooling** (a concrete tech), **credential** (a cert/degree
some postings gate on). The literal keyword diff surfaces mostly tooling; you add the domain /
soft / credential gaps it misses by reading the JDs and the master CV. Group the study plan by
kind, not by raw skill.

For each skill worth acting on:
- A **severity** for the heatmap: `Critical` (blocks many high-fit jobs), `High`, `Medium`,
  `Low` (nice-to-have). Severity is your judgment informed by `score` + how many jobs it
  gates — a high `score` on a single job is not Critical.
- **Personalized direction**: read the master CV and skip what they already have ("you know
  Docker, skip the container-basics module, start at Helm").
- **Concrete resources** found on the WEB. Search with the current year in the query (e.g.
  "best Kubernetes course 2026") so you don't recommend stale material. Prefer official docs
  and well-known courses; give a real title/URL, never "search for a course on X".
- **Estimated hours** and **dependency order** ("learn Docker before Kubernetes before
  Helm"). Present the plan as an ordered path, not a flat list.

## Diff vs the previous report

If `previous_report` is not null, add a `## Cambios desde el último reporte` section:
which gaps CLOSED (in the old heatmap, gone or downgraded now), which are NEW, which
persist. If it is null, say this is the first report.

## Anti-fabrication

Never claim the candidate has a skill they lack — the whole point is honest gaps. Do not
invent a job's requirements: only skills in `hard_gaps` (which came from real JDs) qualify as
tooling gaps, and domain/soft/credential gaps must be traceable to the JDs or the master CV.
Resource claims (hours, provider, title, URL) must come from a page you actually checked this
session — never from memory. If you could not verify a resource, say "verify availability"
rather than inventing a link.

## Output — one JSON object

Complete the intent with `uv run atlas --profile <p> intents complete <id> --result-file <f>`,
where the file holds exactly:

```json
{
  "report_md": "# Plan de upskilling\n\n## Tooling\n### Kubernetes (Critical)\n…markdown…",
  "heatmap": [
    {"skill": "Kubernetes", "severity": "Critical", "note": "gate en 4 vacantes de mejor fit"},
    {"skill": "Go", "severity": "Medium", "note": "adyacente a tu Python; 20h estimadas"}
  ]
}
```

`report_md` is the full study plan (Markdown, in the profile's language). `heatmap` is the
compact severity view the web renders as chips. Every heatmap `severity` ∈
`Critical | High | Medium | Low`. One heatmap entry per skill you took a position on. Every
entry needs a non-empty `skill` — a malformed result is rejected and the intent stays
`running` for a corrected retry.
