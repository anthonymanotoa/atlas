"""Shared HTTP client for ATS feeds + free APIs.

Polite by default: browser-ish UA, generous timeout, follows redirects, and a short
bounded backoff on 429 (these public endpoints rarely rate-limit, but we respect it).
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


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


def get_json(client: httpx.Client, url: str, params: Optional[dict] = None,
             retries: int = 2) -> Any:
    """GET a URL and parse JSON, backing off briefly on 429. Raises on other HTTP errors."""
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            r = client.get(url, params=params)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2 ** attempt * 3))
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


def post_json(client: httpx.Client, url: str, json: Optional[dict] = None,
              retries: int = 2) -> Any:
    """POST a JSON body and parse the JSON response — same 429 backoff as get_json.

    Workday's CXS jobs endpoint is a POST (paginated body), so it needs this sibling
    of get_json rather than a one-off raw client.post that would bypass the backoff.
    """
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            r = client.post(url, json=json)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2 ** attempt * 3))
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
