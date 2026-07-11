"""Cola de intents (F4): enqueue/list/transiciones. Los writers por tipo se testean
en las tareas de cada tipo; aquí solo el ciclo de vida genérico."""

from __future__ import annotations

from pathlib import Path

import pytest

import engine.paths as paths
from engine import intents
from engine.db.models import DB


@pytest.fixture
def db(tmp_path):
    with DB(tmp_path / "t.db") as d:
        yield d


def test_enqueue_and_list_pending(db):
    iid = intents.enqueue(db, "cv_review", {"language": "en"}, job_id=None)
    assert iid.startswith("in_")
    rows = intents.list_intents(db, status="pending")
    assert [r["id"] for r in rows] == [iid]
    assert rows[0]["payload"] == {"language": "en"}
    assert rows[0]["status"] == "pending" and rows[0]["created_at"]


def test_enqueue_unknown_type_raises(db):
    with pytest.raises(ValueError):
        intents.enqueue(db, "world_peace", {})


def test_lifecycle_pending_running_done(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    assert intents.get_intent(db, iid)["status"] == "running"
    intents.mark_done(db, iid, "upskill_report:1")
    row = intents.get_intent(db, iid)
    assert row["status"] == "done"
    assert row["result_ref"] == "upskill_report:1"
    assert row["completed_at"]


def test_mark_running_only_from_pending_or_error(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_done(db, iid, "x:1")
    with pytest.raises(ValueError):
        intents.mark_running(db, iid)


def test_error_intent_can_be_retried(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_error(db, iid, "boom")
    row = intents.get_intent(db, iid)
    assert row["status"] == "error" and row["error"] == "boom" and row["completed_at"]
    intents.mark_running(db, iid)  # reintento permitido
    assert intents.get_intent(db, iid)["status"] == "running"


def test_mark_done_requires_running(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):
        intents.mark_done(db, iid, "x:1")


def test_list_pending_only_returns_pending(db):
    pend = intents.enqueue(db, "cv_review", {})
    done = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, done)
    intents.mark_done(db, done, "x:1")
    running = intents.enqueue(db, "profile_expand", {})
    intents.mark_running(db, running)
    assert {r["id"] for r in intents.list_pending(db)} == {pend}


def test_all_six_intent_types_enqueue(db):
    assert set(intents.INTENT_TYPES) == {
        "cv_review",
        "legitimacy_batch",
        "upskill_report",
        "interview_prep_deep",
        "profile_expand",
        "cover_letter",
    }
    for t in intents.INTENT_TYPES:
        iid = intents.enqueue(db, t)
        assert intents.get_intent(db, iid)["type"] == t


def test_apply_result_rejects_unknown_writer_without_touching_db(db):
    """A known type with no registered writer (skeleton) leaves the intent `running`
    and raises — the brain can re-run once the writer lands."""
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"ok": True})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_result_requires_running_and_dict(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):  # still pending
        intents.apply_result(db, iid, {"ok": True})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):  # non-dict result
        intents.apply_result(db, iid, ["not", "a", "dict"])


def test_apply_result_routes_to_registered_writer(db, monkeypatch):
    """apply_result validates the type, calls its writer, and marks done with the ref."""
    seen: dict = {}

    def _fake_writer(db_, intent, result):
        seen["intent_type"] = intent["type"]
        seen["result"] = result
        return "upskill_report:42"

    monkeypatch.setitem(intents._RESULT_WRITERS, "upskill_report", _fake_writer)
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    ref = intents.apply_result(db, iid, {"score": 7})
    assert ref == "upskill_report:42"
    assert seen == {"intent_type": "upskill_report", "result": {"score": 7}}
    row = intents.get_intent(db, iid)
    assert row["status"] == "done" and row["result_ref"] == "upskill_report:42"


