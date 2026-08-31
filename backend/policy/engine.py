from datetime import datetime, timezone
from backend.ingestion.schemas import Customer, Payment, PolicyConfig, PolicyEvaluation, PolicyResultType, RecoveryAction
from backend.policy.rules import PolicyRuleRegistry


class PolicyEngine:
    """Deterministic policy guard validating proposed recovery actions against safety policies."""

    def __init__(self, config: PolicyConfig | None = None):
        self.config = config or PolicyConfig()
        self.registry = PolicyRuleRegistry()

    def evaluate_action(
        self,
        payment: Payment,
        action: RecoveryAction,
        customer: Customer | None = None,
    ) -> PolicyEvaluation:
        result_type, violations = self.registry.evaluate_rules(
            payment=payment,
            action=action,
            customer=customer,
            config=self.config,
        )

        requires_approval = (result_type == PolicyResultType.NEEDS_HUMAN_APPROVAL)

        return PolicyEvaluation(
            payment_id=payment.payment_id,
            action=action,
            result=result_type,
            violations=violations,
            requires_approval=requires_approval,
            evaluated_at=datetime.now(timezone.utc),
        )
