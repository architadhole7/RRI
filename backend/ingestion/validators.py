from datetime import datetime, timezone
from backend.ingestion.schemas import Customer, Payment, PaymentFailure


class ValidationError(Exception):
    """Custom exception raised when data ingestion validation fails."""
    pass


def validate_customer(customer: Customer) -> None:
    if customer.total_successful_payments < 0:
        raise ValidationError(f"Invalid negative successful payments for customer {customer.customer_id}")
    if customer.total_failed_payments < 0:
        raise ValidationError(f"Invalid negative failed payments for customer {customer.customer_id}")
    if not (0.0 <= customer.risk_score <= 1.0):
        raise ValidationError(f"Risk score out of range [0, 1] for customer {customer.customer_id}")


def validate_payment(payment: Payment, customers: dict[str, Customer] | None = None) -> None:
    if payment.amount <= 0:
        raise ValidationError(f"Payment amount must be greater than zero. Got {payment.amount}")
    if payment.retry_count < 0:
        raise ValidationError(f"Invalid retry_count {payment.retry_count} for payment {payment.payment_id}")
    if payment.attempt_number < 1:
        raise ValidationError(f"Invalid attempt_number {payment.attempt_number} for payment {payment.payment_id}")

    # Integrity check for orphan customer references
    if customers is not None and payment.customer_id not in customers:
        raise ValidationError(f"Orphan payment {payment.payment_id}: Customer {payment.customer_id} does not exist")


def validate_payment_failure(failure: PaymentFailure) -> None:
    if failure.confidence < 0.0 or failure.confidence > 1.0:
        raise ValidationError(f"Confidence score {failure.confidence} out of range [0, 1]")