def test_context_for_includes_prompt_file_and_job(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(
            source="greenhouse",
            source_job_id="9",
            title="ML Engineer",
            company="Beta",
            url="https://x/9",
            description="d" * 9000,
        )
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {"language": "en"}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["prompt_file"] == "brain/prompts/cover_letter.md"
    assert ctx["job"]["id"] == jid
    assert len(ctx["job"]["description"]) == 6000  # recortado


def test_apply_result_requires_running_and_known_writer(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):  # aún pending
        intents.apply_result(db, iid, {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):  # writer no registrado todavía (llega en Task 10)
        intents.apply_result(db, iid, {})
    assert intents.get_intent(db, iid)["status"] == "running"  # no se corrompe el estado


# ── cover_letter writer (Task 8) — valida + persiste la carta que redactó el brain ──
def test_cover_letter_writer_creates_draft_message(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="2", title="Analyst", company="Zeta", url="https://x/2")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {"language": "en"}, job_id=jid)
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {"subject": "Application — Analyst", "body": "Dear team, ...", "language": "en"},
    )
    assert ref.startswith("message:")
    msgs = [m for m in db.messages_for(jid) if m["kind"] == "cover_letter"]
    assert msgs and msgs[-1]["variant"] == "brain" and msgs[-1]["state"] == "draft"
    assert msgs[-1]["channel"] == "email" and msgs[-1]["language"] == "en"
    assert msgs[-1]["subject"] == "Application — Analyst"
    assert intents.get_intent(db, iid)["status"] == "done"


def test_cover_letter_writer_rejects_empty_body(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="3", title="Analyst", company="Eta", url="https://x/3")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"subject": "s", "body": ""})
    # malformed result → no message written and the intent stays running for a retry.
    assert [m for m in db.messages_for(jid) if m["kind"] == "cover_letter"] == []
    assert intents.get_intent(db, iid)["status"] == "running"


def test_cover_letter_writer_rejects_empty_subject(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="4", title="Analyst", company="Theta", url="https://x/4")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"subject": "   ", "body": "a real body"})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_cover_letter_writer_rejects_bad_language(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="5", title="Analyst", company="Iota", url="https://x/5")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"subject": "s", "body": "b", "language": "fr"})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_cover_letter_writer_defaults_language_to_en(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="6", title="Analyst", company="Kappa", url="https://x/6")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "cover_letter", {}, job_id=jid)
    intents.mark_running(db, iid)
    intents.apply_result(db, iid, {"subject": "s", "body": "b"})
    msgs = [m for m in db.messages_for(jid) if m["kind"] == "cover_letter"]
    assert msgs and msgs[-1]["language"] == "en"


def test_cover_letter_context_exposes_cv_learnings_and_messages(db):
    import engine.paths as paths
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="7", title="Analyst", company="Lambda", url="https://x/7")
    )
    jid = db.list_jobs()[0]["id"]
    db.add_message(jid, channel="email", kind="cold_email", body="hi", subject="s")
    iid = intents.enqueue(db, "cover_letter", {}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["master_cv_path"] == str(paths.MASTER_CV_PATH)
    assert isinstance(ctx["learnings"], list)
    assert any(m["kind"] == "cold_email" for m in ctx["existing_messages"])


# ── legitimacy_batch (Task 9, Block G) ─────────────────────────────────────────
# The writer persists ONE tier+notes per job_id in the batch. It is orthogonal to fit:
# it never touches fit_score/match_score. It rejects any entry outside the payload's
# job_ids (the LLM can only rate the shortlist it was handed) and any bad tier / empty
# notes — a malformed batch raises and leaves the intent `running` (not done).
def test_legitimacy_writer_updates_jobs(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="ashby", source_job_id="4", title="DS", company="Ghosty", url="https://x/4")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": [jid]})
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {
            "jobs": [
                {
                    "job_id": jid,
                    "tier": "low",
                    "notes": "Posting de 92 días sin repost; JD genérico.",
                }
            ]
        },
    )
    assert ref == "jobs:1"
    job = db.get_job(jid)
    assert job["legitimacy_tier"] == "low" and "92 días" in job["legitimacy_notes"]
    # Orthogonal to fit: rating legitimacy never fabricates or touches the match/fit scores.
    assert job["fit_score"] is None and job["match_score"] is None
    assert intents.get_intent(db, iid)["status"] == "done"


