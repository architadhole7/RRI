import logging
import os
from backend.agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from backend.ingestion.schemas import (
    AgentRecommendation,
    Customer,
    DecisionResult,
    Payment,
    PaymentFailure,
    PolicyEvaluation,
    PolicyResultType,
    RecoveryAction,
)

logger = logging.getLogger("revenueguard")


class RevenueGuardAgent:
    """Bounded AI agent layer providing structured recovery recommendations with deterministic fallbacks."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    def evaluate_and_recommend(
        self,
        payment: Payment,
        decision_result: DecisionResult,
        policy_eval: PolicyEvaluation,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
    ) -> AgentRecommendation:
        # Check if policy explicitly DENIES the action
        if policy_eval.result == PolicyResultType.DENY:
            return AgentRecommendation(
                recommended_action=RecoveryAction.STOP,
                reasoning_summary=f"Automated action DENIED by deterministic policy engine: {'; '.join(policy_eval.violations)}",
                key_signals=["Policy violation", "Fail-closed safety trigger"],
                confidence=0.99,
            )

        # Attempt LLM call if API key exists, otherwise fallback to deterministic AI synthesis
        if self.api_key:
            try:
                return self._call_llm(payment, decision_result, policy_eval, failure, customer)
            except Exception as e:
                logger.warning("LLM API call failed, using deterministic fallback. Error: %s", str(e))

        return self._deterministic_fallback(payment, decision_result, policy_eval, failure, customer)

    def _deterministic_fallback(
        self,
        payment: Payment,
        decision_result: DecisionResult,
        policy_eval: PolicyEvaluation,
        failure: PaymentFailure | None,
        customer: Customer | None,
    ) -> AgentRecommendation:
        action = decision_result.recommended_action
        signals = []

        if failure:
            signals.append(f"Failure category: {failure.failure_category.value}")

        signals.append(f"Top EV action: {action.value} (Expected net recovery: ₹{decision_result.selected_value:.2f})")
        signals.append(f"Retry count: {payment.retry_count}")

        if customer and not customer.consent_to_contact:
            signals.append("Customer opted out of direct notifications")

        if policy_eval.result == PolicyResultType.NEEDS_HUMAN_APPROVAL:
            summary = (
                f"Action {action.value} offers top EV (₹{decision_result.selected_value:.2f}) "
                f"but requires human merchant approval: {'; '.join(policy_eval.violations)}"
            )
        else:
            summary = (
                f"Recommended {action.value} based on optimal expected net value (₹{decision_result.selected_value:.2f}) "
                f"and full compliance with deterministic safety policy rules."
            )

        return AgentRecommendation(
            recommended_action=action,
            reasoning_summary=summary,
            key_signals=signals,
            confidence=decision_result.confidence,
        )

    def _call_llm(
        self,
        payment: Payment,
        decision_result: DecisionResult,
        policy_eval: PolicyEvaluation,
        failure: PaymentFailure | None,
        customer: Customer | None,
    ) -> AgentRecommendation:
        # Placeholder for external LLM API client call using structured output
        return self._deterministic_fallback(payment, decision_result, policy_eval, failure, customer)
