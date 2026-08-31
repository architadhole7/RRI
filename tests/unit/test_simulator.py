from datetime import datetime, timezone
import pytest

from backend.ingestion.schemas import Customer, FailureCategory, Payment, PaymentFailure, RecoveryAction
from backend.simulator.recovery import RecoverySimulator
from backend.simulator.synthetic_data import SyntheticDataGenerator


def test_synthetic_data_generator_reproducibility():
    gen1 = SyntheticDataGenerator(seed=42)
    gen2 = SyntheticDataGenerator(seed=42)

    _, cust1, pay1, _, gt1 = gen1.generate(num_customers=50, num_transactions=100)
    _, cust2, pay2, _, gt2 = gen2.generate(num_customers=50, num_transactions=100)

    assert len(cust1) == len(cust2) == 50
    assert len(pay1) == len(pay2) == 100
    assert pay1[0].payment_id == pay2[0].payment_id
    assert pay1[0].amount == pay2[0].amount
    assert gt1["pay_000001"]["true_probabilities"] == gt2["pay_000001"]["true_probabilities"]


def test_recovery_simulator_determinism():
    sim1 = RecoverySimulator(seed=100)
    sim2 = RecoverySimulator(seed=100)

    payment = Payment(
        payment_id="pay_test_sim",
        merchant_id="mer_001",
        customer_id="cust_001",
        amount=1000.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
    )

    out1 = sim1.simulate_action(payment, RecoveryAction.RETRY_NOW)
    out2 = sim2.simulate_action(payment, RecoveryAction.RETRY_NOW)

    assert out1.recovered == out2.recovered
    assert out1.recovered_amount == out2.recovered_amount
    assert out1.action_cost == out2.action_cost
