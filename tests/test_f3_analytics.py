"""F3 §6.2: funnel con tasas, score floor empírico, conversión por dimensión, tiempos de respuesta."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine import analytics
from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _mk(db: DB, n: int, *, source="greenhouse", title="Data Scientist", wt="remote") -> str:
    db.upsert_job(
        Job(
            source=source,
            source_job_id=str(n),
            title=title,
            company=f"Acme{n}",
            location="Remote",
            workplace_type=wt,
            url=f"https://x/{n}",
        )
    )
    return [j for j in db.list_jobs() if j["company"] == f"Acme{n}"][0]["id"]


def test_funnel_counts_and_rates(db: DB):
    a, b = _mk(db, 1), _mk(db, 2)
    for jid in (a, b):
        db.set_state(jid, "scored")
        db.set_state(jid, "shortlisted")
        db.set_state(jid, "applied")
    db.set_state(a, "responded")
    stages = {s["stage"]: s for s in analytics.funnel(db)}
    assert stages["discovered"]["count"] == 2 and stages["discovered"]["rate"] is None
    assert stages["applied"]["count"] == 2
    assert stages["responded"]["count"] == 1 and stages["responded"]["rate"] == 0.5


def test_score_floor_empirical(db: DB):
    a, b, c = _mk(db, 1), _mk(db, 2), _mk(db, 3)
    db.set_fit(a, 71.0, [], [])
    db.set_fit(b, 64.0, [], [])
    db.set_fit(c, 40.0, [], [])
    db.set_state(a, "applied")
    db.set_state(a, "responded")
    db.record_outcome(b, "Acme2", final_state="interviewed")
    # c (score 40) no tiene outcome positivo → el floor es 64, no 40
    assert analytics.score_floor(db) == 64.0


def test_score_floor_none_without_positives(db: DB):
    _mk(db, 1)
    assert analytics.score_floor(db) is None


def test_conversion_by_source_and_role_term(db: DB):
    crit = Criteria(roles=["data scientist", "ml engineer"])
    a = _mk(db, 1, source="greenhouse", title="Data Scientist")
    b = _mk(db, 2, source="lever", title="ML Engineer")
    for jid in (a, b):
        db.set_state(jid, "applied")
    db.set_state(a, "responded")
    by_src = {r["key"]: r for r in analytics.conversion_by(db, "source")}
    assert by_src["greenhouse"]["applied"] == 1 and by_src["greenhouse"]["response_rate"] == 1.0
    assert by_src["lever"]["response_rate"] == 0.0
    by_term = {r["key"]: r for r in analytics.conversion_by(db, "role_term", crit)}
    assert by_term["data scientist"]["responded"] == 1
    assert by_term["ml engineer"]["responded"] == 0


def test_conversion_by_unknown_dim_raises(db: DB):
    with pytest.raises(ValueError):
        analytics.conversion_by(db, "astrology")


def test_response_times_from_timestamps_and_outcomes(db: DB):
    a = _mk(db, 1)
    db.set_state(a, "applied")
    db.conn.execute(
        "UPDATE jobs SET applied_at='2026-06-01T00:00:00+00:00', "
        "responded_at='2026-06-08T00:00:00+00:00' WHERE id=?",
        (a,),
    )
    db.conn.commit()
    db.record_outcome(None, "Beta Corp", final_state="responded", response_days=3)
    rt = analytics.response_times(db)
    assert rt["n"] == 2 and rt["avg_days"] == 5.0 and rt["median_days"] == 5.0


# ── §6.2 Recomendaciones deterministas ────────────────────────────────────────
def test_recommendations_threshold_and_block(db: DB):
    crit = Criteria(roles=["data scientist"], shortlist_threshold=60.0)
    # 3 positivos con floor 66 → recomienda subir threshold a 66
    for n, score in ((1, 66.0), (2, 70.0), (3, 80.0)):
        jid = _mk(db, n)
        db.set_fit(jid, score, [], [])
        db.set_state(jid, "applied")
        db.set_state(jid, "responded")
    # Ghost Corp: 3 aplicaciones sin respuesta → recomienda bloquear
    for n in (4, 5, 6):
        db.upsert_job(
            Job(
                source="lever",
                source_job_id=str(n),
                title=f"DS {n}",
                company="Ghost Corp",
                location="Remote",
                url=f"https://g/{n}",
            )
        )
    for j in db.list_jobs():
        if j["company"] == "Ghost Corp":
            db.set_state(j["id"], "applied")
    recs = analytics.recommendations(db, crit)
    by_type = {r["action_type"]: r for r in recs}
    assert by_type["set_criteria"]["payload"] == {"field": "shortlist_threshold", "value": 66.0}
    assert by_type["block_company"]["payload"] == {"company": "Ghost Corp"}
    assert all({"id", "text", "action_type", "payload"} <= set(r) for r in recs)


def test_recommendations_no_block_when_outcome_logged_positive(db: DB):
    """Regresión: registrar un outcome positivo por formulario (record_outcome, SIN set_state)
    NO estampa los timestamps del funnel de `jobs`, pero la empresa SÍ respondió — nunca debe
    recomendarse bloquearla. La rec de block debe consultar application_outcomes, no sólo jobs."""
    crit = Criteria(roles=["data scientist"])
    # Ghost Corp: 3 aplicaciones; el usuario registra por formulario que respondieron/entrevistaron.
    jids = []
    for n in (1, 2, 3):
        db.upsert_job(
            Job(
                source="lever",
                source_job_id=str(n),
                title=f"DS {n}",
                company="Ghost Corp",
                location="Remote",
                url=f"https://g/{n}",
            )
        )
    for j in db.list_jobs():
        if j["company"] == "Ghost Corp":
            db.set_state(j["id"], "applied")
            jids.append(j["id"])
    # Outcomes positivos vía record_outcome — NO se llama set_state, así que responded_at/etc siguen NULL.
    db.record_outcome(jids[0], "Ghost Corp", final_state="responded")
    db.record_outcome(jids[1], "Ghost Corp", final_state="interviewed")
    db.record_outcome(jids[2], "Ghost Corp", final_state="responded")
    blocks = [r for r in analytics.recommendations(db, crit) if r["action_type"] == "block_company"]
    assert not blocks, (
        "no debe recomendar bloquear una empresa que registró respuesta por formulario"
    )


def test_recommendations_skip_already_blocked(db: DB):
    crit = Criteria(roles=["data scientist"], company_blocklist=["Ghost Corp"])
    for n in (1, 2, 3):
        db.upsert_job(
            Job(
                source="lever",
                source_job_id=str(n),
                title=f"DS {n}",
                company="Ghost Corp",
                location="Remote",
                url=f"https://g/{n}",
            )
        )
    for j in db.list_jobs():
        db.set_state(j["id"], "applied")
    assert not [
        r for r in analytics.recommendations(db, crit) if r["action_type"] == "block_company"
    ]


def test_recommendations_conservative_below_thresholds(db: DB):
    """Nada dispara por debajo de los umbrales: 1 aplicación sin respuesta NO bloquea,
    y menos de 3 positivos NO sube el threshold aunque el floor sea alto."""
    crit = Criteria(roles=["data scientist"], shortlist_threshold=60.0)
    # 1 solo positivo con score 90 (floor alto) → NO sube threshold (positives < 3)
    a = _mk(db, 1)
    db.set_fit(a, 90.0, [], [])
    db.set_state(a, "applied")
    db.set_state(a, "responded")
    # 1 sola aplicación a Lonely Corp sin respuesta → NO la bloquea (n < 3)
    db.upsert_job(
        Job(
            source="lever",
            source_job_id="99",
            title="DS",
            company="Lonely Corp",
            location="Remote",
            url="https://l/99",
        )
    )
    for j in db.list_jobs():
        if j["company"] == "Lonely Corp":
            db.set_state(j["id"], "applied")
    recs = analytics.recommendations(db, crit)
    types = {r["action_type"] for r in recs}
    assert "set_criteria" not in types
    assert "block_company" not in types


def test_recommendations_dead_role_term_is_informational(db: DB):
    """Un role-term con ≥5 aplicaciones y 0 respuestas produce una rec informativa (action none)."""
    crit = Criteria(roles=["data scientist"])
    for n in range(1, 6):  # 5 aplicaciones "Data Scientist", ninguna con respuesta
        jid = _mk(db, n, title="Data Scientist")
        db.set_state(jid, "applied")
    recs = analytics.recommendations(db, crit)
    dead = [r for r in recs if r["action_type"] == "none"]
    assert dead and dead[0]["payload"] == {"term": "data scientist"}


def test_analytics_payload_shape(db: DB):
    p = analytics.analytics_payload(db, Criteria())
    assert {
        "funnel",
        "score_floor",
        "by_source",
        "by_ats",
        "by_remote_policy",
        "by_role_term",
        "response_times",
        "recommendations",
        "response_rate_by_channel",
        "response_rate_by_cv_version",
    } <= set(p)


# ── Task 19: outcome calibration — response rate por canal y por versión de CV ─────────────
def _mk_outreach(
    db: DB,
    n: int,
    *,
    channel: str = "email",
    ats_target: str = "greenhouse",
    responded: bool = False,
) -> str:
    """Un job APLICADO con un mensaje ENVIADO (channel) y una CV tailoreada empaquetada en
    `applications` (ats_target) — los dos insumos que Task 19 necesita para atribuir canal y
    versión de CV a un resultado."""
    jid = _mk(db, n)
    db.set_state(jid, "applied")
    if responded:
        db.set_state(jid, "responded")
    cv_id = db.add_cv_version(
        jid,
        language="en",
        ats_target=ats_target,
        path_docx=None,
        path_pdf=None,
        keyword_coverage=0.8,
        matched=[],
        missing=[],
        parse_ok=True,
    )
    db.add_application(jid, method="ats_form", apply_url=None, cv_version_id=cv_id)
    db.add_message(jid, channel=channel, kind="cover_letter", body="x", state="sent")
    return jid


def test_response_rate_by_channel(db: DB):
    # 6 jobs por email, 3 responden → n=6 (≥5) suficiente, rate=0.5
    for n in range(1, 7):
        _mk_outreach(db, n, channel="email", responded=n <= 3)
    # 3 jobs por linkedin, 1 responde → n=3 (<5) insuficiente, sin % engañoso
    for n in range(7, 10):
        _mk_outreach(db, n, channel="linkedin_note", responded=n == 7)
    rows = {r["key"]: r for r in analytics.response_rate_by_channel(db)}
    assert rows["email"]["applied"] == 6
    assert rows["email"]["responded"] == 3
    assert rows["email"]["n"] == 6
    assert rows["email"]["response_rate"] == 0.5
    assert rows["email"]["insufficient"] is False
    assert rows["linkedin"]["applied"] == 3
    assert rows["linkedin"]["n"] == 3
    assert rows["linkedin"]["response_rate"] is None
    assert rows["linkedin"]["insufficient"] is True


def test_response_rate_by_channel_job_without_sent_message_is_excluded(db: DB):
    """Un job aplicado sin ningún mensaje `sent` no se puede atribuir a ningún canal — se
    excluye en vez de inventar una atribución (regla anti-fabricación)."""
    jid = _mk(db, 1)
    db.set_state(jid, "applied")
    rows = analytics.response_rate_by_channel(db)
    assert rows == []


def test_response_rate_by_cv_version(db: DB):
    # 5 aplicaciones con CV target 'greenhouse', 4 responden → n=5 suficiente, rate=0.8
    for n in range(1, 6):
        _mk_outreach(db, n, ats_target="greenhouse", responded=n <= 4)
    # 3 aplicaciones con CV target 'lever', 0 responden → n=3 insuficiente
    for n in range(6, 9):
        _mk_outreach(db, n, ats_target="lever", responded=False)
    rows = {r["key"]: r for r in analytics.response_rate_by_cv_version(db)}
    assert rows["greenhouse"]["applied"] == 5
    assert rows["greenhouse"]["responded"] == 4
    assert rows["greenhouse"]["n"] == 5
    assert rows["greenhouse"]["response_rate"] == 0.8
    assert rows["greenhouse"]["insufficient"] is False
    assert rows["lever"]["applied"] == 3
    assert rows["lever"]["response_rate"] is None
    assert rows["lever"]["insufficient"] is True


def test_response_rate_by_cv_version_without_application_row_is_excluded(db: DB):
    """Un job aplicado cuya CV nunca se empaquetó en `applications` (cv_version_id) no se
    puede atribuir a ninguna versión — se excluye en vez de adivinar."""
    jid = _mk(db, 1)
    db.set_state(jid, "applied")
    db.add_cv_version(
        jid,
        language="en",
        ats_target="greenhouse",
        path_docx=None,
        path_pdf=None,
        keyword_coverage=0.8,
        matched=[],
        missing=[],
        parse_ok=True,
    )
    rows = analytics.response_rate_by_cv_version(db)
    assert rows == []
