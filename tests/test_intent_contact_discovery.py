"""contact_discovery intent (Task 15): the brain proposes CANDIDATE contacts (people who
might work at the company, mined from public sources) plus an optional draft outreach
message. These are candidates, not verified facts — every contact carries a `confidence` so
the human can judge it, and nothing is ever sent: `add_contact` only creates rows and any
draft message is persisted in state='draft'."""

from __future__ import annotations

import pytest

from engine import intents
from engine.db.models import DB
from engine.normalize import Job, norm_company


@pytest.fixture
def db(tmp_path):
    with DB(tmp_path / "t.db") as d:
        yield d


def _job(db, source_job_id="1", company="Acme Robotics", title="Data Scientist"):
    db.upsert_job(
        Job(
            source="lever",
            source_job_id=source_job_id,
            title=title,
            company=company,
            url=f"https://x/{source_job_id}",
            description="Build cool things.",
        )
    )
    return [j for j in db.list_jobs() if j["company"] == company][0]["id"]


def test_contact_discovery_is_a_registered_intent_type():
    assert "contact_discovery" in intents.INTENT_TYPES
    assert intents.PROMPT_FILES["contact_discovery"] == "contact_discovery.md"


def test_context_includes_company_role_and_existing_contacts(db):
    db.add_contact(name="Prior Contact", company="Acme Robotics", role="connection", source="manual")
    jid = _job(db)
    iid = intents.enqueue(db, "contact_discovery", {"role_title": "Hiring Manager"}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["company"] == "Acme Robotics"
    assert ctx["role_title"] == "Hiring Manager"
    assert ctx["job_brief"]["id"] == jid
    assert any(c["name"] == "Prior Contact" for c in ctx["existing_contacts"])


def test_context_defaults_role_title_to_job_title_when_absent(db):
    jid = _job(db, title="Staff Engineer")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    ctx = intents.context_for(db, iid)
    assert ctx["role_title"] == "Staff Engineer"


def test_apply_result_creates_contacts_with_confidence_and_draft_message(db):
    jid = _job(db)
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {
            "contacts": [
                {
                    "name": "Jane Doe",
                    "role": "Engineering Manager",
                    "profile_url": "https://linkedin.com/in/janedoe",
                    "confidence": "high",
                    "reasoning": "Listed as Eng Manager on the team page.",
                },
                {
                    "name": "John Roe",
                    "role": "Recruiter",
                    "profile_url": "https://linkedin.com/in/johnroe",
                    "confidence": "medium",
                    "reasoning": "Posted the job on LinkedIn.",
                },
            ],
            "draft_message": "Hi Jane, I noticed the Data Scientist opening on your team...",
        },
    )
    assert ref == "contacts:2"
    contacts = db.contacts_for_company(norm_company("Acme Robotics"))
    names = {c["name"] for c in contacts}
    assert {"Jane Doe", "John Roe"} <= names
    for c in contacts:
        if c["name"] in ("Jane Doe", "John Roe"):
            assert c["source"] == "brain_research"
            assert "confidence=" in (c["notes"] or "")
    jane = next(c for c in contacts if c["name"] == "Jane Doe")
    assert "confidence=high" in jane["notes"]
    assert "Eng Manager on the team page" in jane["notes"]

    msgs = [m for m in db.messages_for(jid) if m["kind"] == "referral_or_intro"]
    assert len(msgs) == 1
    assert msgs[0]["state"] == "draft"
    assert "Jane" in msgs[0]["body"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_apply_result_persists_confidence_on_existing_contact_name_collision(db):
    """Regression: a brain re-discovery of a contact already in the DB (e.g. a prior
    connections_csv import) must still persist confidence/reasoning and be surfaced as
    brain-corroborated — add_contact's ON CONFLICT never touched notes/role/source, so this
    used to be silently dropped while apply_result still reported success."""
    jid = _job(db, source_job_id="9", company="Kappa Systems")
    db.add_contact(
        name="Jane Doe",
        company="Kappa Systems",
        source="connections_csv",
        role="connection",
        notes=None,
    )
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    intents.apply_result(
        db,
        iid,
        {
            "contacts": [
                {
                    "name": "Jane Doe",
                    "confidence": "high",
                    "reasoning": "Found on team page",
                }
            ]
        },
    )
    contacts = db.contacts_for_company(norm_company("Kappa Systems"))
    jane = next(c for c in contacts if c["name"] == "Jane Doe")
    assert "high" in (jane["notes"] or "")
    assert jane["source"] == "brain_research"
    assert intents.get_intent(db, iid)["status"] == "done"


def test_apply_result_preserves_preexisting_human_note_on_collision(db):
    """A pre-existing human-written note must be preserved (appended to, not clobbered)
    when the brain re-discovers the same contact."""
    jid = _job(db, source_job_id="10", company="Lambda Corp")
    db.add_contact(
        name="John Roe",
        company="Lambda Corp",
        source="manual",
        role="hiring_manager",
        notes="Met at conference, very responsive.",
    )
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    intents.apply_result(
        db,
        iid,
        {
            "contacts": [
                {
                    "name": "John Roe",
                    "confidence": "medium",
                    "reasoning": "Listed as hiring manager on job post",
                }
            ]
        },
    )
    contacts = db.contacts_for_company(norm_company("Lambda Corp"))
    john = next(c for c in contacts if c["name"] == "John Roe")
    assert "Met at conference, very responsive." in john["notes"]
    assert "confidence=medium" in john["notes"]


def test_apply_result_without_draft_message_creates_no_message(db):
    jid = _job(db, source_job_id="2", company="Beta Co")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    intents.apply_result(
        db,
        iid,
        {
            "contacts": [
                {"name": "Solo Contact", "role": "Recruiter", "confidence": "low"},
            ]
        },
    )
    assert [m for m in db.messages_for(jid) if m["kind"] == "referral_or_intro"] == []


def test_apply_result_contact_missing_confidence_raises_and_stays_running(db):
    jid = _job(db, source_job_id="3", company="Gamma Inc")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid, {"contacts": [{"name": "No Confidence Guy", "role": "Recruiter"}]}
        )
    assert intents.get_intent(db, iid)["status"] == "running"
    contacts = db.contacts_for_company(norm_company("Gamma Inc"))
    assert not any(c["name"] == "No Confidence Guy" for c in contacts)


