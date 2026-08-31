from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_list_blocked_actions_endpoint():
    response = client.get("/recovery/blocked")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_transactions_endpoint():
    response = client.get("/recovery/transactions?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "transactions" in data
    assert len(data["transactions"]) <= 10


def test_transaction_journey_endpoint():
    response = client.get("/recovery/transaction/pay_000001/journey")
    # Should either find pay_000001 or return 404 cleanly
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        data = response.json()
        assert "payment" in data
        assert "diagnosis" in data
        assert "candidate_actions" in data
        assert "recommended_action" in data
        assert "policy_evaluation" in data
        assert "outcome" in data


def test_audit_logs_and_verify_endpoints():
    # 1. Audit logs endpoint
    res_logs = client.get("/audit/logs?limit=5")
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert isinstance(logs, list)

    # 2. Audit verify endpoint
    res_verify = client.get("/audit/verify")
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    assert "verified" in verify_data
    assert "status" in verify_data
    assert verify_data["verified"] is True
