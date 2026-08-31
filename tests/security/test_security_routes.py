from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_sensitive_files_not_exposed():
    """Verifies that sensitive configuration, source code, and credentials cannot be served over HTTP."""
    sensitive_paths = [
        "/.env",
        "/.git",
        "/.git/config",
        "/.gitignore",
        "/backend/app.py",
        "/backend/config.py",
        "/backend/routers/security.py",
        "/data/audit_trail.jsonl",
        "/data/models/recoverability_model.json",
        "/requirements.txt",
    ]

    for path in sensitive_paths:
        response = client.get(path)
        # Should return 404 Not Found (or 405 Method Not Allowed), NEVER 200 with file content
        assert response.status_code in (404, 405), f"Path '{path}' returned status {response.status_code}"


def test_dashboard_serves_valid_html():
    """Verifies that the dashboard UI is accessible and serves HTML."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text or "<html" in response.text


def test_system_status_endpoint():
    """Verifies that system status endpoint returns operator config and safety guarantees."""
    response = client.get("/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "operator" in data
    assert data["operator"]["name"] == "Merchant Operations Admin"
    assert data["operator"]["auth_status"] == "configured_identity"
    assert data["safety"]["policy_engine"] == "ACTIVE"