def test_apply_result_contact_bad_confidence_value_raises(db):
    jid = _job(db, source_job_id="4", company="Delta LLC")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db,
            iid,
            {"contacts": [{"name": "Bad Conf", "role": "Recruiter", "confidence": "certain"}]},
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_result_empty_contacts_list_raises(db):
    jid = _job(db, source_job_id="5", company="Epsilon")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"contacts": []})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_apply_result_contact_missing_name_raises(db):
    jid = _job(db, source_job_id="6", company="Zeta")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"contacts": [{"role": "Recruiter", "confidence": "low"}]})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_nothing_is_ever_marked_sent(db):
    """Regression guard for the never-send invariant: no code path in this writer can
    produce a message or a contact in a 'sent' state."""
    jid = _job(db, source_job_id="7", company="Theta")
    iid = intents.enqueue(db, "contact_discovery", {}, job_id=jid)
    intents.mark_running(db, iid)
    intents.apply_result(
        db,
        iid,
        {
            "contacts": [{"name": "Never Sent", "role": "Recruiter", "confidence": "high"}],
            "draft_message": "Hello there",
        },
    )
    msgs = [m for m in db.messages_for(jid) if m["kind"] == "referral_or_intro"]
    assert all(m["state"] != "sent" and m.get("sent_at") is None for m in msgs)


def test_write_package_lists_suggested_contacts(db, tmp_path, monkeypatch):
    import engine.paths as paths
    from engine.outreach.build import write_package

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    jid = _job(db, source_job_id="8", company="Iota Robotics")
    db.add_contact(
        name="Suggested Person",
        company="Iota Robotics",
        title="Engineering Manager",
        role="referral",
        source="brain_research",
        notes="[brain_research] confidence=high; found on team page.",
    )
    path = write_package(db, jid, language="es")
    text = path.read_text()
    assert "Contactos sugeridos" in text
    assert "Suggested Person" in text
    assert "high" in text
