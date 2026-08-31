from datetime import datetime, timezone

from backend.ingestion.schemas import Customer, Payment, PolicyConfig, PolicyResultType, RecoveryAction
from backend.policy.engine import PolicyEngine


def test_policy_engine_max_retries_exceeded():
    engine = PolicyEngine(config=PolicyConfig(max_retries=3))
    payment = Payment(
        payment_id="pay_pol_1",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=1000.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
        retry_count=3,  # Reached max retries!
    )

    eval_res = engine.evaluate_action(payment, RecoveryAction.RETRY_NOW)
    assert eval_res.result == PolicyResultType.DENY
    assert "Retry limit exceeded" in eval_res.violations[0]


def test_policy_engine_customer_opt_out():
    engine = PolicyEngine()
    payment = Payment(
        payment_id="pay_pol_2",
        merchant_id="mer_01",
        customer_id="cust_02",
        amount=1000.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        created_at=datetime.now(timezone.utc),
    )
    customer = Customer(
        customer_id="cust_02",
        merchant_id="mer_01",
        consent_to_contact=False,  # Customer opted out!
    )

    eval_res = engine.evaluate_action(payment, RecoveryAction.NOTIFY_CUSTOMER, customer=customer)
    assert eval_res.result == PolicyResultType.DENY
    assert "opted out" in eval_res.violations[0]


def test_policy_engine_high_value_human_approval():
    engine = PolicyEngine(config=PolicyConfig(approval_threshold_inr=5000.0))
    payment = Payment(
        payment_id="pay_pol_3",
        merchant_id="mer_01",
        customer_id="cust_03",
        amount=15000.0,  # High value > ₹5,000!
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        created_at=datetime.now(timezone.utc),
    )

    eval_res = engine.evaluate_action(payment, RecoveryAction.RETRY_NOW)
    assert eval_res.result == PolicyResultType.NEEDS_HUMAN_APPROVAL
    assert eval_res.requires_approval is True