def test_legitimacy_writer_persists_each_job_in_the_batch(db):
    from engine.normalize import Job

    for n in ("10", "11", "12"):
        db.upsert_job(
            Job(source="ashby", source_job_id=n, title="DS", company=f"Co{n}", url=f"https://x/{n}")
        )
    ids = [j["id"] for j in db.list_jobs()]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": ids})
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {
            "jobs": [
                {"job_id": ids[0], "tier": "high", "notes": "Reciente; JD específico."},
                {"job_id": ids[1], "tier": "medium", "notes": "Señales mixtas; falta info."},
                {"job_id": ids[2], "tier": "low", "notes": "Dominio no coincide con la empresa."},
            ]
        },
    )
    assert ref == "jobs:3"
    assert db.get_job(ids[0])["legitimacy_tier"] == "high"
    assert db.get_job(ids[1])["legitimacy_tier"] == "medium"
    assert db.get_job(ids[2])["legitimacy_tier"] == "low"


def test_legitimacy_writer_rejects_bad_tier_and_foreign_job(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="ashby", source_job_id="5", title="DS", company="Ok", url="https://x/5")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": [jid]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"jobs": [{"job_id": jid, "tier": "meh", "notes": "x"}]})
    with pytest.raises(ValueError):  # job fuera del payload — el LLM no puede tocar otros
        intents.apply_result(db, iid, {"jobs": [{"job_id": "otro", "tier": "low", "notes": "x"}]})
    # A rejected batch leaves the intent `running` (not done) and never wrote a tier.
    assert intents.get_intent(db, iid)["status"] == "running"
    assert db.get_job(jid)["legitimacy_tier"] is None


def test_legitimacy_writer_rejects_empty_batch_and_empty_notes(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="ashby", source_job_id="6", title="DS", company="Ok", url="https://x/6")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": [jid]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):  # empty jobs list
        intents.apply_result(db, iid, {"jobs": []})
    with pytest.raises(ValueError):  # notes are the observations — never empty
        intents.apply_result(db, iid, {"jobs": [{"job_id": jid, "tier": "high", "notes": "  "}]})
    assert db.get_job(jid)["legitimacy_tier"] is None


def test_legitimacy_context_exposes_job_briefs_and_today(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="ashby", source_job_id="8", title="DS", company="Ctx", url="https://x/8")
    )
    jid = db.list_jobs()[0]["id"]
    iid = intents.enqueue(db, "legitimacy_batch", {"job_ids": [jid]})
    ctx = intents.context_for(db, iid)
    assert [b["id"] for b in ctx["jobs"]] == [jid]
    assert len(ctx["today"]) == 10 and ctx["today"][4] == "-"  # YYYY-MM-DD


