from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.ingestion.schemas import Customer, Payment
from backend.orchestrator.executor import ActionExecutor
from backend.security.kill_switch import KillSwitchManager


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    print_banner("REVENUEGUARD AI REVENUE RECOVERY DEMO")

    executor = ActionExecutor()
    kill_switch = KillSwitchManager()

    # Scenario 1: Standard Network Error Recovery
    print_banner("SCENARIO 1: Standard Network Failure -> Automated RETRY_NOW")
    payment_1 = Payment(
        payment_id="pay_demo_101",
        merchant_id="mer_demo",
        customer_id="cust_001",
        amount=1500.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
        retry_count=0,
    )
    cust_1 = Customer(
        customer_id="cust_001",
        merchant_id="mer_demo",
        payment_method="UPI",
        consent_to_contact=True,
    )
    res_1 = executor.process_failed_payment(payment_1, customer=cust_1, raw_message="Gateway timeout")
    print(f"Status:             {res_1.get('status')}")
    print(f"Recommended Action: {res_1.get('recommended_action')}")
    print(f"Policy Result:      {res_1.get('policy_result')}")
    print(f"Reasoning:          {res_1.get('reasoning')}")
    outcome_1 = res_1.get("outcome")
    if outcome_1:
        print(f"Outcome Recovered:  {outcome_1.get('recovered')} (Amount: INR {outcome_1.get('recovered_amount')})")

    # Scenario 2: High Value Transaction -> Human Approval Queue
    print_banner("SCENARIO 2: High Value Transaction (INR 12,500) -> NEEDS_HUMAN_APPROVAL")
    payment_2 = Payment(
        payment_id="pay_demo_102",
        merchant_id="mer_demo",
        customer_id="cust_002",
        amount=12500.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        failure_code="ERR_BANK_DECLINED",
        created_at=datetime.now(timezone.utc),
        retry_count=0,
    )
    res_2 = executor.process_failed_payment(payment_2, raw_message="Card declined by issuing bank")
    print(f"Status:             {res_2.get('status')}")
    print(f"Approval Request ID:{res_2.get('approval_id')}")
    print(f"Recommended Action: {res_2.get('recommended_action')}")
    print(f"Reason / Violation: {res_2.get('reason')}")

    # Scenario 3: Opted Out Customer Notification Attempt -> DENIED
    print_banner("SCENARIO 3: Opted-Out Customer Contact Attempt -> DENIED by Policy")
    payment_3 = Payment(
        payment_id="pay_demo_103",
        merchant_id="mer_demo",
        customer_id="cust_opt_out",
        amount=2200.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        failure_code="ERR_CARD_EXPIRED",
        created_at=datetime.now(timezone.utc),
        retry_count=0,
    )
    cust_3 = Customer(
        customer_id="cust_opt_out",
        merchant_id="mer_demo",
        consent_to_contact=False,  # Explicitly opted out!
    )
    res_3 = executor.process_failed_payment(payment_3, customer=cust_3, raw_message="Card expired")
    print(f"Status:             {res_3.get('status')}")
    print(f"Recommended Action: {res_3.get('recommended_action')}")
    print(f"Policy Result:      {res_3.get('policy_result')}")
    print(f"Reasoning:          {res_3.get('reasoning')}")

    # Scenario 4: Global Kill Switch Triggered -> Fail Closed
    print_banner("SCENARIO 4: Emergency Kill Switch Triggered -> System Fail Closed")
    kill_switch.enable("Demo security threat override")
    res_4 = executor.process_failed_payment(payment_1, customer=cust_1)
    print(f"Kill Switch Active: {kill_switch.is_active()}")
    print(f"Status:             {res_4.get('status')}")
    print(f"Reason:             {res_4.get('reason')}")

    kill_switch.disable()

    print_banner("REVENUEGUARD DEMO EXECUTION COMPLETE")


if __name__ == "__main__":
    main()
