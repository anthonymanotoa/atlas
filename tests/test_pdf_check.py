"""engine/cv/pdf_check.py — conteo de páginas determinista para la verificación visual (F4)."""

from __future__ import annotations

from engine.cv.pdf_check import check_page_count, page_count


def _one_page_pdf(path):
    # PDF mínimo válido de UNA página (suficiente para probar el contador determinista).
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
        b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    return path


def test_page_count_missing_file_is_zero():
    assert page_count("/does/not/exist.pdf") == 0


def test_page_count_single_page(tmp_path):
    pdf = _one_page_pdf(tmp_path / "cv.pdf")
    assert page_count(pdf) == 1


def test_check_page_count_ok_within_limit(tmp_path):
    pdf = _one_page_pdf(tmp_path / "cv.pdf")
    out = check_page_count(pdf, max_pages=2)
    assert out["ok"] is True and out["pages"] == 1 and out["max_pages"] == 2


def test_check_page_count_fails_over_limit(tmp_path, monkeypatch):
    pdf = _one_page_pdf(tmp_path / "cv.pdf")
    # forzamos un conteo de 3 páginas para probar la rama de fallo sin construir un PDF grande
    monkeypatch.setattr("engine.cv.pdf_check.page_count", lambda p: 3)
    out = check_page_count(pdf, max_pages=2)
    assert out["ok"] is False and out["pages"] == 3
    assert "3" in out["reason"] and "2" in out["reason"]


# ── real reportlab-rendered PDFs (exercise the pdfplumber primary path end-to-end) ──


def test_page_count_real_short_cv_is_one_page(tmp_path):
    """A short CV rendered by the real engine.cv.render pipeline is exactly one page,
    counted by pdfplumber (the declared dependency), not the byte-scan fallback."""
    from engine.cv.render import render_pdf

    cv = {"basics": {"name": "Jane Doe", "summary": "One-line summary."}, "skills": ["Python"]}
    pdf = render_pdf(cv, tmp_path / "short.pdf")
    assert pdf is not None
    assert page_count(pdf) == 1
    assert check_page_count(pdf, max_pages=2)["ok"] is True


def test_check_page_count_real_long_cv_over_limit(tmp_path):
    """A CV long enough to spill past two pages fails the deterministic gate on a REAL PDF —
    no monkeypatching: this is the actual multi-page count the brain will act on."""
    from engine.cv.render import render_pdf

    cv = {
        "basics": {"name": "Jane Doe", "summary": "x " * 400},
        "experience": [
            {
                "title": f"Role {i}",
                "company": f"Co {i}",
                "highlights": ["A long highlight sentence about measurable impact. " * 4] * 8,
            }
            for i in range(12)
        ],
    }
    pdf = render_pdf(cv, tmp_path / "long.pdf")
    assert pdf is not None
    out = check_page_count(pdf, max_pages=2)
    assert out["pages"] > 2
    assert out["ok"] is False
    assert str(out["pages"]) in out["reason"] and "2" in out["reason"]
