---
name: cv-linkedin-advisor
description: Audit and improve Anthony's master CV and LinkedIn profile against current best practices, repositioning toward AI/ML using his Claude memories and recent projects. Truthful only — never fabricates.
---

# CV + LinkedIn Advisor

Improve Anthony's **master CV** (`profile/master_cv.yaml`) and **LinkedIn profile** against
current (2025–2026) best practices, repositioning from "data" toward **AI/ML** — truthfully.

## Inputs to read first
1. `profile/master_cv.yaml` (the current master CV).
2. The deterministic audit — run:
   ```bash
   cd /Users/anthonymanotoa/dev/personal/atlas && uv run atlas advise --json
   ```
3. **Claude memories** for who he is and what he's been building lately:
   `/Users/anthonymanotoa/.claude/projects/-Users-anthonymanotoa-dev-personal/memory/` and its `MEMORY.md`.
4. His **recent projects / work** (e.g. this Atlas repo, his Trafilea analytics work, any AI/LLM
   tooling he's built). Use these to surface *real* AI experience to foreground.

## What to produce (in Spanish, with the CV/LinkedIn copy in English by default + an ES variant)

1. **Audit summary** — the high/med/low findings, prioritized.
2. **CV improvements** — concrete, line-level edits to `master_cv.yaml`:
   - Reposition the summary and headline toward AI/ML (LLMs, GenAI, RAG, agents) — only claims
     supported by his real work.
   - Rewrite weak/unquantified bullets as `action verb + tool/skill + quantified result`, using
     **only metrics he confirms are true**. Where a number is unknown, mark it `[confirma: …]`.
   - Add real AI skills to the skills list; keep it to ~12–18, JD-relevant.
3. **LinkedIn optimization** — paste-ready text (he applies it via Claude in Chrome):
   - **Headline** (3 options, ≤220 chars) blending Data + AI.
   - **About** (~3 short paragraphs, first line hooks, ends with what he's looking for: 100% remote).
   - **Experience bullets** for his current Trafilea role, AI-forward and quantified.
   - **Skills** to add/pin and a note on the "Open to work" (remote) setting.
4. **Action list** — top 5 changes ranked by impact.

## Rules
- **Never fabricate** experience, skills, employers, or metrics. Reposition real work; flag
  anything you can't verify with `[confirma: …]` for Anthony to fill.
- Keep it ATS-safe (standard sections, no tables/graphics) and concise.
- Default language English for CV/LinkedIn copy; also give a Spanish variant of the headline + About.
