"""portfolio_research intent (Task 16): the brain researches CURRENT peer reference
portfolios for the profile's domain/target role — keeping the living portfolio reference
set fresh instead of the one-time curated seed pack going stale. Writes upsert
`peer_portfolios` keyed by `peer_portfolio_url` so re-researching the same URL updates the
row instead of duplicating it (Task 16 Part B)."""

from __future__ import annotations

import pytest

from engine import intents
from engine.db.models import DB


@pytest.fixture
def db(tmp_path):
    with DB(tmp_path / "t.db") as d:
        yield d


def test_portfolio_research_is_a_registered_intent_type():
    assert "portfolio_research" in intents.INTENT_TYPES
    assert intents.PROMPT_FILES["portfolio_research"] == "portfolio_research.md"


def test_context_includes_domain_target_role_curated_references_and_existing_peers(db):
    db.add_peer_portfolio(peer_name="Prior Peer", peer_portfolio_url="https://prior.example")
    iid = intents.enqueue(db, "portfolio_research", {})
    ctx = intents.context_for(db, iid)
    # No active profile in the test env → domain falls back to "data", which ships a real
    # committed seed pack (config/seeds/data/portfolio_references.yaml).
    assert ctx["domain"] == "data"
    assert len(ctx["curated_references"]) >= 8
    assert all("peer_name" in r and "url" in r for r in ctx["curated_references"])
    assert isinstance(ctx["patterns"], dict) and ctx["patterns"]
    assert any(p["peer_name"] == "Prior Peer" for p in ctx["existing_peers"])


def test_apply_result_upserts_portfolios_with_reviewed_at(db):
    iid = intents.enqueue(db, "portfolio_research", {})
    intents.mark_running(db, iid)
    ref = intents.apply_result(
        db,
        iid,
        {
            "portfolios": [
                {
                    "peer_name": "Jane Data",
                    "peer_portfolio_url": "https://jane.example",
                    "role_match": "Near-exact: Senior Data Scientist & AI Engineer.",
                    "key_strengths": ["Clean case-study format"],
                    "how_to_emulate": ["Open with a metrics bar"],
                    "source_url": "https://jane.example",
                }
            ]
        },
    )
    assert ref == "peer_portfolios:1"
    peers = db.list_peer_portfolios()
    jane = next(p for p in peers if p["peer_name"] == "Jane Data")
    assert jane["reviewed_at"]
    assert jane["key_strengths"] == ["Clean case-study format"]
    assert jane["how_to_emulate"] == ["Open with a metrics bar"]
    assert intents.get_intent(db, iid)["status"] == "done"


def test_reapplying_same_url_updates_instead_of_duplicating(db):
    iid1 = intents.enqueue(db, "portfolio_research", {})
    intents.mark_running(db, iid1)
    intents.apply_result(
        db,
        iid1,
        {
            "portfolios": [
                {
                    "peer_name": "Jane Data",
                    "peer_portfolio_url": "https://jane.example",
                    "role_match": "Old match text",
                    "key_strengths": ["Old strength"],
                }
            ]
        },
    )
    first_reviewed_at = next(
        p["reviewed_at"] for p in db.list_peer_portfolios() if p["peer_name"] == "Jane Data"
    )

    iid2 = intents.enqueue(db, "portfolio_research", {})
    intents.mark_running(db, iid2)
    intents.apply_result(
        db,
        iid2,
        {
            "portfolios": [
                {
                    "peer_name": "Jane Data (updated)",
                    "peer_portfolio_url": "https://jane.example",
                    "role_match": "Fresh match text",
                    "key_strengths": ["New strength"],
                    "how_to_emulate": ["New emulation tip"],
                }
            ]
        },
    )
    peers = db.list_peer_portfolios()
    matching = [p for p in peers if p["peer_portfolio_url"] == "https://jane.example"]
    assert len(matching) == 1  # updated, not duplicated
    updated = matching[0]
    assert updated["peer_name"] == "Jane Data (updated)"
    assert updated["role_match"] == "Fresh match text"
    assert updated["key_strengths"] == ["New strength"]
    assert updated["how_to_emulate"] == ["New emulation tip"]
    assert updated["reviewed_at"] >= first_reviewed_at


def test_apply_result_missing_peer_name_raises_and_stays_running(db):
    iid = intents.enqueue(db, "portfolio_research", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(
            db, iid, {"portfolios": [{"peer_portfolio_url": "https://x.example"}]}
        )
    assert intents.get_intent(db, iid)["status"] == "running"
    assert db.list_peer_portfolios() == []


def test_apply_result_missing_portfolio_url_raises_and_stays_running(db):
    iid = intents.enqueue(db, "portfolio_research", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"portfolios": [{"peer_name": "No URL Guy"}]})
    assert intents.get_intent(db, iid)["status"] == "running"
    assert db.list_peer_portfolios() == []


def test_apply_result_empty_portfolios_list_raises(db):
    iid = intents.enqueue(db, "portfolio_research", {})
    intents.mark_running(db, iid)
    with pytest.raises(ValueError):
        intents.apply_result(db, iid, {"portfolios": []})
    assert intents.get_intent(db, iid)["status"] == "running"


# ── DB.upsert_peer_portfolio (Task 16 Part B) ───────────────────────────────────
def test_db_upsert_peer_portfolio_inserts_new_row(db):
    pid = db.upsert_peer_portfolio(
        peer_name="New Peer", peer_portfolio_url="https://new.example"
    )
    row = next(p for p in db.list_peer_portfolios() if p["id"] == pid)
    assert row["peer_name"] == "New Peer"
    assert row["reviewed_at"]


def test_db_upsert_peer_portfolio_updates_existing_row_by_url(db):
    pid1 = db.upsert_peer_portfolio(
        peer_name="Old Name", peer_portfolio_url="https://same.example", role_match="Old"
    )
    pid2 = db.upsert_peer_portfolio(
        peer_name="New Name", peer_portfolio_url="https://same.example", role_match="New"
    )
    assert pid1 == pid2
    rows = [p for p in db.list_peer_portfolios() if p["peer_portfolio_url"] == "https://same.example"]
    assert len(rows) == 1
    assert rows[0]["peer_name"] == "New Name"
    assert rows[0]["role_match"] == "New"


def test_db_last_peer_review_returns_none_when_empty(db):
    assert db.last_peer_review() is None


def test_db_last_peer_review_returns_max_reviewed_at(db):
    db.add_peer_portfolio(peer_name="A", peer_portfolio_url="https://a.example")
    db.add_peer_portfolio(peer_name="B", peer_portfolio_url="https://b.example")
    latest = db.last_peer_review()
    assert latest is not None
    assert latest == max(p["reviewed_at"] for p in db.list_peer_portfolios())


# ── CLI: `atlas portfolio research` (Task 16/17 Part C) ─────────────────────────
@pytest.fixture
def cli_db(tmp_path, monkeypatch):
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


def test_cli_portfolio_research_default_shows_curated_and_peers(cli_db):
    cli_db.add_peer_portfolio(peer_name="Discovered Peer", peer_portfolio_url="https://d.example")
    res = _run(["portfolio", "research"])
    assert res.exit_code == 0, res.output
    assert "Discovered Peer" in res.output


def test_cli_portfolio_research_enqueue_creates_pending_intent(cli_db):
    res = _run(["portfolio", "research", "--enqueue"])
    assert res.exit_code == 0, res.output
    rows = intents.list_intents(cli_db, status="pending")
    assert [r["type"] for r in rows] == ["portfolio_research"]