# ── interview_prep_deep (Task 11) ──────────────────────────────────────────────
# The writer validates + persists the brain's audience-mapped deep prep pack (never runs an
# LLM — $0). The context builder reuses the deterministic prep doc as the floor and, if the
# F3 story bank landed, the matched STAR+R stories. Malformed → raises, intent stays running.
def test_interview_prep_deep_writer_persists_and_marks_done(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.normalize import Job

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    db.upsert_job(
        Job(
            source="lever",
            source_job_id="7",
            title="Staff DS",
            company="Nu",
            url="https://x/7",
            description="Python, SQL, causal inference.",
        )
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="hiring_manager")
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db, iid, {"prep_md": "# Prep profundo\n\n## Audience map\n- Hiring manager…"}
    )
    assert ref == f"interview:{ivid}"
    assert "Audience map" in db.get_interview(ivid)["deep_prep_md"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_interview_prep_deep_context_includes_deterministic_prep(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.normalize import Job

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    db.upsert_job(
        Job(
            source="lever",
            source_job_id="8",
            title="DS",
            company="Ka",
            url="https://x/8",
            description="Python and SQL.",
        )
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="technical")
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["interview"]["id"] == ivid
    assert isinstance(ctx["deterministic_prep"], str) and ctx["deterministic_prep"]
    assert isinstance(ctx["matched_stories"], list)  # [] si F3 no dejó historias


def test_interview_prep_deep_context_matches_story_bank(db, tmp_path, monkeypatch):
    """When the F3 story bank has a matching story, the context surfaces it (deterministic)."""
    import engine.paths as paths
    from engine.normalize import Job

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    db.upsert_job(
        Job(
            source="lever",
            source_job_id="80",
            title="Data Scientist",
            company="Sti",
            url="https://x/80",
            description="Deep experience with causal inference and A/B testing.",
        )
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="technical")
    db.add_story(
        title="Rescued a broken A/B test",
        situation="A/B testing pipeline was leaking exposures.",
        action="Rebuilt the causal inference layer end to end.",
        result="Cut false positives 40%.",
        skills=["A/B testing", "causal inference"],
    )
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["matched_stories"], "a matching story should be surfaced"
    top = ctx["matched_stories"][0]
    assert "A/B" in top["story"] and isinstance(top["score"], (int, float))


def test_interview_prep_deep_writer_rejects_empty(db):
    from engine.normalize import Job

    db.upsert_job(
        Job(source="lever", source_job_id="9", title="DS", company="Za", url="https://x/9")
    )
    jid = db.list_jobs()[0]["id"]
    ivid = db.add_interview(jid, round="phone")
    iid = intents.enqueue(db, "interview_prep_deep", {"interview_id": ivid}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"prep_md": ""})
    assert intents.get_intent(db, iid)["status"] == "running"
    assert db.get_interview(ivid)["deep_prep_md"] is None


# ── CLI layer (Task 3) — el brain drena la cola vía estos comandos ─────────────
@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    """Point the CLI's `_db()` and outbox at a throwaway location, and hand back a
    live DB on the SAME file so a test can seed rows the CLI will then see."""
    import engine.paths as paths

    db_path = tmp_path / "atlas.db"
    monkeypatch.setattr(paths, "DB_PATH", db_path)
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    with DB(db_path) as d:
        yield d


def _run(args):
    from typer.testing import CliRunner

    from engine.cli import app

    return CliRunner().invoke(app, args)


def test_cli_intents_list_shows_pending(cli_db):
    intents.enqueue(cli_db, "cv_review", {"language": "en"})
    res = _run(["intents", "list"])
    assert res.exit_code == 0, res.output
    assert "cv_review" in res.output


def test_cli_intents_list_json_empty(cli_db):
    res = _run(["intents", "list", "--json"])
    assert res.exit_code == 0, res.output
    import json

    assert json.loads(res.output) == []


def test_cli_intents_start_marks_running_and_emits_prompt(cli_db):
    iid = intents.enqueue(cli_db, "cover_letter", {})
    res = _run(["intents", "start", iid])
    assert res.exit_code == 0, res.output
    assert "running" in res.output
    assert "brain/prompts/cover_letter.md" in res.output
    assert intents.get_intent(cli_db, iid)["status"] == "running"


def test_cli_intents_start_unknown_id_exits_nonzero(cli_db):
    res = _run(["intents", "start", "in_nope"])
    assert res.exit_code == 2


def test_cli_intents_context_emits_json(cli_db):
    from engine.normalize import Job

    cli_db.upsert_job(
        Job(
            source="greenhouse",
            source_job_id="3",
            title="Data Scientist",
            company="Acme",
            url="https://x/3",
            description="Python + SQL.",
        )
    )
    jid = cli_db.list_jobs()[0]["id"]
    iid = intents.enqueue(cli_db, "cv_review", {}, job_id=jid)
    res = _run(["intents", "context", iid])
    assert res.exit_code == 0, res.output
    import json

    ctx = json.loads(res.output)
    assert ctx["prompt_file"] == "brain/prompts/cv_review.md"
    assert ctx["job"]["id"] == jid


def test_cli_intents_complete_valid_result_applies_and_marks_done(cli_db, monkeypatch):
    """A VALID result → apply_result writes the ref and the intent becomes done."""
    monkeypatch.setitem(
        intents._RESULT_WRITERS, "upskill_report", lambda db, i, r: "upskill_report:7"
    )
    iid = intents.enqueue(cli_db, "upskill_report", {})
    intents.mark_running(cli_db, iid)
    p = _tmp_json({"score": 9})
    res = _run(["intents", "complete", iid, "--result-file", str(p)])
    assert res.exit_code == 0, res.output
    row = intents.get_intent(cli_db, iid)
    assert row["status"] == "done" and row["result_ref"] == "upskill_report:7"


def test_cli_intents_complete_invalid_result_does_not_mark_done(cli_db, monkeypatch):
    """An INVALID result (writer rejects) → non-zero exit and the intent stays running,
    NEVER falsely done. This is the $0/integrity guard for the queue."""

    def _reject(db, intent, result):
        raise ValueError("missing required field")

    monkeypatch.setitem(intents._RESULT_WRITERS, "upskill_report", _reject)
    iid = intents.enqueue(cli_db, "upskill_report", {})
    intents.mark_running(cli_db, iid)
    p = _tmp_json({"bad": True})
    res = _run(["intents", "complete", iid, "--result-file", str(p)])
    assert res.exit_code == 2
    assert intents.get_intent(cli_db, iid)["status"] == "running"  # NOT done


def test_cli_intents_complete_missing_file_exits_nonzero(cli_db):
    iid = intents.enqueue(cli_db, "upskill_report", {})
    intents.mark_running(cli_db, iid)
    res = _run(["intents", "complete", iid, "--result-file", "/no/such/file.json"])
    assert res.exit_code == 2
    assert intents.get_intent(cli_db, iid)["status"] == "running"


def test_cli_intents_fail_marks_error(cli_db):
    iid = intents.enqueue(cli_db, "upskill_report", {})
    intents.mark_running(cli_db, iid)
    res = _run(["intents", "fail", iid, "--error", "no browser"])
    assert res.exit_code == 0, res.output
    row = intents.get_intent(cli_db, iid)
    assert row["status"] == "error" and row["error"] == "no browser"


def test_cli_cv_dump_outputs_path(cli_db):
    from engine.normalize import Job

    cli_db.upsert_job(
        Job(
            source="greenhouse",
            source_job_id="5",
            title="Data Scientist",
            company="Acme",
            url="https://x/5",
            description="We need Python and SQL for analytics.",
        )
    )
    jid = cli_db.list_jobs()[0]["id"]
    res = _run(["cv", "dump", jid])
    assert res.exit_code == 0, res.output
    # Rich wraps the printed path at the terminal width; collapse whitespace to assert
    # on the filename regardless of where the console broke the line.
    assert "cv_for_review.yaml" in "".join(res.output.split())
    assert (paths.OUTBOX_DIR / jid / "cv_for_review.yaml").exists()


def test_cli_cv_dump_unknown_job_exits_nonzero(cli_db):
    res = _run(["cv", "dump", "nope"])
    assert res.exit_code == 2


def _tmp_json(obj):
    """Write `obj` as JSON to a fresh temp file and return its Path."""
    import json
    import os
    import tempfile
    from pathlib import Path

    fd, name = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(obj))
    return Path(name)


