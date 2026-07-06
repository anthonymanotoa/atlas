"""engine/upskill.py — diff duro de skills (pasada 1) + writer del reporte (F4 §7.2).

Pasada 1 (hard_skill_gaps) es DETERMINISTA: reusa la ontología/keywords del tailor y pesa
cada skill faltante por lo mal que encajas (`Σ (100 − fit_score)/100`). No hay LLM ($0). El
writer solo VALIDA + PERSISTE la síntesis del brain (report_md + heatmap); malformado → raise.
"""

from __future__ import annotations

import pytest

import engine.paths as paths
from engine import intents
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    with DB(tmp_path / "t.db") as d:
        d.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="ML Engineer",
                company="Acme",
                url="https://x/1",
                description="We need Kubernetes, Terraform and Go for our platform team.",
            )
        )
        jid = d.list_jobs()[0]["id"]
        d.set_fit(jid, 30.0, [], [])  # peor encaje → pesa más
        yield d


def test_hard_skill_gaps_weights_worse_fits_higher(db):
    from engine.upskill import hard_skill_gaps

    out = hard_skill_gaps(db, ["discovered"])
    assert out["jobs_considered"] == 1
    assert out["skills"], "should surface at least one missing skill"
    assert out["generated_at"]
    top = out["skills"][0]
    # score = Σ (100 − fit)/100 = (100 − 30)/100 = 0.7 for a single occurrence
    assert top["occurrences"] == 1
    assert abs(top["score"] - 0.7) < 1e-6
    assert top["worst_fit"] == 30.0
    assert db.list_jobs()[0]["id"] in top["jobs"]


def test_hard_skill_gaps_missing_fit_treated_as_perfect(db):
    """A job without a fit_score contributes weight 0 (no gap pressure) — a NULL fit is not
    treated as a low fit; only jobs you demonstrably fit BADLY push their gaps up."""
    from engine.normalize import Job
    from engine.upskill import hard_skill_gaps

    db.upsert_job(
        Job(
            source="lever",
            source_job_id="2",
            title="Platform Engineer",
            company="Beta",
            url="https://x/2",
            description="Kubernetes heavy shop.",
        )
    )
    # second job has NO fit_score → weight 0; the 30-fit job still dominates the score.
    out = hard_skill_gaps(db, ["discovered"])
    assert out["jobs_considered"] == 2
    k8s = next(s for s in out["skills"] if s["skill"] == "kubernetes")
    assert k8s["occurrences"] == 2  # seen in both JDs
    assert abs(k8s["score"] - 0.7) < 1e-6  # only the low-fit job adds weight (0.7 + 0.0)
    assert k8s["worst_fit"] == 30.0


def test_hard_skill_gaps_empty_when_no_jobs(db):
    from engine.upskill import hard_skill_gaps

    out = hard_skill_gaps(db, ["applied"])
    assert out["skills"] == []
    assert out["jobs_considered"] == 0
    assert out["generated_at"]


def test_upskill_writer_persists_report_and_marks_done(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {
            "report_md": "# Plan de upskilling\n\n## Kubernetes\nEmpieza por…",
            "heatmap": [
                {"skill": "Kubernetes", "severity": "Critical", "note": "3 vacantes lo exigen"},
                {"skill": "Go", "severity": "Medium", "note": "adyacente a tu Python"},
            ],
        },
    )
    assert ref.startswith("upskill_report:")
    latest = db.latest_upskill_report()
    assert latest["report_md"].startswith("# Plan")
    assert latest["heatmap"][0]["severity"] == "Critical"
    # the deterministic pass-1 payload is persisted alongside the synthesis, for auditing.
    assert isinstance(latest["hard_gaps"], dict) and "skills" in latest["hard_gaps"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_upskill_writer_rejects_bad_severity(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db,
            iid,
            {"report_md": "x", "heatmap": [{"skill": "K8s", "severity": "URGENT", "note": "n"}]},
        )
    assert intents.get_intent(db, iid)["status"] == "running"
    assert db.latest_upskill_report() is None  # nothing written


def test_upskill_writer_rejects_empty_report(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"report_md": "  ", "heatmap": []})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_upskill_writer_rejects_heatmap_entry_without_skill(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db,
            iid,
            {"report_md": "ok", "heatmap": [{"skill": "  ", "severity": "Low", "note": "n"}]},
        )
    assert intents.get_intent(db, iid)["status"] == "running"


def test_upskill_writer_rejects_non_list_heatmap(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"report_md": "ok", "heatmap": {"not": "a list"}})
    assert intents.get_intent(db, iid)["status"] == "running"


def test_upskill_context_injects_hard_gaps_and_previous(db):
    # First report so the second run has a `previous_report` to diff against.
    iid0 = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    intents.mark_running(db, iid0)
    intents.apply_result(
        db,
        iid0,
        {
            "report_md": "# Reporte 1",
            "heatmap": [{"skill": "Kubernetes", "severity": "High", "note": "n"}],
        },
    )
    iid1 = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    ctx = intents.context_for(db, iid1)
    assert ctx["prompt_file"] == "brain/prompts/upskill.md"
    assert ctx["hard_gaps"]["jobs_considered"] == 1
    assert ctx["hard_gaps"]["skills"], "the deterministic pass feeds the brain"
    assert ctx["previous_report"]["report_md"] == "# Reporte 1"
    assert ctx["previous_report"]["heatmap"][0]["skill"] == "Kubernetes"


def test_upskill_context_previous_is_none_on_first_run(db):
    iid = intents.enqueue(db, "upskill_report", {"states": ["discovered"]})
    ctx = intents.context_for(db, iid)
    assert ctx["previous_report"] is None
