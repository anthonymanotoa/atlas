"""Reply-aware follow-up cadence.

Day 0 send → follow-ups at ~Day 3, 7, 14 → a polite breakup at ~Day 21, then STOP.
Hard cap of 4 touches. The instant a reply lands, all pending follow-ups are cancelled
(`register_reply`) so the system never pesters someone who already responded.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from engine.db.models import DB
from engine.outreach.templates import Draft, _first_name

# (touch_number, day_offset, is_breakup)
CADENCE = [(1, 3, False), (2, 7, False), (3, 14, False), (4, 21, True)]


def _parse(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return datetime.now(timezone.utc)


def schedule(db: DB, job_id: str, *, channel: str, message_id: int | None = None,
             base_iso: str | None = None) -> int:
    """Create the follow-up schedule for a sent message. Idempotent per job+channel."""
    # Consider ALL existing touches (pending/done/cancelled) so a catch-up re-run never
    # recreates a completed touch or resurrects one cancelled because the contact replied.
    existing = {f["touch_number"] for f in db.followups_for_job(job_id, channel)}
    base = _parse(base_iso) if base_iso else datetime.now(timezone.utc)
    created = 0
    for touch, offset, _breakup in CADENCE:
        if touch in existing:
            continue
        due = (base + timedelta(days=offset)).isoformat()
        db.add_followup(job_id, channel=channel, touch_number=touch, due_at=due,
                        message_id=message_id)
        created += 1
    return created


def register_reply(db: DB, job_id: str) -> None:
    """A reply arrived — cancel pending follow-ups and advance the job to 'responded'."""
    db.cancel_followups_for_job(job_id)
    job = db.get_job(job_id)
    if job and job.get("state") in ("applied", "ready", "drafted", "tailored", "shortlisted"):
        db.set_state(job_id, "responded", {"trigger": "reply"})


def followup_text(job: dict, candidate: dict, touch_number: int, language: str = "en") -> Draft:
    company, role = job.get("company", ""), job.get("title", "")
    me = candidate.get("name", "")
    is_breakup = touch_number >= 4
    if language == "es":
        if is_breakup:
            body = (f"Hola, cierro el hilo por ahora para no insistir. Sigo muy interesado en el "
                    f"rol de {role} en {company} — si se reactiva, encantado de retomar. ¡Gracias!\n\n{me}")
        else:
            body = (f"Hola, retomo brevemente mi mensaje sobre el rol de {role} en {company}. Sigo "
                    f"muy interesado y disponible. ¿Habría oportunidad de conversar?\n\n{me}")
    else:
        if is_breakup:
            body = (f"Hi — I'll close the loop here so I'm not a bother. I remain very interested in "
                    f"the {role} role at {company}; if it reopens, I'd love to reconnect. Thanks!\n\n{me}")
        else:
            body = (f"Hi — circling back on my note about the {role} role at {company}. Still very "
                    f"interested and available. Would there be a chance to chat?\n\n{me}")
    kind = "breakup" if is_breakup else "follow_up"
    return Draft(kind, "email", body, subject=f"Re: {role} at {company}",
                 variant=f"touch{touch_number}", language=language)
