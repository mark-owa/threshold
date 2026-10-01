"""Real local HTTP delivery checks; no n8n, CRM, broker or database is simulated here."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.core.config import get_settings
from app.core.webhooks import verify_signature
from app.services.outcomes import DeliveryError, deliver_outcome


@pytest.mark.parametrize("code", [200, 429, 401])
def test_delivery_over_real_http(monkeypatch, code):
    org, delivery_id = uuid4(), uuid4()
    secret = "local-http-test-secret-" + "x" * 32
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((dict(self.headers), body))
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "45")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "delivery_id": str(delivery_id)}).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "INTEGRATION_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setattr(
        settings,
        "N8N_OUTCOME_TARGETS",
        {
            str(org): {
                "url": f"http://127.0.0.1:{server.server_port}/outcome",
                "secret_ref": "local_http_test",
                "hubspot_portal_id": "123",
            },
        },
    )
    monkeypatch.setenv("THRESHOLD_WEBHOOK_SECRET__LOCAL_HTTP_TEST", secret)
    row = SimpleNamespace(
        id=delivery_id,
        organization_id=org,
        payload={
            "delivery_id": str(delivery_id),
            "organization_id": str(org),
            "crm": {"provider": "hubspot", "portal_id": "123", "ticket_id": "456"},
        },
    )
    try:
        # This receiver is loopback-only; don't route the local test through
        # a machine's external HTTP proxy. The transport is real TCP/HTTP.
        with httpx.Client(trust_env=False) as client:
            if code == 200:
                deliver_outcome(row, client=client)
            else:
                with pytest.raises(DeliveryError) as caught:
                    deliver_outcome(row, client=client)
                assert caught.value.retryable is (code == 429)
                assert caught.value.retry_after == 45
        assert len(received) == 1
        headers, body = received[0]
        assert json.loads(body) == row.payload
        assert headers["X-Threshold-Delivery-Id"] == str(delivery_id)
        assert headers["X-Threshold-Token"] == secret
        assert verify_signature(
            secret=secret,
            timestamp=headers["X-Threshold-Timestamp"],
            body=body,
            signature=headers["X-Threshold-Signature"],
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
