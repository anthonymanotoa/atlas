"""Shared HTTP client for ATS feeds + free APIs.

Polite by default: browser-ish UA, generous timeout, follows redirects, and a short
bounded backoff on 429 (these public endpoints rarely rate-limit, but we respect it).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from engine.discovery.rate_limiter import RateLimiter

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Lazily-built, process-wide pacer. Config from sources.yaml `rate_limits` (per-domain
# min_delay_ms). Keeps us account/IP-safe on the httpx path; see rate_limiter.py.
_LIMITER: RateLimiter | None = None


def _limiter() -> RateLimiter:
    global _LIMITER
    if _LIMITER is None:
        try:
            from engine.config import load_sources

            limits = load_sources().get("rate_limits") or {}
        except Exception:  # noqa: BLE001 — pacing is best-effort; never block discovery on config
            limits = {}
        _LIMITER = RateLimiter(limits)
    return _LIMITER


def make_client(timeout: float = 45.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": _UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        },
    )


def get_json(client: httpx.Client, url: str, params: dict | None = None, retries: int = 2) -> Any:
    """GET a URL and parse JSON, backing off briefly on 429. Raises on other HTTP errors."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            _limiter().wait(url)
            r = client.get(url, params=params)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2**attempt * 3))
                time.sleep(min(wait, 20))
                last = httpx.HTTPStatusError("429", request=r.request, response=r)
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise
    if last:
        raise last


def post_json(client: httpx.Client, url: str, json: dict | None = None, retries: int = 2) -> Any:
    """POST a JSON body and parse the JSON response — same 429 backoff as get_json.

    Workday's CXS jobs endpoint is a POST (paginated body), so it needs this sibling
    of get_json rather than a one-off raw client.post that would bypass the backoff.
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            _limiter().wait(url)
            r = client.post(url, json=json)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2**attempt * 3))
                time.sleep(min(wait, 20))
                last = httpx.HTTPStatusError("429", request=r.request, response=r)
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise
    if last:
        raise last
