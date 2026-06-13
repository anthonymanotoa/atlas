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
from pathlib import Path
from typing import Any, Iterable, Optional

from engine.normalize import Job, STAGE_TIMESTAMP_COLS, now_iso
from engine.paths import DB_PATH, ensure_dirs

_SCHEMA = Path(__file__).with_name("schema.sql")


def _loads(v: Optional[str], default: Any) -> Any:
    if not v:
        return default
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return default


class DB:
    def __init__(self, path: Path | str = DB_PATH):
        ensure_dirs()
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.init_schema()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def init_schema(self) -> None:
        self.conn.executescript(_SCHEMA.read_text())
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "DB":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── jobs ─────────────────────────────────────────────────────────────────
    def get_job(self, job_id: str) -> Optional[dict]:
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
                    date_posted, raw_json, sources_json, state, discovered_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'discovered', ?)""",
                (
                    job.id, job.source, job.source_job_id, job.title, job.company,
                    job.location, _b(job.is_remote), job.workplace_type, job.url,
                    job.apply_url, job.description, job.employment_type, job.salary_min,
                    job.salary_max, job.salary_currency, job.salary_interval,
                    job.date_posted, json.dumps(job.raw), json.dumps([job.source]), now,
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
                 is_remote       = COALESCE(is_remote, ?),
                 sources_json    = ?
               WHERE id=?""",
            (
                job.description, job.apply_url, job.url, job.salary_min, job.salary_max,
                job.salary_currency, job.salary_interval, job.employment_type,
                job.date_posted, _b(job.is_remote), json.dumps(sorted(sources)), job.id,
            ),
        )
        self.conn.commit()
        return False

    def list_jobs(self, state: Optional[str] = None, states: Optional[Iterable[str]] = None,
                  limit: Optional[int] = None) -> list[dict]:
        q, params = "SELECT * FROM jobs", []
        clauses = []
        if state:
            clauses.append("state=?"); params.append(state)
        if states:
            placeholders = ",".join("?" * len(list(states)))
            clauses.append(f"state IN ({placeholders})"); params.extend(states)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY COALESCE(fit_score,-1) DESC, discovered_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def set_fit(self, job_id: str, score: float, reasons: list[str],
                knockouts: list[str]) -> None:
        self.conn.execute(
            "UPDATE jobs SET fit_score=?, fit_reasons=?, knockout_flags=? WHERE id=?",
            (score, json.dumps(reasons), json.dumps(knockouts), job_id),
        )
        self.conn.commit()

    def set_state(self, job_id: str, new_state: str, detail: Optional[dict] = None) -> None:
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
        rows = self.conn.execute(
            "SELECT state, COUNT(*) n FROM jobs GROUP BY state").fetchall()
        return {r["state"]: r["n"] for r in rows}

    # ── cv versions ──────────────────────────────────────────────────────────
    def add_cv_version(self, job_id: str, *, language: str, ats_target: Optional[str],
                       path_docx: Optional[str], path_pdf: Optional[str],
                       keyword_coverage: Optional[float], matched: list[str],
                       missing: list[str], parse_ok: Optional[bool]) -> int:
        cur = self.conn.execute(
            """INSERT INTO cv_versions
               (job_id, language, ats_target, path_docx, path_pdf, keyword_coverage,
                matched_keywords, missing_keywords, parse_ok, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (job_id, language, ats_target, path_docx, path_pdf, keyword_coverage,
             json.dumps(matched), json.dumps(missing), _b(parse_ok), now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def cv_versions_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cv_versions WHERE job_id=? ORDER BY created_at DESC", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── messages ─────────────────────────────────────────────────────────────
    def add_message(self, job_id: str, *, channel: str, kind: str, body: str,
                    subject: Optional[str] = None, variant: Optional[str] = None,
                    language: str = "en", contact_id: Optional[int] = None,
                    gmail_draft_id: Optional[str] = None, state: str = "draft") -> int:
        cur = self.conn.execute(
            """INSERT INTO messages
               (job_id, contact_id, channel, kind, variant, language, subject, body,
                gmail_draft_id, state, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, contact_id, channel, kind, variant, language, subject, body,
             gmail_draft_id, state, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def messages_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE job_id=? ORDER BY created_at", (job_id,)).fetchall()
        return [dict(r) for r in rows]

    def has_message(self, job_id: str, kind: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM messages WHERE job_id=? AND kind=? LIMIT 1", (job_id, kind)
        ).fetchone()
        return row is not None

    # ── contacts ─────────────────────────────────────────────────────────────
    def add_contact(self, *, name: str, company: Optional[str], title: Optional[str] = None,
                    linkedin_url: Optional[str] = None, email: Optional[str] = None,
                    degree: Optional[int] = None, role: Optional[str] = None,
                    source: Optional[str] = None, notes: Optional[str] = None) -> int:
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

    def contacts_for_company(self, company_norm: str) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM contacts").fetchall()
        return [dict(r) for r in rows]  # fuzzy matching happens in referrals layer

    # ── applications ─────────────────────────────────────────────────────────
    def add_application(self, job_id: str, *, method: str, apply_url: Optional[str],
                        cv_version_id: Optional[int], status: str = "ready",
                        notes: Optional[str] = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO applications
               (job_id, method, status, apply_url, cv_version_id, notes, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (job_id, method, status, apply_url, cv_version_id, notes, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # ── followups ────────────────────────────────────────────────────────────
    def add_followup(self, job_id: str, *, channel: str, touch_number: int,
                     due_at: str, message_id: Optional[int] = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO followups (job_id, message_id, channel, touch_number, due_at, created_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, message_id, channel, touch_number, due_at, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def due_followups(self, as_of_iso: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM followups WHERE state='pending' AND due_at<=? ORDER BY due_at",
            (as_of_iso,),
        ).fetchall()
        return [dict(r) for r in rows]

    def cancel_followups_for_job(self, job_id: str) -> None:
        """Called when a reply lands — never pester after a response."""
        self.conn.execute(
            "UPDATE followups SET state='cancelled' WHERE job_id=? AND state='pending'", (job_id,))
        self.conn.commit()

    # ── events / health / meta ───────────────────────────────────────────────
    def log_event(self, job_id: Optional[str], type_: str, detail: Optional[dict] = None) -> None:
        self.conn.execute(
            "INSERT INTO events (job_id, type, detail, created_at) VALUES (?,?,?,?)",
            (job_id, type_, json.dumps(detail or {}), now_iso()),
        )
        self.conn.commit()

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def log_source_health(self, source: str, ok: bool, count: int,
                          error: Optional[str], duration_ms: int) -> None:
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

    def meta_get(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def meta_set(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO meta (key, value, updated_at) VALUES (?,?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, now_iso()),
        )
        self.conn.commit()


def _b(v: Optional[bool]) -> Optional[int]:
    return None if v is None else int(bool(v))
