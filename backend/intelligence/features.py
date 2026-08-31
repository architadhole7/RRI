import math
from typing import Any
from backend.ingestion.schemas import Customer, FailureCategory, Payment, PaymentFailure, RecoveryAction


class FeatureExtractor:
    """Extracts leakage-free numerical and categorical features for recoverability modeling."""

    def extract_features(
        self,
        payment: Payment,
        action: RecoveryAction | str,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
    ) -> dict[str, float]:
        cat = failure.failure_category if failure else FailureCategory.UNKNOWN

        # Normalized Amount Feature
        amount_log = math.log1p(max(0.0, payment.amount))

        # Retry Count Feature
        retry_count = float(payment.retry_count)

        # Failure Category One-Hot / Indicator Features
        is_network = 1.0 if cat == FailureCategory.NETWORK_ERROR else 0.0
        is_funds = 1.0 if cat == FailureCategory.INSUFFICIENT_FUNDS else 0.0
        is_expired = 1.0 if cat == FailureCategory.EXPIRED_PAYMENT_METHOD else 0.0
        is_declined = 1.0 if cat == FailureCategory.BANK_DECLINED else 0.0
        is_limit = 1.0 if cat == FailureCategory.LIMIT_EXCEEDED else 0.0
        is_temp = 1.0 if cat == FailureCategory.TEMPORARY_FAILURE else 0.0

        # Payment Method Indicators
        pm = payment.payment_method.upper()
        is_upi = 1.0 if pm == "UPI" else 0.0
        is_card = 1.0 if pm == "CARD" else 0.0
        is_netbank = 1.0 if pm == "NET_BANKING" else 0.0

        # Action Indicators
        act_val = action.value if isinstance(action, RecoveryAction) else str(action)
        is_act_retry_now = 1.0 if act_val == RecoveryAction.RETRY_NOW.value else 0.0
        is_act_retry_later = 1.0 if act_val == RecoveryAction.RETRY_LATER.value else 0.0
        is_act_notify = 1.0 if act_val == RecoveryAction.NOTIFY_CUSTOMER.value else 0.0
        is_act_escalate = 1.0 if act_val == RecoveryAction.ESCALATE.value else 0.0
        is_act_stop = 1.0 if act_val == RecoveryAction.STOP.value else 0.0

        # Customer Indicators
        consent = 1.0 if (customer and customer.consent_to_contact) else 0.0
        risk_score = customer.risk_score if customer else 0.1
        contact_count = float(customer.contact_count) if customer else 0.0
        succ_rate = 0.5
        if customer and (customer.total_successful_payments + customer.total_failed_payments) > 0:
            succ_rate = customer.total_successful_payments / (
                customer.total_successful_payments + customer.total_failed_payments
            )

        return {
            "amount_log": amount_log,
            "retry_count": retry_count,
            "is_network": is_network,
            "is_funds": is_funds,
            "is_expired": is_expired,
            "is_declined": is_declined,
            "is_limit": is_limit,
            "is_temp": is_temp,
            "is_upi": is_upi,
            "is_card": is_card,
            "is_netbank": is_netbank,
            "is_act_retry_now": is_act_retry_now,
            "is_act_retry_later": is_act_retry_later,
            "is_act_notify": is_act_notify,
            "is_act_escalate": is_act_escalate,
            "is_act_stop": is_act_stop,
            "consent": consent,
            "risk_score": risk_score,
            "contact_count": contact_count,
            "succ_rate": succ_rate,
        }
