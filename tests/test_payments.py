from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend.app import app
from backend.ingestion.schemas import Payment

client = TestClient(app)


def test_payment_schema_validation_works():
    payment = Payment(
        payment_id="pay_001",
        merchant_id="mer_001",
        customer_id="cust_001",
        amount=2500.50,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="INSUFFICIENT_FUNDS",
        created_at=datetime.now(timezone.utc),
    )
    assert payment.payment_id == "pay_001"
    assert payment.amount == 2500.50


def test_payment_schema_validation_invalid_amount_rejected():
    with pytest.raises(ValidationError):
        Payment(
            payment_id="pay_002",
            merchant_id="mer_001",
            customer_id="cust_001",
            amount=-100.00,  # Invalid amount <= 0
            currency="INR",
            payment_method="CARD",
            status="FAILED",
            created_at=datetime.now(timezone.utc),
        )


def test_create_payment_api_success():
    payload = {
        "payment_id": "pay_test_100",
        "merchant_id": "mer_001",
        "customer_id": "cust_001",
        "amount": 999.0,
        "currency": "INR",
        "payment_method": "NET_BANKING",
        "status": "FAILED",
        "created_at": "2026-08-24T20:00:00Z",
    }
    response = client.post("/payments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["payment_id"] == "pay_test_100"
    assert data["amount"] == 999.0


def test_create_payment_api_invalid_amount_rejected():
    payload = {
        "payment_id": "pay_test_101",
        "merchant_id": "mer_001",
        "customer_id": "cust_001",
        "amount": -50.0,  # Must be > 0
        "currency": "INR",
        "payment_method": "UPI",
        "status": "FAILED",
        "created_at": "2026-08-24T20:00:00Z",
    }
    response = client.post("/payments", json=payload)
    assert response.status_code == 422  # Unprocessable Entity


def test_get_payment_api_success():
    payload = {
        "payment_id": "pay_test_200",
        "merchant_id": "mer_002",
        "customer_id": "cust_002",
        "amount": 500.0,
        "currency": "INR",
        "payment_method": "UPI",
        "status": "FAILED",
        "created_at": "2026-08-24T20:00:00Z",
    }
    client.post("/payments", json=payload)
    response = client.get("/payments/pay_test_200")
    assert response.status_code == 200
    assert response.json()["payment_id"] == "pay_test_200"


def test_get_payment_api_not_found():
    response = client.get("/payments/non_existent_id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
