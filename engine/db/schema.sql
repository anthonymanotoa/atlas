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
    raw_json        TEXT,
    sources_json    TEXT,                      -- json array of every source it was seen on

    state           TEXT NOT NULL DEFAULT 'discovered',
    fit_score       REAL,
    fit_reasons     TEXT,                      -- json
    knockout_flags  TEXT,                      -- json array of strings

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
