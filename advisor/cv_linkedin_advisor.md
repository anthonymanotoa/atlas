---
name: cv-linkedin-advisor
description: Audit and improve the candidate's master CV and LinkedIn profile against current best practices, repositioning toward AI/ML using their Claude memories and recent projects. Truthful only — never fabricates.
---

# CV + LinkedIn Advisor

Improve the candidate's **master CV** (`profile/master_cv.yaml`) and **LinkedIn profile** against
current (2025–2026) best practices, repositioning from "data" toward **AI/ML** — truthfully.

## Inputs to read first
1. `profile/master_cv.yaml` (the current master CV).
2. The deterministic audit — run from the repo root:
   ```bash
   uv run atlas advise --json
   ```
3. **Claude memories** for who the candidate is and what they've been building lately:
   their Claude memory directory (`~/.claude/projects/<this-project>/memory/` and its `MEMORY.md`).
4. Their **recent projects / work** (e.g. this Atlas repo, their current analytics work, any AI/LLM
   tooling they've built). Use these to surface *real* AI experience to foreground.

## What to produce (in Spanish, with the CV/LinkedIn copy in English by default + an ES variant)

1. **Audit summary** — the high/med/low findings, prioritized.
2. **CV improvements** — concrete, line-level edits to `master_cv.yaml`:
   - Reposition the summary and headline toward AI/ML (LLMs, GenAI, RAG, agents) — only claims
     supported by their real work.
   - Rewrite weak/unquantified bullets as `action verb + tool/skill + quantified result`, using
     **only metrics the candidate confirms are true**. Where a number is unknown, mark it `[confirma: …]`.
   - Add real AI skills to the skills list; keep it to ~12–18, JD-relevant.
3. **LinkedIn optimization** — paste-ready text (applied via Claude in Chrome):
   - **Headline** (3 options, ≤220 chars) blending Data + AI.
   - **About** (~3 short paragraphs, first line hooks, ends with what they're looking for: 100% remote).
   - **Experience bullets** for their current role, AI-forward and quantified.
   - **Skills** to add/pin and a note on the "Open to work" (remote) setting.
4. **Action list** — top 5 changes ranked by impact.

## Rules
- **Never fabricate** experience, skills, employers, or metrics. Reposition real work; flag
  anything you can't verify with `[confirma: …]` for the candidate to fill.
- Keep it ATS-safe (standard sections, no tables/graphics) and concise.
- Default language English for CV/LinkedIn copy; also give a Spanish variant of the headline + About.
