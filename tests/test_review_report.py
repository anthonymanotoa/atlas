"""engine/cv/review_report.py — deterministic per-CV review report (review.md)."""

from __future__ import annotations

import yaml

from engine.cv.render import render_docx, render_pdf
from engine.cv.review_report import build_review, check_no_fabricated_companies, companies_in_text
from engine.db.models import DB
from engine.normalize import Job

MASTER = {
    "basics": {
        "name": "Jane Roe",
        "label": "Senior Backend Engineer",
        "email": "jane.roe@gmail.com",
        "summary": (
            "Senior backend engineer with eight years building distributed systems and "
            "leading small teams to ship reliable, observable services at scale for "
            "enterprise customers across multiple regions and time zones."
        ),
    },
    "skills": ["Python", "AWS", "Kubernetes", "PostgreSQL"],
    "experience": [
        {
            "title": "Senior Backend Engineer",
            "company": "Acme Inc",
            "start": "Jan 2020",
            "end": "Present",
            "highlights": [
                "Led the migration of the core platform to Kubernetes, cutting infra costs "
                "by 30 percent while improving deploy frequency for the whole engineering org.",
                "Built distributed data pipelines processing millions of events daily with "
                "strict reliability and latency budgets for downstream analytics teams.",
            ],
        },
        {
            "title": "Backend Engineer",
            "company": "Globex Corp",
            "start": "Jun 2016",
            "end": "Dec 2019",
            "highlights": [
                "Designed and shipped the payments service powering checkout for the "
                "company's flagship product, handling millions of dollars in daily volume.",
            ],
        },
    ],
}

JOB = {"title": "Senior Backend Engineer", "company": "Acme Inc"}
COVERAGE = {"coverage": 0.8, "matched": ["python", "aws"], "missing": []}


def _render(tmp_path, master=MASTER):
    docx_path = render_docx(master, tmp_path / "cv.docx", language="en")
    pdf_path = render_pdf(master, tmp_path / "cv.pdf", language="en")
    return docx_path, pdf_path


# ── happy path ─────────────────────────────────────────────────────────────


def test_happy_path_passes_all_hard_checks(tmp_path):
    docx_path, pdf_path = _render(tmp_path)
    result = build_review(docx_path, pdf_path, MASTER, JOB, COVERAGE)

    assert result.passed is True
    by_name = {c.name: c for c in result.checks}
    assert by_name["Texto extraíble"].ok is True
    assert by_name["Bloque de contacto"].ok is True
    assert by_name["Sin placeholders"].ok is True
    assert by_name["Anti-fabricación (empresas)"].ok is True
    assert by_name["Páginas"].ok is True


def test_markdown_has_one_line_per_check(tmp_path):
    docx_path, pdf_path = _render(tmp_path)
    result = build_review(docx_path, pdf_path, MASTER, JOB, COVERAGE)

    check_lines = [ln for ln in result.markdown.splitlines() if ln.startswith("- ")]
    assert len(check_lines) == len(result.checks)
    for check in result.checks:
        assert any(check.name in ln for ln in check_lines)


def test_low_coverage_is_advisory_not_a_hard_fail(tmp_path):
    docx_path, pdf_path = _render(tmp_path)
    low_coverage = {"coverage": 0.1, "matched": [], "missing": ["docker", "terraform"]}
    result = build_review(docx_path, pdf_path, MASTER, JOB, low_coverage)

    by_name = {c.name: c for c in result.checks}
    assert by_name["Cobertura de keywords"].ok is False
    assert "docker" in by_name["Cobertura de keywords"].detail
    # advisory-only: a low coverage check must NOT drag the overall verdict down
    assert result.passed is True


def test_missing_master_email_fails_contact_check(tmp_path):
    master_no_email = {**MASTER, "basics": {**MASTER["basics"], "email": ""}}
    docx_path, pdf_path = _render(tmp_path, master=master_no_email)
    result = build_review(docx_path, pdf_path, master_no_email, JOB, COVERAGE)

    by_name = {c.name: c for c in result.checks}
    assert by_name["Bloque de contacto"].ok is False
    assert result.passed is False


# ── anti-fabrication helper (unit-tested directly, no render needed) ───────


def test_companies_in_text_extracts_experience_header_companies():
    text = (
        "Jane Roe\n"
        "jane.roe@gmail.com\n"
        "EXPERIENCE\n"
        "Senior Backend Engineer — Acme Inc\n"
        "Remote  |  Jan 2020 – Present\n"
        "Led the migration of the platform.\n"
        "EDUCATION\n"
        "BSc Computer Science — Somewhere University\n"
    )
    companies = companies_in_text(text)
    assert companies == ["Acme Inc"]  # the Education line is out of the Experience block


