from fastapi.testclient import TestClient

from scripts import provider_simulator as simulator


def setup_function():
    simulator._refunds.clear()
    simulator._attempts.clear()


def _headers(key="test-key"):
    return {"Authorization": f"Bearer {simulator.TOKEN}", "Idempotency-Key": key}


def test_simulator_is_idempotent():
    client = TestClient(simulator.app)
    first = client.post(
        "/refunds", headers=_headers(), json={"order_number": "#1001", "amount_usd": 20}
    )
    second = client.post(
        "/refunds", headers=_headers(), json={"order_number": "#1001", "amount_usd": 20}
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_simulator_transient_failure_then_succeeds():
    client = TestClient(simulator.app)
    first = client.post(
        "/refunds",
        headers=_headers("retry"),
        json={"order_number": "RETRY-ONCE-1002", "amount_usd": 20},
    )
    second = client.post(
        "/refunds",
        headers=_headers("retry"),
        json={"order_number": "RETRY-ONCE-1002", "amount_usd": 20},
    )
    assert first.status_code == 503
    assert second.status_code == 200


def test_simulator_permanent_failure():
    client = TestClient(simulator.app)
    response = client.post(
        "/refunds",
        headers=_headers("hard"),
        json={"order_number": "HARD-FAIL-1003", "amount_usd": 20},
    )
    assert response.status_code == 422
