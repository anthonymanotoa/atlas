"""SQLite access layer for Atlas.

Design notes
------------
* WAL mode + a transaction per write so a crash mid-run leaves the DB consistent.
* Cross-source dedupe via the natural-key PRIMARY KEY; `upsert_job` gap-fills
  missing fields instead of overwriting, so a richer source enriches an existing row.
* Everything is idempotent — a Cowork *catch-up* run that re-executes the pipeline
  must never create duplicate jobs, drafts or follow-ups.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import engine.paths as paths
from engine.normalize import STAGE_TIMESTAMP_COLS, Job, norm_company, now_iso
from engine.paths import ensure_dirs

_SCHEMA = Path(__file__).with_name("schema.sql")


def _loads(v: str | None, default: Any) -> Any:
    if not v:
        return default
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return default


class DB:
    def __init__(self, path: Path | str | None = None, *, check_same_thread: bool = True):
        # Read paths.DB_PATH late so DB() follows the active profile; an explicit path
        # (e.g. in tests) still wins and only its own parent is created — never the
        # active profile's dirs.
        if path is None:
            path = paths.DB_PATH
            ensure_dirs()
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread defaults to True (CLI/short-lived `with DB()` callers are
        # single-threaded). The FastAPI layer opts into False to share one connection
        # across uvicorn's worker threads — see dashboard/backend/main.py (plan 014).
        self.conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.init_schema()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def init_schema(self) -> None:
        self.conn.executescript(_SCHEMA.read_text())
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Idempotent additive migrations.

        `CREATE TABLE IF NOT EXISTS` never adds a column to a table that already
        exists, so a new column on an established `jobs` row needs a guarded
        `ALTER TABLE ... ADD COLUMN`. SQLite has no `ADD COLUMN IF NOT EXISTS`, so
        we check `PRAGMA table_info` first — safe to run on every startup.
        """
        self._ensure_column("jobs", "language", "TEXT")
        self._ensure_column("jobs", "match_score", "INTEGER")
        self._ensure_column("jobs", "match_missing", "TEXT")

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        existing = {r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> DB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── jobs ─────────────────────────────────────────────────────────────────
    def get_job(self, job_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def upsert_job(self, job: Job) -> bool:
        """Insert a new job or gap-fill an existing one. Returns True if newly created."""
        job.finalize()
        existing = self.get_job(job.id)
        now = now_iso()
        if existing is None:
            self.conn.execute(
                """INSERT INTO jobs
                   (id, source, source_job_id, title, company, location, is_remote,
                    workplace_type, url, apply_url, description, employment_type,
                    salary_min, salary_max, salary_currency, salary_interval,
                    date_posted, language, raw_json, sources_json, state, discovered_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'discovered', ?)""",
                (
                    job.id,
                    job.source,
                    job.source_job_id,
                    job.title,
                    job.company,
                    job.location,
                    _b(job.is_remote),
                    job.workplace_type,
                    job.url,
                    job.apply_url,
                    job.description,
                    job.employment_type,
                    job.salary_min,
                    job.salary_max,
                    job.salary_currency,
                    job.salary_interval,
                    job.date_posted,
                    job.language,
                    json.dumps(job.raw),
                    json.dumps([job.source]),
                    now,
                ),
            )
            self.log_event(job.id, "discovered", {"source": job.source})
            self.conn.commit()
            return True

        # Existing → enrich gaps + merge sources, never clobber state/fit.
        sources = set(_loads(existing.get("sources_json"), []))
        sources.add(job.source)
        self.conn.execute(
            """UPDATE jobs SET
                 description     = COALESCE(description, ?),
                 apply_url       = COALESCE(apply_url, ?),
                 url             = COALESCE(url, ?),
                 salary_min      = COALESCE(salary_min, ?),
                 salary_max      = COALESCE(salary_max, ?),
                 salary_currency = COALESCE(salary_currency, ?),
                 salary_interval = COALESCE(salary_interval, ?),
                 employment_type = COALESCE(employment_type, ?),
                 date_posted     = COALESCE(date_posted, ?),
                 language        = COALESCE(language, ?),
                 is_remote       = COALESCE(is_remote, ?),
                 sources_json    = ?
               WHERE id=?""",
            (
                job.description,
                job.apply_url,
                job.url,
                job.salary_min,
                job.salary_max,
                job.salary_currency,
                job.salary_interval,
                job.employment_type,
                job.date_posted,
                job.language,
                _b(job.is_remote),
                json.dumps(sorted(sources)),
                job.id,
            ),
        )
        self.conn.commit()
        return False

    def list_jobs(
        self,
        state: str | None = None,
        states: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        q, params = "SELECT * FROM jobs", []
        clauses = []
        if state:
            clauses.append("state=?")
            params.append(state)
        if states:
            states = list(
                states
            )  # materialize once: a generator would be consumed by the count below
            placeholders = ",".join("?" * len(states))
            clauses.append(f"state IN ({placeholders})")
            params.extend(states)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY COALESCE(fit_score,-1) DESC, discovered_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def set_fit(self, job_id: str, score: float, reasons: list[str], knockouts: list[str]) -> None:
        self.conn.execute(
            "UPDATE jobs SET fit_score=?, fit_reasons=?, knockout_flags=? WHERE id=?",
            (score, json.dumps(reasons), json.dumps(knockouts), job_id),
        )
        self.conn.commit()

    def set_match(self, job_id: str, score: int, missing: list[str]) -> None:
        """Persist the CV↔JD match score (0–100) + importance-ranked missing JD keywords."""
        self.conn.execute(
            "UPDATE jobs SET match_score=?, match_missing=? WHERE id=?",
            (score, json.dumps(missing), job_id),
        )
        self.conn.commit()

    def set_state(self, job_id: str, new_state: str, detail: dict | None = None) -> None:
        """Advance a job's state and stamp the per-stage timestamp + an event."""
        sets = ["state=?"]
        params: list[Any] = [new_state]
        col = STAGE_TIMESTAMP_COLS.get(new_state)
        if col:
            sets.append(f"{col}=COALESCE({col}, ?)")
            params.append(now_iso())
        params.append(job_id)
        self.conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", params)
        self.log_event(job_id, "stage_change", {"to": new_state, **(detail or {})})
        self.conn.commit()

    def counts_by_state(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT state, COUNT(*) n FROM jobs GROUP BY state").fetchall()
        return {r["state"]: r["n"] for r in rows}

    # ── cv versions ──────────────────────────────────────────────────────────
    def add_cv_version(
        self,
        job_id: str,
        *,
        language: str,
        ats_target: str | None,
        path_docx: str | None,
        path_pdf: str | None,
        keyword_coverage: float | None,
        matched: list[str],
        missing: list[str],
        parse_ok: bool | None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO cv_versions
               (job_id, language, ats_target, path_docx, path_pdf, keyword_coverage,
                matched_keywords, missing_keywords, parse_ok, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                language,
                ats_target,
                path_docx,
                path_pdf,
                keyword_coverage,
                json.dumps(matched),
                json.dumps(missing),
                _b(parse_ok),
                now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def cv_versions_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cv_versions WHERE job_id=? ORDER BY created_at DESC", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── messages ─────────────────────────────────────────────────────────────
    def add_message(
        self,
        job_id: str,
        *,
        channel: str,
        kind: str,
        body: str,
        subject: str | None = None,
        variant: str | None = None,
        language: str = "en",
        contact_id: int | None = None,
        gmail_draft_id: str | None = None,
        state: str = "draft",
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO messages
               (job_id, contact_id, channel, kind, variant, language, subject, body,
                gmail_draft_id, state, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                contact_id,
                channel,
                kind,
                variant,
                language,
                subject,
                body,
                gmail_draft_id,
                state,
                now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def messages_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE job_id=? ORDER BY created_at", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def has_message(self, job_id: str, kind: str, variant: str | None = None) -> bool:
        if variant is None:
            row = self.conn.execute(
                "SELECT 1 FROM messages WHERE job_id=? AND kind=? LIMIT 1", (job_id, kind)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT 1 FROM messages WHERE job_id=? AND kind=? AND variant=? LIMIT 1",
                (job_id, kind, variant),
            ).fetchone()
        return row is not None

    # ── contacts ─────────────────────────────────────────────────────────────
    def add_contact(
        self,
        *,
        name: str,
        company: str | None,
        title: str | None = None,
        linkedin_url: str | None = None,
        email: str | None = None,
        degree: int | None = None,
        role: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO contacts
               (name, company, title, linkedin_url, email, degree, role, source, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(name, company) DO UPDATE SET
                 title=COALESCE(contacts.title, excluded.title),
                 linkedin_url=COALESCE(contacts.linkedin_url, excluded.linkedin_url),
                 email=COALESCE(contacts.email, excluded.email),
                 degree=COALESCE(contacts.degree, excluded.degree)""",
            (name, company, title, linkedin_url, email, degree, role, source, notes, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def all_contacts(self) -> list[dict]:
        """Every contact. Callers that match many jobs load this ONCE and reuse it,
        instead of re-scanning the table per job (fuzzy matching happens in the referrals layer)."""
        rows = self.conn.execute("SELECT * FROM contacts").fetchall()
        return [dict(r) for r in rows]

    def contacts_for_company(self, company_norm: str) -> list[dict]:
        return self.all_contacts()  # fuzzy matching happens in referrals layer

    # ── applications ─────────────────────────────────────────────────────────
    def add_application(
        self,
        job_id: str,
        *,
        method: str,
        apply_url: str | None,
        cv_version_id: int | None,
        status: str = "ready",
        notes: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO applications
               (job_id, method, status, apply_url, cv_version_id, notes, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (job_id, method, status, apply_url, cv_version_id, notes, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # ── followups ────────────────────────────────────────────────────────────
    def add_followup(
        self,
        job_id: str,
        *,
        channel: str,
        touch_number: int,
        due_at: str,
        message_id: int | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO followups (job_id, message_id, channel, touch_number, due_at, created_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, message_id, channel, touch_number, due_at, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def followups_for_job(self, job_id: str, channel: str | None = None) -> list[dict]:
        """ALL follow-up rows for a job (any state) — used by schedule() for idempotency."""
        if channel is None:
            rows = self.conn.execute("SELECT * FROM followups WHERE job_id=?", (job_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM followups WHERE job_id=? AND channel=?", (job_id, channel)
            ).fetchall()
        return [dict(r) for r in rows]

    def due_followups(self, as_of_iso: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM followups WHERE state='pending' AND due_at<=? ORDER BY due_at",
            (as_of_iso,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_followup(self, followup_id: int, state: str = "done") -> None:
        self.conn.execute("UPDATE followups SET state=? WHERE id=?", (state, followup_id))
        self.conn.commit()

    def cancel_followups_for_job(self, job_id: str) -> None:
        """Called when a reply lands — never pester after a response."""
        self.conn.execute(
            "UPDATE followups SET state='cancelled' WHERE job_id=? AND state='pending'", (job_id,)
        )
        self.conn.commit()

    # ── events / health / meta ───────────────────────────────────────────────
    def log_event(self, job_id: str | None, type_: str, detail: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO events (job_id, type, detail, created_at) VALUES (?,?,?,?)",
            (job_id, type_, json.dumps(detail or {}), now_iso()),
        )
        self.conn.commit()

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def log_source_health(
        self, source: str, ok: bool, count: int, error: str | None, duration_ms: int
    ) -> None:
        self.conn.execute(
            """INSERT INTO source_health (source, run_at, ok, count, error, duration_ms)
               VALUES (?,?,?,?,?,?)""",
            (source, now_iso(), _b(ok), count, error, duration_ms),
        )
        self.conn.commit()

    def latest_source_health(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT sh.* FROM source_health sh
               JOIN (SELECT source, MAX(run_at) mx FROM source_health GROUP BY source) m
                 ON sh.source=m.source AND sh.run_at=m.mx
               ORDER BY sh.source"""
        ).fetchall()
        return [dict(r) for r in rows]

    def meta_get(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def meta_set(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO meta (key, value, updated_at) VALUES (?,?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, now_iso()),
        )
        self.conn.commit()

    # ── social mentions (P2-C) ─────────────────────────────────────────────────
    def add_social_mention(
        self,
        job_id: str,
        *,
        platform: str,
        source_url: str | None = None,
        recruiter_name: str | None = None,
        recruiter_linkedin: str | None = None,
        recruiter_email: str | None = None,
        post_title: str | None = None,
        post_excerpt: str | None = None,
        context_type: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO social_mentions
               (job_id, platform, source_url, recruiter_name, recruiter_linkedin,
                recruiter_email, post_title, post_excerpt, context_type, found_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                platform,
                source_url,
                recruiter_name,
                recruiter_linkedin,
                recruiter_email,
                post_title,
                post_excerpt,
                context_type,
                now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def social_mentions_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM social_mentions WHERE job_id=? ORDER BY found_at DESC", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── learning loop (P2-D) ───────────────────────────────────────────────────
    def record_outcome(
        self,
        job_id: str | None,
        company: str,
        *,
        final_state: str,
        response_days: int | None = None,
        interview_count: int = 0,
        offer_made: bool = False,
        recruiter_source: str | None = None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Record a HUMAN-confirmed application outcome (company stored normalized)."""
        cur = self.conn.execute(
            """INSERT INTO application_outcomes
               (job_id, company, final_state, response_days, interview_count, offer_made,
                recruiter_source, reason, notes, captured_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                norm_company(company),
                final_state,
                response_days,
                interview_count,
                _b(offer_made),
                recruiter_source,
                reason,
                notes,
                now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def outcomes_for_company(self, company: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM application_outcomes WHERE company=? ORDER BY captured_at",
            (norm_company(company),),
        ).fetchall()
        return [dict(r) for r in rows]

    def companies_with_outcomes(self) -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT company FROM application_outcomes").fetchall()
        return [r["company"] for r in rows]

    def upsert_learning(
        self, company: str, pattern_type: str, observation: str, confidence: float, evidence: int
    ) -> None:
        self.conn.execute(
            """INSERT INTO learnings
                 (company, pattern_type, observation, confidence, evidence_count, last_updated)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(company, pattern_type) DO UPDATE SET
                 observation=excluded.observation,
                 confidence=excluded.confidence,
                 evidence_count=excluded.evidence_count,
                 last_updated=excluded.last_updated""",
            (norm_company(company), pattern_type, observation, confidence, evidence, now_iso()),
        )
        self.conn.commit()

    def learnings_for_company(self, company: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM learnings WHERE company=? ORDER BY confidence DESC",
            (norm_company(company),),
        ).fetchall()
        return [dict(r) for r in rows]

    def all_learnings(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM learnings ORDER BY company, confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── interviews (P3-E) ──────────────────────────────────────────────────────
    def add_interview(
        self,
        job_id: str,
        *,
        scheduled_at: str | None = None,
        round: str | None = None,
        mode: str | None = None,
        notes: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO interviews (job_id, scheduled_at, round, mode, notes, created_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, scheduled_at, round, mode, notes, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_interview(self, interview_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM interviews WHERE id=?", (interview_id,)).fetchone()
        return dict(row) if row else None

    def interviews_for_job(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM interviews WHERE job_id=? ORDER BY scheduled_at", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_interviews(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM interviews ORDER BY scheduled_at").fetchall()
        return [dict(r) for r in rows]

    def set_interview_prep_path(self, interview_id: int, path: str) -> None:
        self.conn.execute("UPDATE interviews SET prep_path=? WHERE id=?", (path, interview_id))
        self.conn.commit()

    def add_interviewer(
        self,
        interview_id: int,
        *,
        name: str,
        title: str | None = None,
        company: str | None = None,
        linkedin_url: str | None = None,
        research_notes: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO interviewers
               (interview_id, name, title, company, linkedin_url, research_notes, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (interview_id, name, title, company, linkedin_url, research_notes, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def interviewers_for(self, interview_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM interviewers WHERE interview_id=? ORDER BY id", (interview_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── portfolio + peers (P3-F) ───────────────────────────────────────────────
    def add_portfolio(
        self,
        *,
        version: str,
        path_html: str,
        metadata_json: str = "{}",
        output_format: str = "html",
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO portfolios (version, output_format, path_html, metadata_json, generated_at)
               VALUES (?,?,?,?,?)""",
            (version, output_format, path_html, metadata_json, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_portfolios(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM portfolios ORDER BY generated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def latest_portfolio(self) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM portfolios ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def add_peer_portfolio(
        self,
        *,
        peer_name: str,
        role_match: str | None = None,
        peer_profile_url: str | None = None,
        peer_portfolio_url: str | None = None,
        key_strengths: list[str] | None = None,
        how_to_emulate: list[str] | None = None,
        source_url: str | None = None,
        notes: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO peer_portfolios
               (role_match, peer_name, peer_profile_url, peer_portfolio_url,
                key_strengths_json, how_to_emulate_json, source_url, notes, reviewed_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                role_match,
                peer_name,
                peer_profile_url,
                peer_portfolio_url,
                json.dumps(key_strengths or []),
                json.dumps(how_to_emulate or []),
                source_url,
                notes,
                now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_peer_portfolios(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM peer_portfolios ORDER BY reviewed_at DESC"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["key_strengths"] = _loads(d.get("key_strengths_json"), [])
            d["how_to_emulate"] = _loads(d.get("how_to_emulate_json"), [])
            out.append(d)
        return out

    def record_learning_feedback(
        self,
        learning_id: int,
        *,
        feedback_type: str,
        job_id: str | None = None,
        reasoning: str = "",
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO learning_feedback (learning_id, job_id, feedback_type, reasoning, created_at)
               VALUES (?,?,?,?,?)""",
            (learning_id, job_id, feedback_type, reasoning, now_iso()),
        )
        # A 'disagree' halves the pattern's confidence so the scorer trusts it less.
        if feedback_type == "disagree":
            self.conn.execute(
                "UPDATE learnings SET confidence = confidence * 0.5 WHERE id=?", (learning_id,)
            )
        self.conn.commit()
        return int(cur.lastrowid)


def _b(v: bool | None) -> int | None:
    return None if v is None else int(bool(v))
