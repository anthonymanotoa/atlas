"""Liveness gate (spec §5.3): deterministic HTTP checks; ambiguity NEVER expires a job."""

from __future__ import annotations

import httpx

from engine.db.models import DB
from engine.discovery.liveness import check_url, sweep_liveness
from engine.normalize import STATES, Job


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_expired_is_a_valid_state():
    assert "expired" in STATES


def test_404_and_410_are_dead():
    with _client(lambda req: httpx.Response(404)) as c:
        assert check_url(c, "https://x.co/jobs/1") == ("dead", "http 404")
    with _client(lambda req: httpx.Response(410)) as c:
        assert check_url(c, "https://x.co/jobs/1") == ("dead", "http 410")


def test_tombstone_phrases_multilanguage():
    for phrase in (
        "This position has been filled.",
        "Sorry, this job is no longer available.",
        "Esta oferta ya no está disponible.",
        "Cette offre n'est plus disponible.",
    ):
        with _client(lambda req, p=phrase: httpx.Response(200, text=f"<html>{p}</html>")) as c:
            verdict, reason = check_url(c, "https://x.co/jobs/1")
        assert verdict == "dead", phrase
        assert "tombstone" in reason


def test_redirect_to_careers_root_is_dead():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/jobs/123":
            return httpx.Response(302, headers={"location": "https://x.co/careers"})
        return httpx.Response(200, text="<html>Open roles at X</html>")

    with _client(handler) as c:
        verdict, reason = check_url(c, "https://x.co/jobs/123")
    assert verdict == "dead" and "careers root" in reason


def test_alive_and_ambiguous_cases():
    with _client(lambda req: httpx.Response(200, text="<html>Apply now! Great role.</html>")) as c:
        assert check_url(c, "https://x.co/jobs/1")[0] == "alive"
    with _client(lambda req: httpx.Response(500)) as c:
        assert check_url(c, "https://x.co/jobs/1")[0] == "unknown"

    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    with _client(boom) as c:
        assert check_url(c, "https://x.co/jobs/1")[0] == "unknown"


def test_sweep_expires_dead_keeps_alive_and_stamps_checked_at(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        if "dead" in str(req.url):
            return httpx.Response(404)
        return httpx.Response(200, text="Apply now")

    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(source="lever", title="DE A", company="Acme", url="https://x.co/jobs/dead")
        )
        db.upsert_job(
            Job(source="lever", title="DE B", company="Beta", url="https://x.co/jobs/alive")
        )
        with _client(handler) as c:
            out = sweep_liveness(db, limit=10, client=c, delay_s=0)
        rows = {r["title"]: r for r in db.list_jobs(states=list(STATES))}
    assert out == {"checked": 2, "expired": 1, "unknown": 0}
    assert rows["DE A"]["state"] == "expired"
    assert rows["DE B"]["state"] == "discovered"
    assert rows["DE A"]["liveness_checked_at"] and rows["DE B"]["liveness_checked_at"]
