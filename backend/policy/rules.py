from backend.ingestion.schemas import (
    Customer,
    Payment,
    PolicyConfig,
    PolicyResultType,
    RecoveryAction,
)


class PolicyRuleRegistry:
    """Evaluates individual safety and compliance rules against a proposed action."""

    def evaluate_rules(
        self,
        payment: Payment,
        action: RecoveryAction,
        customer: Customer | None = None,
        config: PolicyConfig | None = None,
    ) -> tuple[PolicyResultType, list[str]]:
        if config is None:
            config = PolicyConfig()

        violations: list[str] = []
        requires_approval = False

        # 1. Global Kill Switch Rule
        if config.kill_switch_enabled:
            violations.append("Global emergency Kill Switch is active. All automated actions blocked.")
            return PolicyResultType.DENY, violations

        # STOP action is always allowed
        if action == RecoveryAction.STOP:
            return PolicyResultType.ALLOW, []

        # 2. Max Retry Limit Rule
        if action in (RecoveryAction.RETRY_NOW, RecoveryAction.RETRY_LATER):
            if payment.retry_count >= config.max_retries:
                violations.append(f"Retry limit exceeded ({payment.retry_count}/{config.max_retries}).")

        # 3. Customer Consent & Contact Limits
        if action == RecoveryAction.NOTIFY_CUSTOMER:
            if customer and not customer.consent_to_contact:
                violations.append("Customer has explicitly opted out of marketing/recovery contacts.")
            if customer and customer.contact_count >= config.contact_limit:
                violations.append(f"Customer contact limit reached ({customer.contact_count}/{config.contact_limit}).")

        # 4. High Value Transaction Human Approval Rule
        if payment.amount >= config.approval_threshold_inr:
            if action != RecoveryAction.STOP:
                requires_approval = True
                violations.append(
                    f"Transaction amount (₹{payment.amount:.2f}) exceeds high-value threshold (₹{config.approval_threshold_inr:.2f}). Requires merchant approval."
                )

        # 5. Customer Risk Level Rule
        if customer and customer.risk_score >= config.risk_limit:
            requires_approval = True
            violations.append(f"Customer risk score ({customer.risk_score}) exceeds safe threshold ({config.risk_limit}).")

        # Determine Final Result
        # Hard violations cause immediate DENY
        hard_deny_keywords = ["Kill Switch", "Retry limit", "opted out", "contact limit"]
        for v in violations:
            if any(kw in v for kw in hard_deny_keywords):
                return PolicyResultType.DENY, violations

        if requires_approval or violations:
            return PolicyResultType.NEEDS_HUMAN_APPROVAL, violations

        return PolicyResultType.ALLOW, []
