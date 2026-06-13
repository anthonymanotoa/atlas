"""Per-domain request pacing — "slower is fine, never get my IP banned".

Enforces a minimum spacing (with ±20% jitter) between requests to the same domain on
the httpx discovery path (ATS feeds + free APIs through ``http.get_json``/``post_json``).
Config lives in ``sources.yaml`` under ``rate_limits`` (per-domain ``min_delay_ms``).

IMPORTANT: this does NOT govern the logged-in LinkedIn browsing done via
Claude-in-Chrome (the account/IP-ban risk for social search + interviewer/peer
research). That path is paced by the supervised skill's human-speed guardrails —
see ``docs/RATE_LIMITING.md``.
"""

from __future__ import annotations

import random
import time
from urllib.parse import urlsplit


class RateLimiter:
    def __init__(
        self,
        limits: dict[str, dict] | None = None,
        *,
        default_min_delay_ms: float = 0,
        time_fn=time.monotonic,
        sleep_fn=time.sleep,
        rand_fn=random.random,
    ) -> None:
        self._limits = limits or {}
        self._default_min = default_min_delay_ms
        self._last: dict[str, float] = {}
        self._time, self._sleep, self._rand = time_fn, sleep_fn, rand_fn

    def _min_delay_ms(self, domain: str) -> float:
        # config keys are substrings ("linkedin", "indeed") matched against the netloc
        for key, cfg in self._limits.items():
            if key in domain:
                return float((cfg or {}).get("min_delay_ms", self._default_min))
        return float(self._default_min)

    def wait(self, url: str) -> float:
        """Sleep just long enough to honor the domain's min spacing. Returns seconds slept."""
        domain = (urlsplit(url).netloc or url).lower()
        min_delay = self._min_delay_ms(domain) / 1000.0
        waited = 0.0
        if min_delay > 0:
            last = self._last.get(domain)
            if last is not None:
                target = min_delay * (0.8 + 0.4 * self._rand())  # ±20% jitter
                elapsed = self._time() - last
                if elapsed < target:
                    waited = target - elapsed
                    self._sleep(waited)
        self._last[domain] = self._time()
        return waited
