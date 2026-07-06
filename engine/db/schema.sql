-- Atlas SQLite schema. Idempotent: safe to run on every startup.
-- WAL + foreign keys are set as PRAGMAs in models.py (per-connection).

CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,          -- stable natural key (normalize.compute_job_id)
    source          TEXT NOT NULL,             -- first source that discovered it
    source_job_id   TEXT,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    is_remote       INTEGER,                   -- 1 / 0 / NULL(unknown)
    workplace_type  TEXT DEFAULT 'unknown',    -- remote | hybrid | onsite | unknown
    url             TEXT,
    apply_url       TEXT,
    description     TEXT,
    employment_type TEXT,
    salary_min      REAL,
    salary_max      REAL,
    salary_currency TEXT,
    salary_interval TEXT,
    date_posted     TEXT,
    language        TEXT,                      -- detected posting language (en|es|de|fr|pt)
    geo_restriction TEXT,                      -- raw geo-restriction text detected (F2, UI)
    geo_scope       TEXT,                      -- normalized scope: iso2/region | worldwide | unknown | ''
    repost_count    INTEGER DEFAULT 0,         -- ghost-job signal: same company+core-title reposts in 90d
    liveness_checked_at TEXT,                  -- last liveness HTTP check (F2 hygiene)
    raw_json        TEXT,
    sources_json    TEXT,                      -- json array of every source it was seen on

    state           TEXT NOT NULL DEFAULT 'discovered',
    fit_score       REAL,
    fit_reasons     TEXT,                      -- json
    knockout_flags  TEXT,                      -- json array of strings
    match_score     INTEGER,                   -- CV↔JD keyword match 0–100 (distinct from fit_score)
    match_missing   TEXT,                      -- json array of JD keywords the CV doesn't evidence
    knockout_warnings TEXT,                    -- json array of knock-out pre-scan warnings (F3, visa/years/degree/language/clearance)
    score_breakdown TEXT,                      -- json: machine summary — per-factor score deltas (F3)
    legitimacy_tier TEXT,                      -- high | medium | low (F4 Block G; NULL = unrated)
    legitimacy_notes TEXT,                     -- señales observadas, nunca acusaciones

    discovered_at   TEXT NOT NULL,
    scored_at       TEXT,
    shortlisted_at  TEXT,
    tailored_at     TEXT,
    drafted_at      TEXT,
    ready_at        TEXT,
    applied_at      TEXT,
    responded_at    TEXT,
    interview_at    TEXT,
    offer_at        TEXT,
    rejected_at     TEXT,
    closed_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);

CREATE TABLE IF NOT EXISTS cv_versions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id            TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    language          TEXT DEFAULT 'en',
    ats_target        TEXT,
    path_docx         TEXT,
    path_pdf          TEXT,
    keyword_coverage  REAL,                    -- 0..1
    matched_keywords  TEXT,                    -- json
    missing_keywords  TEXT,                    -- json
    parse_ok          INTEGER,                 -- 1/0 from parse_check
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cv_job ON cv_versions(job_id);

CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    company      TEXT,
    title        TEXT,
    linkedin_url TEXT,
    email        TEXT,
    degree       INTEGER,                      -- 1 = 1st-degree connection, 2 = 2nd
    role         TEXT,                         -- recruiter | hiring_manager | connection | referral
    source       TEXT,                         -- connections_csv | manual | chrome
    notes        TEXT,
    created_at   TEXT NOT NULL,
    UNIQUE(name, company)
);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);

CREATE TABLE IF NOT EXISTS messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    contact_id     INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    channel        TEXT,                       -- email | linkedin_note | linkedin_inmail | referral
    kind           TEXT,                       -- cover_letter | recruiter | hiring_manager | referral_ask | follow_up | breakup
    variant        TEXT,
    language       TEXT DEFAULT 'en',
    subject        TEXT,
    body           TEXT,
    gmail_draft_id TEXT,
    state          TEXT DEFAULT 'draft',       -- draft | ready | sent (sent set only by the human)
    created_at     TEXT NOT NULL,
    sent_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_job ON messages(job_id);

