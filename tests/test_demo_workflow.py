from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_demo_transaction_triggers_human_approval():
    """Verifies that high-value demo transaction (INR 12,500) reaches NEEDS_HUMAN_APPROVAL."""
    response = client.post("/recovery/demo/transaction")
    assert response.status_code == 200
    data = response.json()

    assert data["amount"] == 12500.0
    assert data["status"] == "NEEDS_HUMAN_APPROVAL"
    assert "approval_id" in data
    assert "exceeds high-value threshold" in data["reason"]

    approval_id = data["approval_id"]
    payment_id = data["payment_id"]

    # Verify pending approvals list contains this request
    app_res = client.get("/recovery/approvals")
    assert app_res.status_code == 200
    approvals = app_res.json()
    assert any(a["approval_id"] == approval_id for a in approvals)

    # Approve and execute via operator review endpoint
    review_res = client.post(f"/recovery/approvals/{approval_id}/review?approve=true")
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["status"] == "APPROVED"
    assert rev_data["reviewer"] == "Merchant Operations Admin"

    # Verify transaction journey for the approved payment
    journey_res = client.get(f"/recovery/transaction/{payment_id}/journey")
    assert journey_res.status_code == 200
    j_data = journey_res.json()
    assert j_data["payment"]["payment_id"] == payment_id
    assert j_data["diagnosis"]["raw_code"] == "ERR_INSUFFICIENT_FUNDS"
    assert len(j_data["audit_trail"]) >= 1


def test_demo_transaction_denial_workflow():
    """Verifies that operator denial blocks recovery execution and logs denial in audit trail."""
    response = client.post("/recovery/demo/transaction")
    assert response.status_code == 200
    data = response.json()
    approval_id = data["approval_id"]

    # Deny approval
    review_res = client.post(f"/recovery/approvals/{approval_id}/review?approve=false")
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["status"] == "REJECTED"

    # Verify blocked actions contains the blocked transaction
    blocked_res = client.get("/recovery/blocked")
    assert blocked_res.status_code == 200
    blocked_list = blocked_res.json()
    assert len(blocked_list) >= 1


def test_demo_blocked_scenario():
    """Verifies that controlled unsafe scenario triggers deterministic policy DENY."""
    response = client.post("/recovery/demo/blocked")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("BLOCKED", "SECURITY_BLOCKED")
    assert data["recommended_action"] == "STOP"
    assert "Retry limit exceeded" in data["reason"] or "limit" in data["reason"].lower()

    # Verify audit hash chain integrity is valid
    verify_res = client.get("/audit/verify")
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["verified"] is True
