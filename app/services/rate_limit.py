"""
Lightweight in-process rate limiting and OTP attempt throttling.

No external dependency and safe on any Python version. NOTE: state lives in this
process only — with multiple workers each keeps its own counters. For horizontal
scaling back these with Redis. For a single-process MVP this is sufficient.
"""

import time
import threading
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request, HTTPException, status

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def rate_limit(max_calls: int, window_seconds: int):
    """
    FastAPI dependency factory: allow at most `max_calls` per `window_seconds`
    per client IP + path. Raises HTTP 429 when exceeded.
    """
    def _dependency(request: Request):
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        now = time.monotonic()
        cutoff = now - window_seconds
        with _lock:
            bucket = _hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_calls:
                retry = int(bucket[0] + window_seconds - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Please try again in {retry} seconds.",
                    headers={"Retry-After": str(retry)},
                )
            bucket.append(now)
    return _dependency


# ─── OTP failed-attempt throttling ───
_otp_attempts: Dict[str, int] = defaultdict(int)
OTP_MAX_ATTEMPTS = 5


def register_otp_failure(athlete_id: str) -> int:
    """Record a failed OTP attempt; returns the running count for this athlete."""
    with _lock:
        _otp_attempts[athlete_id] += 1
        return _otp_attempts[athlete_id]


def otp_attempts_exceeded(athlete_id: str) -> bool:
    with _lock:
        return _otp_attempts[athlete_id] >= OTP_MAX_ATTEMPTS


def reset_otp_attempts(athlete_id: str) -> None:
    with _lock:
        _otp_attempts.pop(athlete_id, None)


def reset_all() -> None:
    """Clear all rate-limit buckets and OTP counters. Intended for tests only."""
    with _lock:
        _hits.clear()
        _otp_attempts.clear()