CREATE TABLE IF NOT EXISTS applications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    method         TEXT,                       -- ats_form | linkedin | email | referral
    status         TEXT DEFAULT 'ready',       -- ready | applied | rejected | ...
    apply_url      TEXT,
    cv_version_id  INTEGER REFERENCES cv_versions(id) ON DELETE SET NULL,
    notes          TEXT,
    created_at     TEXT NOT NULL,
    applied_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_apps_job ON applications(job_id);

CREATE TABLE IF NOT EXISTS followups (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    message_id    INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    channel       TEXT,
    kind          TEXT,                        -- F3 cadencia v2: pipeline state that seeded this touch (e.g. 'applied'); NULL = legacy per-message touch
    touch_number  INTEGER,                     -- 1..4 then breakup
    due_at        TEXT,
    state         TEXT DEFAULT 'pending',      -- pending | done | cancelled
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_followups_due ON followups(state, due_at);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT,
    type        TEXT NOT NULL,                 -- discovered | scored | stage_change | source_run | error | note | ...
    detail      TEXT,                          -- json
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

CREATE TABLE IF NOT EXISTS source_health (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    run_at      TEXT NOT NULL,
    ok          INTEGER NOT NULL,
    count       INTEGER DEFAULT 0,
    error       TEXT,
    duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_health_source ON source_health(source, run_at);

-- Key/value store for watermarks + heartbeat (last_run, last_success_ts, ...).
CREATE TABLE IF NOT EXISTS meta (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT
);

-- Self-improving memory (P2-D). Outcomes are HUMAN-confirmed (form/CLI), never fabricated
-- by the brain. auto_learn() rolls them into per-company `learnings` the scorer/outreach read.
CREATE TABLE IF NOT EXISTS application_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    company         TEXT NOT NULL,             -- normalized (normalize.norm_company)
    final_state     TEXT NOT NULL,             -- rejected | responded | interviewed | offer | ghosted
    response_days   INTEGER,
    interview_count INTEGER DEFAULT 0,
    offer_made      INTEGER DEFAULT 0,         -- 1/0
    recruiter_source TEXT,                      -- referral | recruiter | cold | inbound | unknown
    reason          TEXT,
    notes           TEXT,
    captured_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcomes_company ON application_outcomes(company);

CREATE TABLE IF NOT EXISTS learnings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company        TEXT NOT NULL,              -- normalized
    pattern_type   TEXT NOT NULL,              -- process_speed | referral_conversion | rejection_rate | offer_rate | process
    observation    TEXT NOT NULL,
    confidence     REAL DEFAULT 0,             -- 0..1, grows with evidence
    evidence_count INTEGER DEFAULT 0,
    last_updated   TEXT NOT NULL,
    UNIQUE(company, pattern_type)
);
CREATE INDEX IF NOT EXISTS idx_learnings_company ON learnings(company);

CREATE TABLE IF NOT EXISTS learning_feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id   INTEGER REFERENCES learnings(id) ON DELETE CASCADE,
    job_id        TEXT,
    feedback_type TEXT,                        -- agree | disagree
    reasoning     TEXT,
    created_at    TEXT NOT NULL
);

-- Social signal (P2-C): recruiter/posts found about a vacancy on LinkedIn/X via a
-- SUPERVISED Claude-in-Chrome session. Captured after the human confirms — never auto-contacted.
CREATE TABLE IF NOT EXISTS social_mentions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id            TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    platform          TEXT,                    -- linkedin | x | other
    source_url        TEXT,
    recruiter_name    TEXT,
    recruiter_linkedin TEXT,
    recruiter_email   TEXT,
    post_title        TEXT,
    post_excerpt      TEXT,
    context_type      TEXT,                    -- hiring_post | recruiter_profile | mention | other
    found_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_social_job ON social_mentions(job_id);

-- Interview prep (P3-E): interviews are entered MANUALLY in the dashboard. Interviewer
-- research is SUPERVISED Claude-in-Chrome (the human confirms LinkedIn URLs).
CREATE TABLE IF NOT EXISTS interviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    scheduled_at TEXT,
    round        TEXT,                          -- phone | technical | system_design | hiring_manager | final | other
    mode         TEXT,                          -- video | onsite | phone
    status       TEXT DEFAULT 'scheduled',      -- scheduled | done | cancelled
    notes        TEXT,
    prep_path    TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interviews_job ON interviews(job_id);