def test_check_no_fabricated_companies_passes_when_all_in_master():
    master = {"experience": [{"company": "Acme Inc"}, {"company": "Globex Corp"}]}
    text = "EXPERIENCE\nSenior Engineer — Acme Inc\nStaff Engineer — Globex Corp\n"
    ok, foreign = check_no_fabricated_companies(text, master)
    assert ok is True
    assert foreign == []


def test_check_no_fabricated_companies_flags_foreign_company():
    master = {"experience": [{"company": "Acme Inc"}]}
    text = "EXPERIENCE\nSenior Engineer — Umbrella Corp\nDid things well for the team.\n"
    ok, foreign = check_no_fabricated_companies(text, master)
    assert ok is False
    assert foreign == ["Umbrella Corp"]


def test_build_review_fails_when_docx_lists_a_fabricated_company(tmp_path):
    # End-to-end: render a real DOCX whose experience includes "Umbrella Corp", but review it
    # against a master_cv that never mentions that employer — a regression that let an override
    # introduce a foreign employer must surface as an overall passed=False, not just a helper.
    rendered_master = {
        **MASTER,
        "experience": [
            MASTER["experience"][0],
            {**MASTER["experience"][1], "company": "Umbrella Corp"},
        ],
    }
    docx_path, pdf_path = _render(tmp_path, master=rendered_master)
    trusted_master = {**MASTER, "experience": [MASTER["experience"][0]]}  # no Umbrella Corp

    result = build_review(docx_path, pdf_path, trusted_master, JOB, COVERAGE)

    by_name = {c.name: c for c in result.checks}
    assert by_name["Anti-fabricación (empresas)"].ok is False
    assert "Umbrella Corp" in by_name["Anti-fabricación (empresas)"].detail
    assert result.passed is False


# ── integration: same wiring as `atlas tailor` / `atlas prep` (engine/cli.py) ──────────────


def test_review_md_lands_next_to_docx_and_pdf_like_the_cli_does(tmp_path, monkeypatch):
    """Mirrors what `tailor`/`prep` do after build_for_job: call build_review and write
    review.md into the job's outbox dir, alongside the DOCX/PDF build_for_job already put
    there — without going through the full Typer CLI (which needs a real profile config)."""
    import engine.paths as paths
    from engine.cv.build import build_for_job

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    master_path = tmp_path / "master_cv.yaml"
    master_path.write_text(yaml.safe_dump(MASTER, allow_unicode=True))
    monkeypatch.setattr(paths, "MASTER_CV_PATH", master_path)

    with DB(tmp_path / "t.db") as db:
        db.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="Senior Backend Engineer",
                company="Acme Inc",
                url="https://x/1",
                description="Python, AWS and Kubernetes experience needed.",
            )
        )
        job_id = db.list_jobs()[0]["id"]
        res = build_for_job(db, job_id, language="en")
        job = db.get_job(job_id) or {}

    coverage = {"coverage": res.coverage, "matched": res.matched, "missing": res.missing}
    result = build_review(res.docx_path, res.pdf_path, MASTER, job, coverage)
    review_path = res.docx_path.parent / "review.md"
    review_path.write_text(result.markdown)

    assert review_path.exists()
    assert review_path.parent == res.docx_path.parent == res.pdf_path.parent
    assert "Texto extraíble" in review_path.read_text()


def test_write_package_writes_review_md_too(tmp_path, monkeypatch):
    """Regression: write_package() (called by the web route POST /api/jobs/{id}/prep and the
    daily brain in brain/run_brain.py — the DOMINANT prep paths, not `atlas tailor`/`prep`)
    used to never write review.md, since build_review only lived in engine/cli.py. Both those
    call sites go through write_package, so review.md must land there too."""
    import engine.paths as paths
    from engine.cv.build import build_for_job
    from engine.outreach.build import write_package

    monkeypatch.setattr(paths, "OUTBOX_DIR", tmp_path / "outbox")
    master_path = tmp_path / "master_cv.yaml"
    master_path.write_text(yaml.safe_dump(MASTER, allow_unicode=True))
    monkeypatch.setattr(paths, "MASTER_CV_PATH", master_path)

    with DB(tmp_path / "t.db") as db:
        db.upsert_job(
            Job(
                source="greenhouse",
                source_job_id="1",
                title="Senior Backend Engineer",
                company="Acme Inc",
                url="https://x/1",
                description="Python, AWS and Kubernetes experience needed.",
            )
        )
        job_id = db.list_jobs()[0]["id"]
        build_for_job(db, job_id, language="en")
        pkg_path = write_package(db, job_id, language="en")

    review_path = pkg_path.parent / "review.md"
    assert review_path.exists()
    assert "Texto extraíble" in review_path.read_text()
