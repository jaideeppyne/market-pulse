"""Lightweight, dependency-free security primitives for public deployment.

This module backs the hardening applied in ``app/main.py``. It provides:
  * an in-process per-client-IP rate limiter (fixed-window, no external deps),
  * a CORS configuration helper (locked down by default),
  * a small error-message sanitizer so internal exception text / file paths
    are never leaked to API clients.

------------------------------------------------------------------------------
DEPLOY SECURITY POSTURE — env vars to set for a PUBLIC instance
------------------------------------------------------------------------------
Market Pulse is meant to be deployed publicly (Oracle / Railway / Render).
When exposed to the internet you SHOULD set the following:

  Writes (already enforced by _assert_write_allowed in app/main.py):
    MARKET_PULSE_WRITE_KEY=<random-secret>
        Required on the X-API-Key header for any mutating request from a
        non-local client. Set this. Do NOT set MARKET_PULSE_ALLOW_UNAUTH_WRITES.
    MARKET_PULSE_ALLOW_UNAUTH_WRITES=1
        Escape hatch only — allows unauthenticated writes. Avoid in production.

  CORS (browser origin allow-list):
    MARKET_PULSE_CORS_ORIGINS=https://yourapp.example.com,https://www.example.com
        Comma-separated exact origins permitted to call the API from a browser.
        Default is "no cross-origin browser access" (same-origin only), which is
        correct when the SPA is served by this same FastAPI app. Never use "*"
        together with credentials.
    MARKET_PULSE_CORS_ALLOW_CREDENTIALS=1
        Only enable if you actually use cookie/credentialed CORS AND have set an
        explicit origin list above (never combined with "*").

  Rate limiting (per-client-IP, applied to expensive endpoints):
    MARKET_PULSE_RATE_LIMIT_DISCOVER        (default 5 / 60s)
    MARKET_PULSE_RATE_LIMIT_FULL_SCAN       (default 2 / 300s)
    MARKET_PULSE_RATE_LIMIT_ANALYZE         (default 20 / 60s)
    MARKET_PULSE_RATE_LIMIT_EDGE            (default 10 / 60s)
        Each accepts either "<count>" or "<count>/<window_seconds>".
    MARKET_PULSE_RATE_LIMIT_EXEMPT_LOCAL=0
        Set to 0 to also rate-limit localhost (default 1 = local exempt).

  Networking:
    Run behind the platform's TLS terminator; uvicorn is started with
    proxy_headers=True so X-Forwarded-For is honored for client IP.

Notes / residual risks:
  * The rate limiter is in-process: limits are per worker. With multiple
    workers/replicas the effective limit multiplies. For a single free-tier
    instance (the intended target) this is fine; for horizontal scaling put a
    shared limiter (e.g. Redis) or a gateway in front.
  * State is an unbounded-ish dict keyed by client IP; we prune expired windows
    on access and cap the table size to avoid memory growth from IP churn.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Iterable

# --------------------------------------------------------------------------- #
# Error sanitization
# --------------------------------------------------------------------------- #

def safe_error_detail(prefix: str, exc: BaseException | None = None) -> str:
    """Return a client-safe error string that never leaks internals.

    We deliberately do NOT include the exception's str()/repr() (which can carry
    file paths, SQL, stack context, or third-party library internals). The full
    error is expected to be logged server-side by the caller.
    """
    cls = type(exc).__name__ if exc is not None else ""
    if cls:
        return f"{prefix} ({cls})"
    return prefix


# --------------------------------------------------------------------------- #
# CORS configuration
# --------------------------------------------------------------------------- #

_CORS_ORIGINS_ENV = "MARKET_PULSE_CORS_ORIGINS"
_CORS_CREDENTIALS_ENV = "MARKET_PULSE_CORS_ALLOW_CREDENTIALS"


def cors_settings() -> dict:
    """Resolve CORS settings from env, locked down by default.

    Returns a dict suitable for ``CORSMiddleware(**settings)``-style use.
    Default: empty origin allow-list (same-origin only). We never combine the
    "*" wildcard with credentials (that is rejected by browsers and unsafe).
    """
    raw = (os.getenv(_CORS_ORIGINS_ENV) or "").strip()
    origins = [o.strip() for o in raw.split(",") if o.strip()] if raw else []

    allow_credentials = os.getenv(_CORS_CREDENTIALS_ENV) == "1"
    wildcard = origins == ["*"]
    if wildcard and allow_credentials:
        # Unsafe + browser-rejected combo. Drop credentials, keep wildcard.
        allow_credentials = False

    return {
        "allow_origins": origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["X-API-Key", "Content-Type"],
    }


# --------------------------------------------------------------------------- #
# Rate limiting (fixed-window, per client IP, in-process)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RateLimit:
    """A fixed-window limit: at most ``count`` requests per ``window`` seconds."""

    count: int
    window: float


def _parse_limit(env_name: str, default_count: int, default_window: float) -> RateLimit:
    """Parse "<count>" or "<count>/<window_seconds>" from an env var."""
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return RateLimit(default_count, default_window)
    try:
        if "/" in raw:
            c_str, w_str = raw.split("/", 1)
            count = int(c_str)
            window = float(w_str)
        else:
            count = int(raw)
            window = default_window
        if count <= 0 or window <= 0:
            raise ValueError
        return RateLimit(count, window)
    except (ValueError, TypeError):
        return RateLimit(default_count, default_window)


# Default limits chosen to protect yfinance / CPU on a free-tier instance while
# staying generous enough for a real interactive user.
DEFAULT_LIMITS: dict[str, RateLimit] = {
    "discover": _parse_limit("MARKET_PULSE_RATE_LIMIT_DISCOVER", 5, 60.0),
    "full_scan": _parse_limit("MARKET_PULSE_RATE_LIMIT_FULL_SCAN", 2, 300.0),
    "analyze": _parse_limit("MARKET_PULSE_RATE_LIMIT_ANALYZE", 20, 60.0),
    "edge": _parse_limit("MARKET_PULSE_RATE_LIMIT_EDGE", 10, 60.0),
}

_EXEMPT_LOCAL = os.getenv("MARKET_PULSE_RATE_LIMIT_EXEMPT_LOCAL", "1") != "0"

# Cap on number of (bucket, ip) windows we track, to bound memory under IP churn.
_MAX_TRACKED_KEYS = 50_000


class RateLimiter:
    """Thread-safe fixed-window rate limiter keyed by (bucket, client-ip).

    Endpoints are served by FastAPI's threadpool / event loop; the limiter uses
    a plain lock so it is safe regardless of how the handler is scheduled.
    """

    def __init__(self, limits: dict[str, RateLimit] | None = None):
        self._limits = dict(limits or DEFAULT_LIMITS)
        self._lock = threading.Lock()
        # key -> (window_start_epoch, count_in_window)
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}

    def limit_for(self, bucket: str) -> RateLimit | None:
        return self._limits.get(bucket)

    def _prune_locked(self, now: float) -> None:
        if len(self._windows) <= _MAX_TRACKED_KEYS:
            return
        # Drop any windows whose period has fully elapsed; if still too big,
        # clear entirely (cheap, correct — worst case briefly resets counters).
        stale = [
            k
            for k, (start, _c) in self._windows.items()
            if now - start >= self._limits.get(k[0], RateLimit(1, 60.0)).window
        ]
        for k in stale:
            self._windows.pop(k, None)
        if len(self._windows) > _MAX_TRACKED_KEYS:
            self._windows.clear()

    def check(self, bucket: str, client_ip: str) -> tuple[bool, float]:
        """Record a request and report whether it is allowed.

        Returns ``(allowed, retry_after_seconds)``. When allowed,
        ``retry_after_seconds`` is 0.0.
        """
        limit = self._limits.get(bucket)
        if limit is None:
            return True, 0.0

        now = time.monotonic()
        key = (bucket, client_ip or "unknown")
        with self._lock:
            self._prune_locked(now)
            start, count = self._windows.get(key, (now, 0))
            if now - start >= limit.window:
                # Window expired — start a fresh one.
                start, count = now, 0
            if count >= limit.count:
                retry_after = max(0.0, limit.window - (now - start))
                return False, retry_after
            self._windows[key] = (start, count + 1)
            return True, 0.0


def client_ip_from_scope(host: str | None, forwarded_for: str | None) -> str:
    """Best-effort client IP. Honors X-Forwarded-For (left-most) behind a proxy.

    uvicorn is started with proxy_headers=True, but X-Forwarded-For may carry a
    list; we take the first (original client) entry.
    """
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return host or "unknown"


def is_local_exempt() -> bool:
    return _EXEMPT_LOCAL


# Module-level singleton used by app.main.
limiter = RateLimiter()


__all__ = [
    "RateLimit",
    "RateLimiter",
    "limiter",
    "cors_settings",
    "safe_error_detail",
    "client_ip_from_scope",
    "is_local_exempt",
    "DEFAULT_LIMITS",
]
