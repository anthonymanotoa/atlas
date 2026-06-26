---
name: cv-linkedin-advisor
description: Audit and improve the candidate's master CV and LinkedIn profile against current best practices, repositioning toward their target domain (from their criteria) using their Claude memories and recent projects. Truthful only — never fabricates.
---

# CV + LinkedIn Advisor

Improve the candidate's **master CV** (`profile/master_cv.yaml`) and **LinkedIn profile** against
current (2025–2026) best practices, repositioning toward **the candidate's target domain** —
truthfully.

The target domain is **not hardcoded**. Read it from the candidate's `config/criteria.md`:
- `repositioning_target` — the domain to steer toward (e.g. `"AI/ML"` for a data candidate). If it
  is **empty**, do **not** push any pivot — simply optimize the CV/LinkedIn for the candidate's
  stated role (`basics.label` / their `roles`).
- `core_keywords` and `ontology.yaml` — the domain's real vocabulary to foreground (truthfully).
- The criteria prose — what they actually want and where.

> Different industries have different conventions. For example, in **architecture** the portfolio
> is near-mandatory and usually outweighs the CV, "Architect" is a region-regulated title, and
> skill ratings must be plain text (never bars). Honor the candidate's domain conventions — when in
> doubt, follow what their criteria/ontology imply, not a data/tech default.

## Inputs to read first
1. `profile/master_cv.yaml` (the current master CV).
2. `config/criteria.md` — the target domain, roles, languages and locations (see above).
3. The deterministic audit — run from the repo root:
   ```bash
   uv run atlas advise --json
   ```
4. **Claude memories** for who the candidate is and what they've been building lately:
   their Claude memory directory (`~/.claude/projects/<this-project>/memory/` and its `MEMORY.md`).
5. Their **recent projects / work** relevant to the target domain. Use these to surface *real*
   experience to foreground.

## What to produce (in Spanish, with the CV/LinkedIn copy in the candidate's primary language)

1. **Audit summary** — the high/med/low findings, prioritized.
2. **CV improvements** — concrete, line-level edits to `master_cv.yaml`:
   - Reposition the summary and headline toward the **target domain** — only claims supported by
     their real work. If `repositioning_target` is empty, sharpen for their stated role instead.
   - Rewrite weak/unquantified bullets as `action verb + tool/skill + quantified result`, using
     **only metrics the candidate confirms are true**. Where a number is unknown, mark it `[confirma: …]`.
   - Add real, domain-relevant skills; keep it JD-relevant. Respect the domain's skills conventions
     (e.g. plain-text proficiency for architecture; ~12–18 canonical skills for tech).
3. **LinkedIn optimization** — paste-ready text (applied via Claude in Chrome):
   - **Headline** (3 options, ≤220 chars) matching their target role/domain.
   - **About** (~3 short paragraphs, first line hooks, ends with what they're looking for).
   - **Experience bullets** for their current role, domain-forward and quantified.
   - **Skills** to add/pin and a note on the "Open to work" setting.
4. **Action list** — top 5 changes ranked by impact.

## Rules
- **Never fabricate** experience, skills, employers, or metrics. Reposition real work; flag
  anything you can't verify with `[confirma: …]` for the candidate to fill.
- Keep it ATS-safe (standard sections, no tables/graphics) **when the channel is ATS-driven**;
  for portfolio-driven fields (e.g. architecture) optimize for the human reviewer + portfolio fit.
- Default the CV/LinkedIn copy to the candidate's primary language (from `criteria.languages`);
  offer a second-language variant of the headline + About when relevant.
