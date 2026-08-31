from typing import Any
from backend.analytics.metrics import MetricsCalculator
from backend.decisioning.baseline import FixedPolicyBaselineStrategy
from backend.ingestion.schemas import (
    Customer,
    EvaluationMetrics,
    Merchant,
    Payment,
    PaymentFailure,
    PolicyConfig,
    RecoveryAction,
    RecoveryOutcome,
)
from backend.orchestrator.executor import ActionExecutor
from backend.policy.engine import PolicyEngine
from backend.simulator.recovery import RecoverySimulator


class Evaluator:
    """Evaluates Fixed-Policy Baseline vs. RevenueGuard Strategy on identical held-out dataset."""

    def __init__(self, seed: int = 42, policy_config: PolicyConfig | None = None):
        self.seed = seed
        self.policy_config = policy_config or PolicyConfig()
        self.baseline_strategy = FixedPolicyBaselineStrategy()
        self.metrics_calculator = MetricsCalculator()

    def resolve_simulated_approval(
        self,
        payment: Payment,
        action: RecoveryAction | str,
        customer: Customer | None = None,
        failure: PaymentFailure | None = None,
    ) -> bool:
        """Deterministic decision-time simulated approval rule for merchant operator review.
        
        Rule:
        - Approve intervention if transaction amount <= ₹25,000 AND customer risk score <= 0.35 AND failure confidence >= 0.75.
        - Otherwise reject (DENIED).
        Strictly uses decision-time context; zero access to future recovery outcomes.
        """
        risk_score = customer.risk_score if customer else 0.1
        confidence = failure.confidence if failure else 0.9

        if payment.amount <= 25000.0 and risk_score <= 0.35 and confidence >= 0.75:
            return True
        return False

    def run_evaluation(
        self,
        merchants: dict[str, Merchant],
        customers: dict[str, Customer],
        payments: dict[str, Payment],
        failures: dict[str, PaymentFailure],
        ground_truth: dict[str, Any],
    ) -> tuple[EvaluationMetrics, list[dict[str, Any]], list[RecoveryOutcome]]:
        simulator = RecoverySimulator(ground_truth=ground_truth, seed=self.seed)
        policy_engine = PolicyEngine(config=self.policy_config)
        executor = ActionExecutor(policy_engine=policy_engine, simulator=simulator)

        baseline_outcomes: list[RecoveryOutcome] = []
        rg_outcome_records: list[dict[str, Any]] = []

        total_at_risk = sum(p.amount for p in payments.values())

        unsafe_blocked_count = 0
        approval_required_count = 0
        approval_approved_count = 0
        approval_denied_count = 0
        policy_denied_count = 0

        for p_id, payment in payments.items():
            customer = customers.get(payment.customer_id)
            failure = failures.get(p_id)

            # 1. Run Fixed Baseline
            b_action = self.baseline_strategy.recommend_action(payment, failure, customer)
            b_outcome = simulator.simulate_action(payment, b_action, customer, failure)
            baseline_outcomes.append(b_outcome)

            # 2. Run RevenueGuard Agent
            res = executor.process_failed_payment(payment, failure, customer)
            status = res.get("status")

            if status in ("SECURITY_BLOCKED", "BLOCKED"):
                unsafe_blocked_count += 1
                policy_denied_count += 1
                stop_out = simulator.simulate_action(payment, RecoveryAction.STOP, customer, failure)
                rg_outcome_records.append({"outcome": stop_out, "is_human_approved": False})

            elif status == "NEEDS_HUMAN_APPROVAL":
                approval_required_count += 1
                rec_action_str = res.get("recommended_action", "STOP")
                rec_action = RecoveryAction(rec_action_str) if isinstance(rec_action_str, str) else rec_action_str

                # Simulated Approval Resolution
                approved = self.resolve_simulated_approval(payment, rec_action, customer, failure)
                if approved:
                    approval_approved_count += 1
                    exec_out = simulator.simulate_action(payment, rec_action, customer, failure)
                    rg_outcome_records.append({"outcome": exec_out, "is_human_approved": True})
                else:
                    approval_denied_count += 1
                    stop_out = simulator.simulate_action(payment, RecoveryAction.STOP, customer, failure)
                    rg_outcome_records.append({"outcome": stop_out, "is_human_approved": False})

            elif status == "EXECUTED":
                rg_out = res.get("outcome")
                if rg_out:
                    outcome_obj = RecoveryOutcome(**rg_out)
                    rg_outcome_records.append({"outcome": outcome_obj, "is_human_approved": False})
                else:
                    stop_out = simulator.simulate_action(payment, RecoveryAction.STOP, customer, failure)
                    rg_outcome_records.append({"outcome": stop_out, "is_human_approved": False})

            else:
                policy_denied_count += 1
                stop_out = simulator.simulate_action(payment, RecoveryAction.STOP, customer, failure)
                rg_outcome_records.append({"outcome": stop_out, "is_human_approved": False})

        metrics = self.metrics_calculator.calculate_metrics(
            rg_outcomes=rg_outcome_records,
            baseline_outcomes=baseline_outcomes,
            total_at_risk_amount=total_at_risk,
            unsafe_blocked=unsafe_blocked_count,
            approval_required_count=approval_required_count,
            approval_approved_count=approval_approved_count,
            approval_denied_count=approval_denied_count,
            policy_denied_count=policy_denied_count,
        )

        return metrics, rg_outcome_records, baseline_outcomes