def test_intent_registries_are_aligned():
    """INTENT_TYPES, PROMPT_FILES, builders and writers must cover exactly the same types —
    drift crashes context_for with a KeyError at runtime, so pin it here instead."""
    types = set(intents.INTENT_TYPES)
    assert set(intents.PROMPT_FILES) == types
    assert set(intents._CONTEXT_BUILDERS) == types
    assert set(intents._RESULT_WRITERS) == types


def test_intent_prompt_files_exist():
    root = Path(__file__).resolve().parents[1]
    for fname in intents.PROMPT_FILES.values():
        assert (root / "brain" / "prompts" / fname).is_file(), fname


# ── stale detection + requeue (Task 6) ──────────────────────────────────────────
# Two real intents on the owner profile sat `pending` for 4+ days with no visible signal.
# `age_hours`/`is_stale` make staleness visible in list_intents/stale_intents, and `requeue`
# gives the brain a way to unstick an `error`/`running` intent back to `pending`.
def test_stale_pending_intent_flagged(db):
    from datetime import UTC, datetime, timedelta

    iid = intents.enqueue(db, "upskill_report", {})
    three_days_ago = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    db.conn.execute("UPDATE intents SET created_at=? WHERE id=?", (three_days_ago, iid))
    db.conn.commit()

    stale = intents.stale_intents(db)
    assert [s["id"] for s in stale] == [iid]

    row = intents.get_intent(db, iid)
    assert row["is_stale"] is True
    assert 71.0 <= row["age_hours"] <= 73.0


