"""Frontmatter splitting must only break on a bare `---` fence line.

Regression: `_split_frontmatter` used `body.split("---", 2)`, which split on the first
two `---` *anywhere* — so a `---` inside a YAML comment (e.g. `# --- section ---`) was
mistaken for the closing fence. The YAML was silently truncated there and every field
after it reverted to its model default (no error). This lost a profile's
`candidate_years`, `deal_breakers`, `core_keywords`, etc.
"""

from __future__ import annotations

from engine.config import Criteria, _split_frontmatter

CRITERIA_WITH_DASHES_IN_COMMENT = """\
---
roles:
  - data analyst
# --- seniority-fit realism (P4) ---
candidate_years: 5
deal_breakers:
  - unpaid
core_keywords:
  - sql
  - python
---
# Prose heading

Some markdown body for the LLM brain.
"""


def test_dashes_inside_a_comment_do_not_truncate_frontmatter():
    meta, prose = _split_frontmatter(CRITERIA_WITH_DASHES_IN_COMMENT)
    # Every field after the `# --- ... ---` comment must survive.
    assert meta["candidate_years"] == 5
    assert meta["deal_breakers"] == ["unpaid"]
    assert meta["core_keywords"] == ["sql", "python"]
    # The prose is everything after the closing fence, not the YAML tail.
    assert prose.startswith("# Prose heading")
    assert "candidate_years" not in prose


def test_truncated_fields_survive_through_to_criteria():
    meta, prose = _split_frontmatter(CRITERIA_WITH_DASHES_IN_COMMENT)
    meta["prose"] = prose
    c = Criteria(**meta)
    assert c.candidate_years == 5  # not the model default of 0
    assert c.deal_breakers == ["unpaid"]
    assert c.core_keywords == ["sql", "python"]


def test_plain_frontmatter_still_splits():
    text = "---\nroles:\n  - data analyst\n---\nbody here\n"
    meta, prose = _split_frontmatter(text)
    assert meta == {"roles": ["data analyst"]}
    assert prose == "body here"


def test_no_frontmatter_returns_empty_meta():
    text = "just some prose, no fence\n"
    meta, prose = _split_frontmatter(text)
    assert meta == {}
    assert prose == "just some prose, no fence"
