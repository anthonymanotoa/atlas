"""P2-C: per-domain pacing (deterministic — fake clock + sleep, no real waits)."""

from __future__ import annotations

from engine.discovery.rate_limiter import RateLimiter


def _rl(limits):
    clock = {"t": 0.0}
    slept: list[float] = []

    def sleep_fn(s):
        slept.append(s)
        clock["t"] += s  # advance virtual time as if we'd slept

    rl = RateLimiter(
        limits,
        time_fn=lambda: clock["t"],
        sleep_fn=sleep_fn,
        rand_fn=lambda: 0.5,  # jitter factor → exactly min_delay
    )
    return rl, slept


def test_spaces_consecutive_requests_to_same_domain():
    rl, slept = _rl({"linkedin": {"min_delay_ms": 1000}})
    assert rl.wait("https://www.linkedin.com/jobs") == 0.0  # first call: no wait
    waited = rl.wait("https://www.linkedin.com/jobs")  # immediate second: must pace
    assert 0.99 <= waited <= 1.01
    assert slept and 0.99 <= slept[0] <= 1.01


def test_unconfigured_domain_is_not_throttled():
    rl, slept = _rl({"linkedin": {"min_delay_ms": 1000}})
    assert rl.wait("https://api.greenhouse.io/v1/boards/x/jobs") == 0.0
    assert rl.wait("https://api.greenhouse.io/v1/boards/x/jobs") == 0.0
    assert slept == []
