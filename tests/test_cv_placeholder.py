from engine.cv.placeholder import find_placeholders, is_template_cv


def test_template_cv_is_flagged():
    cv = {
        "basics": {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "linkedin": "linkedin.com/in/example",
        }
    }
    findings = find_placeholders(cv)
    assert any("Ada Lovelace" in f for f in findings)
    assert any("example.com" in f for f in findings)
    assert is_template_cv(cv) is True


def test_real_cv_passes():
    cv = {
        "basics": {
            "name": "Jane Roe",
            "email": "jane@gmail.com",
            "linkedin": "linkedin.com/in/janeroe",
        }
    }
    assert find_placeholders(cv) == []
    assert is_template_cv(cv) is False


def test_empty_or_missing_basics_is_flagged():
    assert is_template_cv({}) is True
