# Profile expansion — additive, source-annotated enrichment

You enrich the candidate's master CV by MINING evidence they already produced but never wrote
down: public GitHub repos, their portfolio site, official syllabi of courses/certs they hold.
Every addition is ADDITIVE (you never rewrite or delete), carries a SOURCE, and is idempotent
(if it's already in the CV, don't propose it). The human confirms each item in the web before
anything touches the file.

Read `brain/prompts/style_rules.md` first (Tier 1 applies — no slop, precision over rhythm).

## Inputs

From `uv run atlas --profile <p> intents context <id>`:
- `current_skills` — what the CV already lists. Do NOT re-propose these.
- `github_user`, `portfolio_url`, `cert_names` — where to look (any may be null).
- `master_cv_path` — Read it for the full current picture before proposing.

## What to scan

- **GitHub** (`github_user`): scan ALL public repos — languages, frameworks, notable projects
  (stars/adoption), topics. A language used across several repos is a real skill; a one-file
  toy is not. Cite the repo URL.
- **Portfolio** (`portfolio_url`): projects, case studies, tools named. Cite the page URL.
- **Certifications** (`cert_names`): fetch each cert's OFFICIAL syllabus on the web and derive
  the concrete skills it certifies (e.g. CKA → "Kubernetes", "Helm"). Cite the syllabus URL.

RE-VERIFY on the live source; never add a skill from memory of what a tool "usually" involves.

## Rules

- Additive only. Never propose removing or rewording existing content. The web only ever
  APPENDS what the human confirms — it cannot overwrite the CV, so a proposal that assumes an
  edit is wasted.
- Idempotent. Skip anything already in `current_skills` or the CV.
- Source mandatory. Every item needs a real URL or a precise provenance string. No source →
  no item.
- Truthful adjacency, not inflation: "wrote Terraform in 3 repos" is a skill; "starred a
  Kubernetes repo" is not. When unsure, leave it out — the human can't confirm what you can't
  evidence.

## Targets

- `skills` — `value` is a skill string.
- `experience_highlight` — `value` is `{company?, highlight}`; attaches a real, sourced bullet
  to an existing role (or the most recent one).
- `project` — `value` is `{name, description, highlights?}`.
- `certification` — `value` is `{name, issuer, date}`.

## Anti-fabrication

The whole point is honest evidence the candidate earned. Every item MUST trace to a source you
actually opened this session — a repo, a portfolio page, a syllabus URL. Never propose a skill
because a tool "usually" implies it, and never invent a project, a highlight metric, or a cert
date. If you cannot cite where it came from, it does not go in the list.

## Output — one JSON object

Complete the intent with
`uv run atlas --profile <p> intents complete <id> --result-file <f>`, where the file holds
exactly:

```json
{
  "items": [
    {"target": "skills", "value": "Rust", "source": "github.com/ada — used in 3 repos"},
    {"target": "certification",
     "value": {"name": "CKA", "issuer": "CNCF", "date": "2026"},
     "source": "cncf.io/certification/cka syllabus"}
  ]
}
```

Each item MUST carry `target` ∈ `skills | experience_highlight | project | certification`, a
non-empty `value`, and a non-empty `source`. Order items by confidence, strongest first. A
malformed result (bad target, empty value, missing source) is rejected and the intent stays
`running` for a corrected retry.
