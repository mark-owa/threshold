from app.core.webhooks import compute_signature, verify_signature


def test_webhook_signature_accepts_valid_message():
    body = b'{"event":"refund.requested"}'
    timestamp = "1700000000"
    secret = "super-secret-value"
    signature = compute_signature(secret, timestamp, body)
    assert verify_signature(
        secret=secret,
        timestamp=timestamp,
        body=body,
        signature=f"sha256={signature}",
        allowed_clock_skew_seconds=300,
        now=1700000010,
    )


def test_webhook_signature_rejects_tampered_body():
    timestamp = "1700000000"
    secret = "super-secret-value"
    signature = compute_signature(secret, timestamp, b'{"amount":10}')
    assert not verify_signature(
        secret=secret,
        timestamp=timestamp,
        body=b'{"amount":1000}',
        signature=signature,
        allowed_clock_skew_seconds=300,
        now=1700000010,
    )


def test_webhook_signature_rejects_expired_timestamp():
    body = b"{}"
    timestamp = "1700000000"
    secret = "super-secret-value"
    signature = compute_signature(secret, timestamp, body)
    assert not verify_signature(
        secret=secret,
        timestamp=timestamp,
        body=body,
        signature=signature,
        allowed_clock_skew_seconds=300,
        now=1700000401,
    )
