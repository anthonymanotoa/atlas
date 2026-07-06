# Deep interview prep — audience-mapped, source-cited, story-matched

Read `brain/prompts/style_rules.md` first (Tier 1). This upgrades the deterministic prep doc
(`context.deterministic_prep`) into a round-specific pack. Do NOT throw the baseline away —
it already has real STAR evidence and JD-gap topics; you sharpen and extend it.

## Inputs

From `atlas intents context <id>`:
- `interview` — round, mode, scheduled_at.
- `interviewers` — the confirmed people (name, title, linkedin_url, research_notes).
- `job` — title/company/description/url.
- `deterministic_prep` — the baseline prep doc (Markdown). Your floor, not your ceiling.
- `matched_stories` — ranked stories from the STAR+R story bank (may be empty).
- `debrief_md` — the candidate's debrief from a PRIOR round of this same interview (or null).
  If present, it is real performance data: let it steer where you go deep or ease off.
- `master_cv_path` — Read it. The EXCLUSIVE source of what the candidate has actually done.

Research the company and each interviewer on the web before writing. RE-VERIFY every fact you
cite; unverified facts do not appear.

## Audience Map (the core of this prep)

Infer the round type from `interview.round` and build the pack for THAT audience:
- **recruiter-screen** (`phone`) — motivation, logistics (comp, location, timeline), a
  60-second pitch, no deep tech. Anticipate the knockout questions (visa, salary, notice).
- **hiring-manager** (`hiring_manager`) — ownership stories, judgment under ambiguity,
  why-this-team. Map each likely question to a story from `matched_stories` (or the CV).
- **peer-tech** (`technical` / `system_design`) — hands-on depth in the JD's stack; be ready
  to whiteboard/trace.
- **panel-mixed** (`final` / `other`) — cover all of the above; label which panelist each
  block targets.

For EACH interviewer with research_notes, add one line: what they likely probe, and which of
your stories answers it.

## Question bank — cite or label, NEVER invent

Every question you list carries a source:
- `[from JD]` — the responsibility/skill in the posting it comes from.
- `[from interviewer]` — grounded in a specific interviewer's background.
- `[from company]` — a verified company fact (recent launch, public incident, stack).
- `[inferred from JD]` — an educated guess. Allowed, but it MUST wear this label. Never
  present an inferred question as a known one.

"Real performance data outranks inferred risk": if `debrief_md` or `matched_stories` show the
candidate is strong somewhere, do not manufacture a risk there just to be thorough.

## Story matching

For the top likely questions, attach the best story from `matched_stories` (already ranked
by the deterministic F3 matcher — respect its order). If the bank is empty, scaffold a STAR+R
answer from the master CV instead. Never invent a story or a metric.

## Mock practice check

End with a short "verify before you walk in" list: for every CLAIM the prep leans on, point
to where in the master CV it is grounded, so the candidate can't get caught overselling.

## Output — one JSON object

Complete the intent with `atlas intents complete <id> --result-file <f>`, where the file holds
exactly:

```json
{"prep_md": "# Prep profundo — <role> @ <company>\n\n## Audience map\n…full Markdown…"}
```

`prep_md` is the entire pack in Markdown, in the profile's language (or `payload.language`). A
result with an empty `prep_md` is rejected and the intent stays `running` for a corrected retry.