def test_fresh_pending_intent_not_stale(db):
    iid = intents.enqueue(db, "upskill_report", {})
    row = intents.get_intent(db, iid)
    assert row["is_stale"] is False
    assert row["age_hours"] is not None and row["age_hours"] < 1.0
    assert intents.stale_intents(db) == []


def test_running_intent_is_never_stale_even_if_old(db):
    """is_stale only applies to `pending` — a long-running intent isn't 'atascado en la cola'."""
    from datetime import UTC, datetime, timedelta

    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    three_days_ago = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    db.conn.execute("UPDATE intents SET created_at=? WHERE id=?", (three_days_ago, iid))
    db.conn.commit()
    row = intents.get_intent(db, iid)
    assert row["is_stale"] is False
    assert intents.stale_intents(db) == []


def test_requeue_error_intent_clears_error_and_reenqueues(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_error(db, iid, "boom")
    row = intents.requeue(db, iid)
    assert row["status"] == "pending"
    assert row["error"] is None
    assert intents.get_intent(db, iid)["status"] == "pending"


def test_requeue_running_intent_becomes_pending(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    row = intents.requeue(db, iid)
    assert row["status"] == "pending"


def test_requeue_done_intent_raises(db):
    iid = intents.enqueue(db, "upskill_report", {})
    intents.mark_running(db, iid)
    intents.mark_done(db, iid, "x:1")
    with pytest.raises(ValueError):
        intents.requeue(db, iid)
    assert intents.get_intent(db, iid)["status"] == "done"


def test_requeue_pending_intent_raises(db):
    iid = intents.enqueue(db, "upskill_report", {})
    with pytest.raises(ValueError):
        intents.requeue(db, iid)


def test_requeue_unknown_id_raises(db):
    with pytest.raises(ValueError):
        intents.requeue(db, "in_nope")


# ── CLI: requeue command + EDAD column + `status` stale warning ────────────────
def test_cli_intents_requeue_marks_pending(cli_db):
    iid = intents.enqueue(cli_db, "upskill_report", {})
    intents.mark_running(cli_db, iid)
    intents.mark_error(cli_db, iid, "boom")
    res = _run(["intents", "requeue", iid])
    assert res.exit_code == 0, res.output
    assert intents.get_intent(cli_db, iid)["status"] == "pending"


def test_cli_intents_requeue_done_exits_nonzero(cli_db):
    iid = intents.enqueue(cli_db, "upskill_report", {})
    intents.mark_running(cli_db, iid)
    intents.mark_done(cli_db, iid, "x:1")
    res = _run(["intents", "requeue", iid])
    assert res.exit_code == 1
    assert intents.get_intent(cli_db, iid)["status"] == "done"


def test_cli_intents_list_shows_age_column(cli_db):
    from datetime import UTC, datetime, timedelta

    iid = intents.enqueue(cli_db, "upskill_report", {})
    three_days_ago = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    cli_db.conn.execute("UPDATE intents SET created_at=? WHERE id=?", (three_days_ago, iid))
    cli_db.conn.commit()
    res = _run(["intents", "list"])
    assert res.exit_code == 0, res.output
    assert "71" in res.output or "72" in res.output or "73" in res.output


def test_cli_status_warns_about_stale_intents(cli_db):
    from datetime import UTC, datetime, timedelta

    iid = intents.enqueue(cli_db, "upskill_report", {})
    three_days_ago = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    cli_db.conn.execute("UPDATE intents SET created_at=? WHERE id=?", (three_days_ago, iid))
    cli_db.conn.commit()
    res = _run(["status"])
    assert res.exit_code == 0, res.output
    assert "atascado" in res.output


def test_cli_status_no_warning_when_no_stale_intents(cli_db):
    res = _run(["status"])
    assert res.exit_code == 0, res.output
    assert "atascado" not in res.output
