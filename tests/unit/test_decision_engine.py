from datetime import datetime, timezone

from backend.decisioning.decision import DecisionEngine
from backend.decisioning.expected_value import ExpectedValueCalculator
from backend.ingestion.schemas import FailureCategory, Payment, PaymentFailure, RecoveryAction


def test_ev_calculator_scores_all_candidate_actions():
    calc = ExpectedValueCalculator()
    payment = Payment(
        payment_id="pay_ev_1",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=5000.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
    )
    failure = PaymentFailure(
        payment_id="pay_ev_1",
        failure_code="ERR_NETWORK_TIMEOUT",
        failure_category=FailureCategory.NETWORK_ERROR,
        occurred_at=datetime.now(timezone.utc),
    )

    scores = calc.evaluate_candidate_actions(payment, failure)
    assert len(scores) == 5
    actions_found = {s.action for s in scores}
    assert actions_found == {
        RecoveryAction.RETRY_NOW,
        RecoveryAction.RETRY_LATER,
        RecoveryAction.NOTIFY_CUSTOMER,
        RecoveryAction.ESCALATE,
        RecoveryAction.STOP,
    }


def test_decision_engine_ranks_highest_ev():
    engine = DecisionEngine()
    payment = Payment(
        payment_id="pay_dec_1",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=3000.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
    )
    failure = PaymentFailure(
        payment_id="pay_dec_1",
        failure_code="ERR_NETWORK_TIMEOUT",
        failure_category=FailureCategory.NETWORK_ERROR,
        occurred_at=datetime.now(timezone.utc),
    )

    res = engine.make_decision(payment, failure)
    assert res.recommended_action in (RecoveryAction.RETRY_NOW, RecoveryAction.RETRY_LATER)
    assert res.selected_value > 0.0