CREATE TABLE IF NOT EXISTS interviewers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id   INTEGER REFERENCES interviews(id) ON DELETE CASCADE,
    name           TEXT,
    title          TEXT,
    company        TEXT,
    linkedin_url   TEXT,
    research_notes TEXT,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interviewers_iv ON interviewers(interview_id);

-- Portfolio (P3-F): generated artifacts (local-only, never auto-published) + peer references
-- studied via SUPERVISED Claude-in-Chrome (links + notes only — no scraping/hoarding).
CREATE TABLE IF NOT EXISTS portfolios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    version       TEXT,
    output_format TEXT DEFAULT 'html',
    path_html     TEXT,
    metadata_json TEXT,
    generated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS peer_portfolios (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    role_match         TEXT,
    peer_name          TEXT,
    peer_profile_url   TEXT,
    peer_portfolio_url TEXT,
    key_strengths_json TEXT,
    how_to_emulate_json TEXT,
    source_url         TEXT,
    notes              TEXT,
    reviewed_at        TEXT
);

-- Posting archive (F2 hygiene): an immutable snapshot of the posting captured when the
-- user marks Applied — evidence for prep/negotiation even after the posting dies.
CREATE TABLE IF NOT EXISTS posting_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    captured_at TEXT NOT NULL,
    payload     TEXT NOT NULL                      -- json: title/company/location/description/salary/url/date_posted
);
CREATE INDEX IF NOT EXISTS idx_snapshots_job ON posting_snapshots(job_id);

-- Story bank STAR+R (F3 §6.3). Vive en la DB del perfil activo (una por perfil).
-- El matcher determinista (engine/stories.py) rankea por overlap de tokens/skills.
CREATE TABLE IF NOT EXISTS stories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    situation   TEXT DEFAULT '',
    task        TEXT DEFAULT '',
    action      TEXT DEFAULT '',
    result      TEXT DEFAULT '',
    reflection  TEXT DEFAULT '',
    skills      TEXT DEFAULT '[]',              -- json array de tags de skill
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Intent queue (F4): guided handoff web → brain. The web enqueues; the brain (Claude Code)
-- drains as step 0 of `corre atlas` and completes each intent with a validated result JSON.
CREATE TABLE IF NOT EXISTS intents (
    id           TEXT PRIMARY KEY,              -- in_<hex12>
    type         TEXT NOT NULL,                 -- cv_review | legitimacy_batch | upskill_report
                                                --  | interview_prep_deep | profile_expand | cover_letter
    job_id       TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    payload      TEXT NOT NULL DEFAULT '{}',    -- json, validated per-type at the API
    status       TEXT NOT NULL DEFAULT 'pending', -- pending | running | done | error
    result_ref   TEXT,                          -- e.g. cv_review:3, jobs:12, message:7
    error        TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_intents_status ON intents(status, created_at);
CREATE INDEX IF NOT EXISTS idx_intents_job ON intents(job_id);

-- CV reviews (F4 §7.2): salida del reviewer LLM (hiring-manager proxy). Los edits se
-- aplican mecánicamente desde la web (apply-edit) y los flags se resuelven keep/soften/drop.
CREATE TABLE IF NOT EXISTS cv_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id     TEXT REFERENCES intents(id) ON DELETE SET NULL,
    job_id        TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    cv_version_id INTEGER REFERENCES cv_versions(id) ON DELETE SET NULL,
    edits         TEXT NOT NULL DEFAULT '[]',   -- json [{file, old_string, new_string, reason, applied?, applied_ref?}]
    critique      TEXT NOT NULL DEFAULT '{}',   -- json {missed_keywords, company_angles, reframing, tone_register}
    flags         TEXT NOT NULL DEFAULT '[]',   -- json [{file, bullet, classification, reason, softened?, resolution?}]
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cv_reviews_job ON cv_reviews(job_id);
