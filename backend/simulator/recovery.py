from datetime import datetime, timezone
import hashlib
import random
from typing import Any

from backend.ingestion.schemas import Customer, Payment, PaymentFailure, RecoveryAction, RecoveryOutcome

ACTION_COSTS = {
    RecoveryAction.RETRY_NOW: 2.0,
    RecoveryAction.RETRY_LATER: 3.0,
    RecoveryAction.NOTIFY_CUSTOMER: 5.0,
    RecoveryAction.ESCALATE: 50.0,
    RecoveryAction.STOP: 0.0,
}

BASE_FRICTION = {
    RecoveryAction.RETRY_NOW: 2.0,
    RecoveryAction.RETRY_LATER: 1.0,
    RecoveryAction.NOTIFY_CUSTOMER: 10.0,
    RecoveryAction.ESCALATE: 20.0,
    RecoveryAction.STOP: 0.0,
}


class RecoverySimulator:
    """Simulates payment recovery outcomes in a reproducible synthetic environment."""

    def __init__(self, ground_truth: dict[str, Any] | None = None, seed: int = 42):
        self.ground_truth = ground_truth or {}
        self.seed = seed

    def simulate_action(
        self,
        payment: Payment,
        action: RecoveryAction | str,
        customer: Customer | None = None,
        failure: PaymentFailure | None = None,
        occurred_at: datetime | None = None,
    ) -> RecoveryOutcome:
        if occurred_at is None:
            occurred_at = datetime.now(timezone.utc)

        # Normalize action to RecoveryAction enum
        if isinstance(action, str):
            action_enum = RecoveryAction(action)
        else:
            action_enum = action

        action_str = action_enum.value

        # 1. Deterministic Pseudo-random Seed for Action Evaluation
        hash_input = f"{self.seed}_{payment.payment_id}_{action_str}_{payment.retry_count}".encode("utf-8")
        hash_val = int(hashlib.sha256(hash_input).hexdigest(), 16)
        action_rng = random.Random(hash_val)

        # 2. Extract Ground Truth Probability
        gt_data = self.ground_truth.get(payment.payment_id, {})
        true_probs = gt_data.get("true_probabilities", {})

        p_success = true_probs.get(action_str, 0.10)

        # 3. Simulate Roll
        roll = action_rng.random()
        recovered = (roll < p_success) and (action_enum != RecoveryAction.STOP)

        recovered_amount = payment.amount if recovered else 0.0

        # 4. Action Costs & Friction
        action_cost = ACTION_COSTS.get(action_enum, 0.0)
        friction = BASE_FRICTION.get(action_enum, 0.0)

        if action_enum == RecoveryAction.NOTIFY_CUSTOMER and customer and not customer.consent_to_contact:
            friction += 80.0  # High friction penalty for contacting non-consenting customers

        if action_enum == RecoveryAction.RETRY_NOW and payment.retry_count >= 2:
            friction += 15.0  # Friction from repeated immediate retries

        # Risk penalty for spamming or high-risk profiles
        risk_penalty = 0.0
        if customer and customer.risk_score > 0.5:
            risk_penalty += 10.0

        # Recovery delay hours
        recovery_time = 0.0
        if recovered:
            if action_enum == RecoveryAction.RETRY_NOW:
                recovery_time = 0.1
            elif action_enum == RecoveryAction.RETRY_LATER:
                recovery_time = 24.0
            elif action_enum == RecoveryAction.NOTIFY_CUSTOMER:
                recovery_time = 4.5
            elif action_enum == RecoveryAction.ESCALATE:
                recovery_time = 12.0

        return RecoveryOutcome(
            payment_id=payment.payment_id,
            action=action_enum,
            recovered=recovered,
            recovered_amount=recovered_amount,
            recovery_time_hours=recovery_time,
            action_cost=action_cost,
            customer_friction=friction,
            risk_penalty=risk_penalty,
            occurred_at=occurred_at,
        )
