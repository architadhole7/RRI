from datetime import datetime, timezone

from backend.ingestion.schemas import Customer, Payment
from backend.orchestrator.executor import ActionExecutor
from backend.security.kill_switch import KillSwitchManager


def test_action_executor_end_to_end_flow():
    executor = ActionExecutor()
    payment = Payment(
        payment_id="pay_orch_1",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=1200.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
    )

    res = executor.process_failed_payment(payment)
    assert res["status"] in ("EXECUTED", "NEEDS_HUMAN_APPROVAL")
    assert "recommended_action" in res


def test_action_executor_kill_switch_blocking():
    executor = ActionExecutor()
    kill_switch = KillSwitchManager()
    kill_switch.enable("Test emergency kill switch")

    payment = Payment(
        payment_id="pay_orch_kill",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=1000.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        created_at=datetime.now(timezone.utc),
    )

    res = executor.process_failed_payment(payment)
    assert res["status"] == "BLOCKED"
    assert "Kill Switch" in res["reason"]

    kill_switch.disable()
