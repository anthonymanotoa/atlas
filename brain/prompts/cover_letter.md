# Cover letter drafter — company-researched, human-voiced

Read `brain/prompts/style_rules.md` FIRST. Tier 1 (anti-slop) and Tier 2 (conversational
voice) both apply here: this is outreach, not an ATS document. Run the recruiter-side risk
map from that file before writing. Every doubt it surfaces must be answered inside the
letter, by evidence or by honest framing of adjacent experience, never by hiding it.

This is a forward-looking letter, not a CV rehash. It argues why THIS candidate wants THIS
job at THIS company and what they would do in it. Do not restate the CV bullet by bullet.

## Inputs

From `uv run atlas --profile <p> intents context <id>`:
- `job` — title, company, description, url. The posting you are writing for.
- `master_cv_path` — Read this file. It is the EXCLUSIVE source of truth for what the
  candidate can claim. Anything not in it does not exist.
- `learnings` — what past outcomes taught us about this company (may be empty). Let it shape
  the angle; never contradict it.
- `existing_messages` — drafts already on this job (the deterministic cover letter, outreach).
  Do NOT duplicate them. Improve on them: sharper hook, better-matched evidence.

Research the company on the web before writing (site, product pages, engineering blog, recent
news). RE-VERIFY every company fact you use — product names, recent launches, stack, mission —
against a live source, never memory. An unverified fact does not go in the letter.

## Rules

- ≤ 250 words. Under 300 is the hard ceiling; 250 is the target. Three paragraphs:
  1. **Why THIS company** — one verified, specific hook (a product, a recent move, a problem
     they are solving). Not flattery, not "I admire your mission".
  2. **Evidence** — two proofs from the master CV matched to the JD's top needs, each in the
     bullet formula from style_rules.md (action + system/scope + tool + outcome + proof).
     These are the strongest match, not a full tour.
  3. **Honest close** — what you bring, one thing you would want to dig into, a plain call to
     action. Human hedging is allowed where honest ("I have not run X in production, but I
     built Y, which shares its core problem").
- Voice: Tier 2 conversational. Contractions are good. Write like a competent person talking
  to another competent person, not a press release.
- Anti-fabrication (identical to cv_review.md, non-negotiable):
  1. Sources of truth are EXCLUSIVE: the master CV + the provided context. Nothing else.
  2. Reformulate, never invent. "uses X" ≠ "built X"; exposure ≠ expertise; contribution ≠
     ownership.
  3. Silence on a topic beats manufactured detail.
  4. Metrics are read from the CV verbatim. Never invent one, never round one up, never merge
     two into a better-sounding number.
  5. Where there is a real gap, frame adjacent experience honestly. Never hide it.
- Language: `payload.language` if set, else the posting's language (`job` fields), else the
  profile's default.

## Output — exactly one JSON object

Becomes `atlas intents complete <id> --result-file`. `subject` and `body` are both required
and must be non-empty; `body` is plain text (real newlines between paragraphs, no markdown).

```json
{"subject": "<email subject>", "body": "<the letter, plain text>", "language": "en"}
```
