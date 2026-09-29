from __future__ import annotations

import hashlib
import hmac
import os
import time


def webhook_secret_value(reference: str | None) -> str | None:
    if not reference:
        return None
    return os.getenv(f"THRESHOLD_WEBHOOK_SECRET__{reference.upper()}")


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(
    *,
    secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
    allowed_clock_skew_seconds: int = 300,
    now: int | None = None,
) -> bool:
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = int(time.time()) if now is None else int(now)
    if abs(current - sent_at) > allowed_clock_skew_seconds:
        return False
    expected = compute_signature(secret, timestamp, body)
    supplied = signature.removeprefix("sha256=").strip().lower()
    return hmac.compare_digest(expected, supplied)
