"""Reply-aware follow-up cadence.

Day 0 send → follow-ups at ~Day 3, 7, 14 → a polite breakup at ~Day 21, then STOP.
Hard cap of 4 touches. The instant a reply lands, all pending follow-ups are cancelled
(`register_reply`) so the system never pesters someone who already responded.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import parse_dt_utc
from engine.outreach.templates import Draft

# (touch_number, day_offset, is_breakup)
CADENCE = [(1, 3, False), (2, 7, False), (3, 14, False), (4, 21, True)]


def _parse(iso: str) -> datetime:
    return parse_dt_utc(iso) or datetime.now(UTC)


def schedule(
    db: DB, job_id: str, *, channel: str, message_id: int | None = None, base_iso: str | None = None
) -> int:
    """Create the follow-up schedule for a sent message. Idempotent per job+channel."""
    # Consider ALL existing touches (pending/done/cancelled) so a catch-up re-run never
    # recreates a completed touch or resurrects one cancelled because the contact replied.
    existing = {f["touch_number"] for f in db.followups_for_job(job_id, channel)}
    base = _parse(base_iso) if base_iso else datetime.now(UTC)
    created = 0
    for touch, offset, _breakup in CADENCE:
        if touch in existing:
            continue
        due = (base + timedelta(days=offset)).isoformat()
        db.add_followup(
            job_id, channel=channel, touch_number=touch, due_at=due, message_id=message_id
        )
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
            body = (
                f"Hola, cierro el hilo por ahora para no insistir. Sigo muy interesado en el "
                f"rol de {role} en {company} — si se reactiva, encantado de retomar. ¡Gracias!\n\n{me}"
            )
        else:
            body = (
                f"Hola, retomo brevemente mi mensaje sobre el rol de {role} en {company}. Sigo "
                f"muy interesado y disponible. ¿Habría oportunidad de conversar?\n\n{me}"
            )
    else:
        if is_breakup:
            body = (
                f"Hi — I'll close the loop here so I'm not a bother. I remain very interested in "
                f"the {role} role at {company}; if it reopens, I'd love to reconnect. Thanks!\n\n{me}"
            )
        else:
            body = (
                f"Hi — circling back on my note about the {role} role at {company}. Still very "
                f"interested and available. Would there be a chance to chat?\n\n{me}"
            )
    kind = "breakup" if is_breakup else "follow_up"
    return Draft(
        kind,
        "email",
        body,
        subject=f"Re: {role} at {company}",
        variant=f"touch{touch_number}",
        language=language,
    )


# ── Cadencia v2 por estado (F3 §6.1) ─────────────────────────────────────────
# Los toques v2 llevan `kind` = estado que los sembró y se confirman a mano en /followups
# (el brain NUNCA los auto-draftea — ver brain/run_brain.py). Los toques legacy del plan
# 006 (kind NULL, creados por schedule()) siguen intactos para el flujo por mensaje.
CADENCE_STATES = ("applied", "responded", "interview")
URGENT_WINDOW_DAYS = 3  # vencido < 3d → URGENT; ≥ 3d → OVERDUE


def cadence_for(state: str, criteria: Criteria) -> tuple[int, int] | None:
    """(days, max_touches) para un estado, o None si el estado no lleva cadencia."""
    cfg = (criteria.followup_cadence or {}).get(state)
    if not cfg:
        return None
    days, max_touches = int(cfg.get("days", 0)), int(cfg.get("max_touches", 0))
    if days <= 0 or max_touches <= 0:
        return None
    return days, max_touches


def seed_for_state(
    db: DB, job_id: str, state: str, criteria: Criteria, *, base_iso: str | None = None
) -> int | None:
    """Siembra el SIGUIENTE toque de la cadencia de `state`. Idempotente: nunca duplica un
    pending ni supera max_touches (cuenta done/cancelled también, como schedule())."""
    cad = cadence_for(state, criteria)
    if cad is None:
        return None
    days, max_touches = cad
    existing = [f for f in db.followups_for_job(job_id) if f.get("kind") == state]
    if any(f["state"] == "pending" for f in existing) or len(existing) >= max_touches:
        return None
    touch = (max((f["touch_number"] or 0) for f in existing) + 1) if existing else 1
    base = _parse(base_iso) if base_iso else datetime.now(UTC)
    due = (base + timedelta(days=days)).isoformat()
    return db.add_followup(job_id, channel="email", touch_number=touch, due_at=due, kind=state)


def register_sent(db: DB, followup_id: int, criteria: Criteria) -> dict:
    """Confirmación humana de envío: marca done y siembra el siguiente toque si queda cupo."""
    row = db.conn.execute("SELECT * FROM followups WHERE id=?", (followup_id,)).fetchone()
    if row is None:
        return {"ok": False, "next_id": None}
    f = dict(row)
    db.mark_followup(followup_id, "done")
    next_id = seed_for_state(db, f["job_id"], f["kind"], criteria) if f.get("kind") else None
    return {"ok": True, "next_id": next_id}


def bucket_followups(followups: list[dict], now: datetime) -> dict[str, list[dict]]:
    """Clasificación PURA de follow-ups pending en urgencia. No toca la DB.

    `now` es un parámetro explícito (nunca datetime.now() interno) para que los tests sean
    deterministas. `waiting` = aún no vence; `urgent` = vencido hace < URGENT_WINDOW_DAYS;
    `overdue` = vencido hace ≥ URGENT_WINDOW_DAYS. Los toques no-pending se ignoran.
    """
    buckets: dict[str, list[dict]] = {"urgent": [], "overdue": [], "waiting": []}
    for f in followups:
        if f.get("state") != "pending":
            continue
        due = _parse(f.get("due_at") or "")
        overdue_days = (now - due).total_seconds() / 86400
        item = {**f, "days_overdue": round(max(overdue_days, 0.0), 1)}
        if overdue_days < 0:
            buckets["waiting"].append(item)
        elif overdue_days < URGENT_WINDOW_DAYS:
            buckets["urgent"].append(item)
        else:
            buckets["overdue"].append(item)
    for rows in buckets.values():
        rows.sort(key=lambda r: r.get("due_at") or "")
    return buckets


def cold_jobs(db: DB, criteria: Criteria) -> list[dict]:
    """Jobs 'applied' con la cadencia agotada (todos los toques done, sin pending) → COLD."""
    cad = cadence_for("applied", criteria)
    if cad is None:
        return []
    _, max_touches = cad
    rows = db.conn.execute(
        """SELECT j.id AS job_id, j.title, j.company, j.applied_at,
                  SUM(CASE WHEN f.state='done' THEN 1 ELSE 0 END) AS touches_done,
                  SUM(CASE WHEN f.state='pending' THEN 1 ELSE 0 END) AS touches_pending
           FROM jobs j JOIN followups f ON f.job_id = j.id AND f.kind='applied'
           WHERE j.state='applied'
           GROUP BY j.id"""
    ).fetchall()
    return [dict(r) for r in rows if r["touches_pending"] == 0 and r["touches_done"] >= max_touches]


# ── Drafts deterministas (§6.1): value-first, sin "just checking in", <150 palabras ──
def draft_followup(
    job: dict,
    candidate_name: str,
    kind: str,
    touch_number: int,
    language: str = "en",
    highlight: str = "",
) -> Draft:
    company, role, me = job.get("company", ""), job.get("title", ""), candidate_name
    hl_en = (
        f" — for example, my work with {highlight} maps directly to what the role needs"
        if highlight
        else ""
    )
    hl_es = (
        f" — por ejemplo, mi experiencia con {highlight} encaja directo con lo que pide el rol"
        if highlight
        else ""
    )
    if language == "es":
        bodies = {
            "applied": {
                1: (
                    f"Hola — apliqué al rol de {role} en {company} y quería sumar contexto útil: "
                    f"llego con resultados concretos en problemas como los que describe la vacante"
                    f"{hl_es}. Si les sirve, puedo compartir un ejemplo breve de un proyecto "
                    f"comparable. ¿Tiene sentido una conversación corta esta semana?\n\n{me}"
                ),
                2: (
                    f"Hola — segundo y último toque sobre el rol de {role} en {company}. Desde mi "
                    f"aplicación estuve pensando en su contexto{hl_es}; si el proceso sigue "
                    f"abierto, encantado de mostrar cómo abordaría los primeros 90 días. Si ya "
                    f"avanzaron con otra persona, también agradezco saberlo.\n\n{me}"
                ),
            },
            "responded": {
                1: (
                    f"Hola — gracias por responder sobre el rol de {role} en {company}. Para "
                    f"facilitar el siguiente paso: tengo disponibilidad esta semana y puedo "
                    f"adelantar material relevante{hl_es}. ¿Qué horario les acomoda?\n\n{me}"
                )
            },
            "interview": {
                1: (
                    f"Hola — gracias por la conversación de hoy sobre el rol de {role} en "
                    f"{company}. Me quedé pensando en los retos que mencionaron{hl_es}; quedo "
                    f"atento a los siguientes pasos y disponible para cualquier profundización."
                    f"\n\n{me}"
                )
            },
        }
        subject = f"Re: {role} en {company}"
    else:
        bodies = {
            "applied": {
                1: (
                    f"Hi — I applied for the {role} role at {company} and wanted to add useful "
                    f"context: I bring concrete results on the kind of problems the posting "
                    f"describes{hl_en}. Happy to share a short example of comparable work if "
                    f"helpful. Would a brief chat this week make sense?\n\n{me}"
                ),
                2: (
                    f"Hi — second and final note on the {role} role at {company}. Since applying "
                    f"I've been thinking about your context{hl_en}; if the process is still open, "
                    f"I'd love to show how I'd approach the first 90 days. If you've moved forward "
                    f"with someone else, I'd appreciate knowing that too.\n\n{me}"
                ),
            },
            "responded": {
                1: (
                    f"Hi — thanks for getting back about the {role} role at {company}. To make the "
                    f"next step easy: I'm available this week and can send relevant material ahead "
                    f"of time{hl_en}. What time works for you?\n\n{me}"
                )
            },
            "interview": {
                1: (
                    f"Hi — thank you for today's conversation about the {role} role at {company}. "
                    f"I kept thinking about the challenges you mentioned{hl_en}; looking forward "
                    f"to next steps, and happy to go deeper on anything.\n\n{me}"
                )
            },
        }
        subject = f"Re: {role} at {company}"
    per_kind = bodies.get(kind) or bodies["applied"]
    body = per_kind.get(touch_number) or per_kind[max(per_kind)]
    return Draft(
        "follow_up",
        "email",
        body,
        subject=subject,
        variant=f"{kind}-touch{touch_number}",
        language=language,
    )
