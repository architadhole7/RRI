from typing import Any
from backend.ingestion.schemas import EvaluationMetrics, RecoveryOutcome


class MetricsCalculator:
    """Calculates performance, economic recovery, and baseline comparison metrics."""

    def calculate_metrics(
        self,
        rg_outcomes: list[dict[str, Any]],
        baseline_outcomes: list[RecoveryOutcome],
        total_at_risk_amount: float,
        unsafe_blocked: int = 0,
        approval_required_count: int = 0,
        approval_approved_count: int = 0,
        approval_denied_count: int = 0,
        policy_denied_count: int = 0,
    ) -> EvaluationMetrics:
        total_txns = len(rg_outcomes)

        # RevenueGuard Metrics
        rg_auto_recovered = 0.0
        rg_human_recovered = 0.0

        rg_action_cost = 0.0
        rg_friction = 0.0
        rg_risk = 0.0

        rg_interventions = 0
        rg_contacts = 0
        rg_escalations = 0

        action_counts: dict[str, int] = {
            "RETRY_NOW": 0,
            "RETRY_LATER": 0,
            "NOTIFY_CUSTOMER": 0,
            "ESCALATE": 0,
            "STOP": 0,
        }

        for item in rg_outcomes:
            outcome: RecoveryOutcome = item["outcome"]
            is_human_approved: bool = item.get("is_human_approved", False)
            act_str = outcome.action.value if hasattr(outcome.action, "value") else str(outcome.action)

            action_counts[act_str] = action_counts.get(act_str, 0) + 1

            if outcome.recovered:
                if is_human_approved:
                    rg_human_recovered += outcome.recovered_amount
                else:
                    rg_auto_recovered += outcome.recovered_amount

            rg_action_cost += outcome.action_cost
            rg_friction += outcome.customer_friction
            rg_risk += outcome.risk_penalty

            if act_str != "STOP":
                rg_interventions += 1
            if act_str == "NOTIFY_CUSTOMER":
                rg_contacts += 1
            if act_str == "ESCALATE":
                rg_escalations += 1

        rg_total_recovered = rg_auto_recovered + rg_human_recovered
        rg_rec_rate = (rg_total_recovered / total_at_risk_amount) if total_at_risk_amount > 0 else 0.0
        rg_net_recovery = rg_total_recovered - rg_action_cost - rg_friction - rg_risk

        # Baseline Metrics
        b_recovered = sum(o.recovered_amount for o in baseline_outcomes if o.recovered)
        b_rec_rate = (b_recovered / total_at_risk_amount) if total_at_risk_amount > 0 else 0.0

        # Incremental Lift
        incremental_recovered = rg_total_recovered - b_recovered
        lift_pct = ((rg_total_recovered - b_recovered) / b_recovered * 100.0) if b_recovered > 0 else 0.0

        return EvaluationMetrics(
            total_transactions=total_txns,
            total_at_risk_amount=round(total_at_risk_amount, 2),
            baseline_recovered_amount=round(b_recovered, 2),
            baseline_recovery_rate=round(b_rec_rate, 4),
            revenueguard_automated_recovered_amount=round(rg_auto_recovered, 2),
            revenueguard_human_approved_recovered_amount=round(rg_human_recovered, 2),
            total_recovered_amount=round(rg_total_recovered, 2),
            recovery_rate=round(rg_rec_rate, 4),
            incremental_recovery_amount=round(incremental_recovered, 2),
            incremental_recovery_lift_pct=round(lift_pct, 2),
            net_recovery=round(rg_net_recovery, 2),
            intervention_count=rg_interventions,
            total_action_cost=round(rg_action_cost, 2),
            contact_count=rg_contacts,
            escalation_count=rg_escalations,
            action_breakdown=action_counts,
            unsafe_actions_blocked=unsafe_blocked,
            approval_required_count=approval_required_count,
            approval_approved_count=approval_approved_count,
            approval_denied_count=approval_denied_count,
            policy_denied_count=policy_denied_count,
        )
