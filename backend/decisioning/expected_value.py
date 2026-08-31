from backend.decisioning.actions import ALL_CANDIDATE_ACTIONS, ACTION_DESCRIPTIONS
from backend.ingestion.schemas import CandidateActionScore, Customer, Payment, PaymentFailure, RecoveryAction
from backend.intelligence.recoverability import RecoverabilityModel
from backend.simulator.recovery import ACTION_COSTS, BASE_FRICTION


class ExpectedValueCalculator:
    """Calculates expected economic value EV(a) for each candidate recovery action."""

    def __init__(self, recoverability_model: RecoverabilityModel | None = None):
        self.model = recoverability_model or RecoverabilityModel()

    def evaluate_candidate_actions(
        self,
        payment: Payment,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
    ) -> list[CandidateActionScore]:
        scores: list[CandidateActionScore] = []

        for action in ALL_CANDIDATE_ACTIONS:
            p_rec = self.model.predict_probability(payment, action, failure, customer)
            cost = ACTION_COSTS.get(action, 0.0)

            # Compute friction penalty
            friction = BASE_FRICTION.get(action, 0.0)
            reason_codes = [ACTION_DESCRIPTIONS.get(action, "Candidate action")]

            if action == RecoveryAction.NOTIFY_CUSTOMER:
                if customer and not customer.consent_to_contact:
                    friction += 80.0
                    reason_codes.append("High friction penalty: Customer opted out of contact")
                elif customer and customer.contact_count >= 2:
                    friction += 30.0
                    reason_codes.append("Increased friction penalty: Multiple past notifications sent")

            if action == RecoveryAction.RETRY_NOW and payment.retry_count >= 2:
                friction += 15.0
                reason_codes.append("Friction penalty: Repeated immediate retry attempt")

            # Risk penalty calculation
            risk_penalty = 0.0
            if customer and customer.risk_score > 0.5:
                risk_penalty += 10.0
                reason_codes.append("Risk penalty: High-risk customer profile")

            # Calculate Net Expected Value
            if action == RecoveryAction.STOP:
                ev = 0.0
            else:
                ev = (p_rec * payment.amount) - cost - friction - risk_penalty

            scores.append(
                CandidateActionScore(
                    action=action,
                    expected_value=round(ev, 2),
                    p_recovery=round(p_rec, 4),
                    action_cost=round(cost, 2),
                    customer_friction=round(friction, 2),
                    risk_penalty=round(risk_penalty, 2),
                    reason_codes=reason_codes,
                )
            )

        return scores
