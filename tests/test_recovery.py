from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_recovery_evaluate_endpoint():
    payload = {"payment_id": "pay_eval_001", "merchant_id": "mer_001"}
    response = client.post("/recovery/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "recommended_action" in data
    assert "decision_id" in data


def test_recovery_simulate_endpoint():
    payload = {"payment_id": "pay_sim_001"}
    response = client.post("/recovery/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["payment_id"] == "pay_sim_001"
    assert "scenarios" in data
    assert len(data["scenarios"]) > 0
