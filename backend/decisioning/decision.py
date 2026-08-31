from datetime import datetime, timezone
from backend.decisioning.expected_value import ExpectedValueCalculator
from backend.ingestion.schemas import Customer, DecisionResult, Payment, PaymentFailure, RecoveryAction
from backend.intelligence.recoverability import RecoverabilityModel


class DecisionEngine:
    """Ranks candidate actions by expected economic value and outputs structured decision results."""

    def __init__(self, ev_calculator: ExpectedValueCalculator | None = None):
        self.ev_calculator = ev_calculator or ExpectedValueCalculator()

    def make_decision(
        self,
        payment: Payment,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
    ) -> DecisionResult:
        candidate_scores = self.ev_calculator.evaluate_candidate_actions(
            payment=payment,
            failure=failure,
            customer=customer,
        )

        # Sort candidate actions descending by expected value
        sorted_candidates = sorted(candidate_scores, key=lambda x: x.expected_value, reverse=True)

        best_candidate = sorted_candidates[0]

        # If best non-STOP action has non-positive expected value (EV <= 0), fallback to STOP
        if best_candidate.expected_value <= 0.0 and best_candidate.action != RecoveryAction.STOP:
            # Find STOP candidate score
            stop_candidate = next((c for c in sorted_candidates if c.action == RecoveryAction.STOP), best_candidate)
            best_candidate = stop_candidate

        reasons = list(best_candidate.reason_codes)
        reasons.append(f"Ranked highest expected value (₹{best_candidate.expected_value:.2f})")

        return DecisionResult(
            payment_id=payment.payment_id,
            recommended_action=best_candidate.action,
            candidate_actions=candidate_scores,
            selected_value=best_candidate.expected_value,
            confidence=round(best_candidate.p_recovery if best_candidate.action != RecoveryAction.STOP else 0.95, 2),
            reason_codes=reasons,
            evaluated_at=datetime.now(timezone.utc),
        )
