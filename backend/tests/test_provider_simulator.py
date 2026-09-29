from fastapi.testclient import TestClient

from scripts import provider_simulator


def setup_function():
    provider_simulator._refunds.clear()
    provider_simulator._attempts.clear()


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer local-simulator-token",
        "Idempotency-Key": key,
    }


def test_provider_simulator_is_idempotent():
    client = TestClient(provider_simulator.app)
    payload = {"order_number": "ORDER-1", "amount_usd": 12.34}
    first = client.post("/refunds", json=payload, headers=_headers("idem-1"))
    second = client.post("/refunds", json=payload, headers=_headers("idem-1"))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_provider_simulator_retry_once_then_succeeds():
    client = TestClient(provider_simulator.app)
    payload = {"order_number": "RETRY-ONCE-1", "amount_usd": 15.00}
    first = client.post("/refunds", json=payload, headers=_headers("idem-retry"))
    second = client.post("/refunds", json=payload, headers=_headers("idem-retry"))
    assert first.status_code == 503
    assert second.status_code == 200


def test_provider_simulator_reconciliation_by_idempotency():
    client = TestClient(provider_simulator.app)
    payload = {"order_number": "ORDER-2", "amount_usd": 20.00}
    created = client.post("/refunds", json=payload, headers=_headers("idem-reconcile"))
    assert created.status_code == 200
    found = client.get(
        "/refunds/by-idempotency/idem-reconcile",
        headers={"Authorization": "Bearer local-simulator-token"},
    )
    assert found.status_code == 200
    assert found.json()["id"] == created.json()["id"]
