from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_api_application_imports_successfully():
    assert app is not None
    assert app.title == "RevenueGuard"


def test_root_endpoint_returns_200():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "RevenueGuard API is running"
    assert "docs_url" in data
    assert "dashboard_url" in data
