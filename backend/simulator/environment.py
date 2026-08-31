from typing import Any
from backend.ingestion.schemas import Customer, Merchant, Payment, PaymentFailure, RecoveryAction, RecoveryOutcome
from backend.simulator.recovery import RecoverySimulator


class SimulatedEnvironment:
    """Stateful simulation environment for evaluating recovery strategies over synthetic datasets."""

    def __init__(
        self,
        merchants: dict[str, Merchant],
        customers: dict[str, Customer],
        payments: dict[str, Payment],
        failures: dict[str, PaymentFailure],
        ground_truth: dict[str, Any],
        seed: int = 42,
    ):
        self.merchants = merchants
        self.customers = customers
        self.payments = payments
        self.failures = failures
        self.ground_truth = ground_truth
        self.simulator = RecoverySimulator(ground_truth=ground_truth, seed=seed)
        self.history: list[dict[str, Any]] = []

    def execute_action(self, payment_id: str, action: RecoveryAction) -> RecoveryOutcome:
        payment = self.payments[payment_id]
        customer = self.customers.get(payment.customer_id)
        failure = self.failures.get(payment_id)

        outcome = self.simulator.simulate_action(
            payment=payment,
            action=action,
            customer=customer,
            failure=failure,
        )

        # Update environment state
        if action in (RecoveryAction.RETRY_NOW, RecoveryAction.RETRY_LATER):
            payment.retry_count += 1
            payment.attempt_number += 1

        if action == RecoveryAction.NOTIFY_CUSTOMER and customer:
            customer.contact_count += 1

        if outcome.recovered:
            payment.status = "RECOVERED"
            if customer:
                customer.total_successful_payments += 1

        self.history.append({
            "payment_id": payment_id,
            "action": action,
            "outcome": outcome,
        })

        return outcome
