from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from alfred.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitPolicy:
    max_per_minute: int
    min_interval_s: float


DEFAULT_POLICIES: dict[str, RateLimitPolicy] = {
    # DuckDuckGo (unofficial): be conservative.
    "ddg": RateLimitPolicy(max_per_minute=15, min_interval_s=2.0),
    # Brave: paid API, but still avoid bursts (and pagination multiplies calls).
    "brave": RateLimitPolicy(max_per_minute=60, min_interval_s=1.0),
    # Tavily / Exa / You / Langsearch: conservative defaults.
    "tavily": RateLimitPolicy(max_per_minute=60, min_interval_s=1.0),
    "exa": RateLimitPolicy(max_per_minute=60, min_interval_s=1.0),
    "you": RateLimitPolicy(max_per_minute=30, min_interval_s=1.0),
    "langsearch": RateLimitPolicy(max_per_minute=60, min_interval_s=1.0),
    # Self-hosted SearxNG typically can handle more; keep a mild throttle.
    "searx": RateLimitPolicy(max_per_minute=120, min_interval_s=0.25),
    # Public sites that may gate content; keep conservative.
    "blind": RateLimitPolicy(max_per_minute=30, min_interval_s=1.0),
    "levels": RateLimitPolicy(max_per_minute=60, min_interval_s=0.5),
    # Paid OpenWeb Ninja Glassdoor API: avoid bursts.
    "glassdoor": RateLimitPolicy(max_per_minute=120, min_interval_s=0.25),
}


class WebRateLimiter:
    """Best-effort, respectful rate limiter for outbound web/search requests.

    Uses Redis when available to coordinate across processes (Celery prefork, API workers).
    Falls back to in-process limits when Redis isn't usable.
    """

    def __init__(self, *, prefix: str = "alfred:rate") -> None:
        self._prefix = prefix
        self._lock = Lock()
        self._next_allowed: dict[str, float] = {}
        self._minute_key: dict[str, int] = {}
        self._minute_count: dict[str, int] = {}

    def policy_for(self, provider: str) -> RateLimitPolicy:
        return DEFAULT_POLICIES.get(
            provider, RateLimitPolicy(max_per_minute=60, min_interval_s=1.0)
        )

    def wait(self, provider: str, *, policy: RateLimitPolicy | None = None) -> None:
        policy = policy or self.policy_for(provider)
        provider = (provider or "unknown").strip().lower()

        redis_client = get_redis_client()
        if redis_client is not None:
            try:
                self._wait_redis(redis_client, provider, policy)
                return
            except Exception as exc:
                logger.debug("Redis rate limiter unavailable (%s); falling back to local", exc)

        self._wait_local(provider, policy)

    def _wait_local(self, provider: str, policy: RateLimitPolicy) -> None:
        now = time.monotonic()
        with self._lock:
            minute = int(time.time() // 60)
            if self._minute_key.get(provider) != minute:
                self._minute_key[provider] = minute
                self._minute_count[provider] = 0

            next_allowed = self._next_allowed.get(provider, 0.0)
            if now < next_allowed:
                sleep_for = next_allowed - now
            else:
                sleep_for = 0.0

        if sleep_for > 0:
            time.sleep(sleep_for)

        with self._lock:
            self._minute_count[provider] = self._minute_count.get(provider, 0) + 1
            if self._minute_count[provider] > policy.max_per_minute:
                # Wait until next minute boundary.
                wait_for = 60.0 - (time.time() % 60.0) + random.uniform(0.05, 0.25)
                time.sleep(wait_for)
                self._minute_key[provider] = int(time.time() // 60)
                self._minute_count[provider] = 1

            self._next_allowed[provider] = time.monotonic() + policy.min_interval_s

    def _wait_redis(self, redis_client: Any, provider: str, policy: RateLimitPolicy) -> None:
        interval_key = f"{self._prefix}:interval:{provider}"
        minute_bucket = int(time.time() // 60)
        count_key = f"{self._prefix}:count:{provider}:{minute_bucket}"

        # 1) Enforce minimum spacing between requests globally (across processes).
        if policy.min_interval_s > 0:
            interval_ms = int(policy.min_interval_s * 1000)
            while True:
                ok = redis_client.set(interval_key, "1", nx=True, px=interval_ms)
                if ok:
                    break
                try:
                    wait_ms = redis_client.pttl(interval_key)
                except Exception:
                    wait_ms = interval_ms
                sleep_for = max(0.05, float(wait_ms) / 1000.0) + random.uniform(0.0, 0.05)
                time.sleep(sleep_for)

        # 2) Enforce max requests per minute globally.
        while True:
            count = int(redis_client.incr(count_key))
            if count == 1:
                redis_client.expire(count_key, 120)
            if count <= policy.max_per_minute:
                return

            # Exceeded: wait for the minute bucket to roll over.
            wait_for = 60.0 - (time.time() % 60.0) + random.uniform(0.05, 0.25)
            time.sleep(wait_for)
            minute_bucket = int(time.time() // 60)
            count_key = f"{self._prefix}:count:{provider}:{minute_bucket}"


web_rate_limiter = WebRateLimiter()
