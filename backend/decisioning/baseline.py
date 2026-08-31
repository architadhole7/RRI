from backend.ingestion.schemas import Customer, FailureCategory, Payment, PaymentFailure, RecoveryAction


class FixedPolicyBaselineStrategy:
    """Fixed-policy recovery strategy representing standard deterministic industry rules."""

    def recommend_action(
        self,
        payment: Payment,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
    ) -> RecoveryAction:
        retry_count = payment.retry_count
        category = failure.failure_category if failure else FailureCategory.UNKNOWN

        # Max retries safeguard
        if retry_count >= 3:
            return RecoveryAction.STOP

        if category == FailureCategory.NETWORK_ERROR:
            if retry_count == 0:
                return RecoveryAction.RETRY_NOW
            elif retry_count == 1:
                return RecoveryAction.RETRY_LATER
            else:
                return RecoveryAction.STOP

        elif category == FailureCategory.INSUFFICIENT_FUNDS:
            if retry_count == 0:
                return RecoveryAction.RETRY_LATER
            elif retry_count == 1 and customer and customer.consent_to_contact and customer.contact_count == 0:
                return RecoveryAction.NOTIFY_CUSTOMER
            else:
                return RecoveryAction.STOP

        elif category == FailureCategory.EXPIRED_PAYMENT_METHOD:
            if customer and customer.consent_to_contact and customer.contact_count == 0:
                return RecoveryAction.NOTIFY_CUSTOMER
            elif payment.amount >= 5000.0:
                return RecoveryAction.ESCALATE
            else:
                return RecoveryAction.STOP

        elif category in (FailureCategory.LIMIT_EXCEEDED, FailureCategory.TEMPORARY_FAILURE):
            if retry_count == 0:
                return RecoveryAction.RETRY_LATER
            elif customer and customer.consent_to_contact and customer.contact_count == 0:
                return RecoveryAction.NOTIFY_CUSTOMER
            else:
                return RecoveryAction.STOP

        elif category == FailureCategory.BANK_DECLINED:
            if payment.amount >= 5000.0:
                return RecoveryAction.ESCALATE
            elif customer and customer.consent_to_contact and customer.contact_count == 0:
                return RecoveryAction.NOTIFY_CUSTOMER
            else:
                return RecoveryAction.STOP

        else:  # UNKNOWN
            if retry_count == 0:
                return RecoveryAction.RETRY_LATER
            else:
                return RecoveryAction.STOP
