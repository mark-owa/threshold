def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Threshold"


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_request_id_header_roundtrip(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-123"})
    assert response.headers["x-request-id"] == "test-request-123"


def test_request_id_generated_when_absent(client):
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0
