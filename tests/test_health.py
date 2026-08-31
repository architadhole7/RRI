from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_returns_http_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_expected_status():
    response = client.get("/health")
    data = response.json()
    assert data == {"status": "healthy"}
