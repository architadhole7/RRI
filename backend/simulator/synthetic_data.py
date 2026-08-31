from datetime import datetime, timedelta, timezone
import random
from typing import Any

from backend.ingestion.schemas import (
    Customer,
    FailureCategory,
    Merchant,
    Payment,
    PaymentFailure,
    RecoveryAction,
)


FAILURE_CODES_MAP = {
    "ERR_NETWORK_TIMEOUT": FailureCategory.NETWORK_ERROR,
    "ERR_GATEWAY_DOWN": FailureCategory.NETWORK_ERROR,
    "ERR_INSUFFICIENT_FUNDS": FailureCategory.INSUFFICIENT_FUNDS,
    "ERR_LOW_BALANCE": FailureCategory.INSUFFICIENT_FUNDS,
    "ERR_CARD_EXPIRED": FailureCategory.EXPIRED_PAYMENT_METHOD,
    "ERR_BANK_DECLINED": FailureCategory.BANK_DECLINED,
    "ERR_SECURITY_BLOCK": FailureCategory.BANK_DECLINED,
    "ERR_DAILY_LIMIT_EXCEEDED": FailureCategory.LIMIT_EXCEEDED,
    "ERR_TEMP_PROCESSING_ISSUE": FailureCategory.TEMPORARY_FAILURE,
    "ERR_UNKNOWN": FailureCategory.UNKNOWN,
}

PAYMENT_METHODS = ["UPI", "CARD", "NET_BANKING", "WALLET", "AUTO_DEBIT"]
MERCHANT_CATEGORIES = ["E_COMMERCE", "SAAS_SUBSCRIPTION", "ED_TECH", "FINTECH_LENDING"]


class SyntheticDataGenerator:
    """Generates synthetic merchants, customers, payments, failures, and ground truth."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(
        self, num_merchants: int = 5, num_customers: int = 1000, num_transactions: int = 5000
    ) -> tuple[list[Merchant], list[Customer], list[Payment], list[PaymentFailure], dict[str, Any]]:
        self.rng = random.Random(self.seed)

        # 1. Generate Merchants
        merchants: list[Merchant] = []
        for i in range(1, num_merchants + 1):
            m_id = f"mer_{i:03d}"
            cat = self.rng.choice(MERCHANT_CATEGORIES)
            merchants.append(
                Merchant(
                    merchant_id=m_id,
                    name=f"Merchant {i} ({cat})",
                    category=cat,
                    risk_tolerance=round(self.rng.uniform(0.2, 0.8), 2),
                )
            )

        # 2. Generate Customers
        customers: list[Customer] = []
        for i in range(1, num_customers + 1):
            c_id = f"cust_{i:05d}"
            m_id = self.rng.choice(merchants).merchant_id
            pm = self.rng.choice(PAYMENT_METHODS)
            consent = self.rng.random() > 0.15  # 85% consent rate
            sub_status = "ACTIVE" if self.rng.random() > 0.20 else "CANCELLED"
            avg_val = round(self.rng.lognormvariate(6.5, 0.8), 2)  # Log-normal distribution
            avg_val = max(100.0, min(avg_val, 50000.0))
            risk_score = round(self.rng.uniform(0.02, 0.30), 3)

            customers.append(
                Customer(
                    customer_id=c_id,
                    merchant_id=m_id,
                    payment_method=pm,
                    total_successful_payments=self.rng.randint(1, 50),
                    total_failed_payments=self.rng.randint(0, 5),
                    consent_to_contact=consent,
                    subscription_status=sub_status,
                    avg_transaction_value=avg_val,
                    risk_score=risk_score,
                )
            )

        # 3. Generate Transactions & Failures
        payments: list[Payment] = []
        failures: list[PaymentFailure] = []
        ground_truth: dict[str, Any] = {}

        base_time = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(1, num_transactions + 1):
            p_id = f"pay_{i:06d}"
            cust = self.rng.choice(customers)

            # Amount around customer average
            amount = round(max(50.0, self.rng.gauss(cust.avg_transaction_value, cust.avg_transaction_value * 0.3)), 2)

            created_at = base_time + timedelta(minutes=self.rng.randint(1, 30 * 24 * 60))

            failure_code = self.rng.choice(list(FAILURE_CODES_MAP.keys()))
            failure_cat = FAILURE_CODES_MAP[failure_code]

            retry_count = self.rng.choices([0, 1, 2, 3], weights=[0.7, 0.2, 0.08, 0.02])[0]

            payment = Payment(
                payment_id=p_id,
                merchant_id=cust.merchant_id,
                customer_id=cust.customer_id,
                amount=amount,
                currency="INR",
                payment_method=cust.payment_method,
                status="FAILED",
                failure_code=failure_code,
                created_at=created_at,
                attempt_number=retry_count + 1,
                retry_count=retry_count,
            )

            payment_failure = PaymentFailure(
                payment_id=p_id,
                failure_code=failure_code,
                failure_category=failure_cat,
                failure_message=f"System error: {failure_code}",
                occurred_at=created_at,
                confidence=round(self.rng.uniform(0.85, 0.99), 2),
            )

            payments.append(payment)
            failures.append(payment_failure)

            # 4. Generate Ground Truth probabilities & outcomes for each action
            gt_action_probs = self._calculate_ground_truth_probs(
                failure_cat=failure_cat,
                amount=amount,
                retry_count=retry_count,
                cust=cust,
            )
            ground_truth[p_id] = {
                "payment_id": p_id,
                "failure_category": failure_cat.value,
                "true_probabilities": gt_action_probs,
            }

        return merchants, customers, payments, failures, ground_truth

    def _calculate_ground_truth_probs(
        self, failure_cat: FailureCategory, amount: float, retry_count: int, cust: Customer
    ) -> dict[str, float]:
        """Defines hidden ground-truth recovery probabilities based on realistic physical system behaviors."""
        base_probs = {
            RecoveryAction.RETRY_NOW.value: 0.10,
            RecoveryAction.RETRY_LATER.value: 0.15,
            RecoveryAction.NOTIFY_CUSTOMER.value: 0.10,
            RecoveryAction.ESCALATE.value: 0.05,
            RecoveryAction.STOP.value: 0.00,
        }

        if failure_cat == FailureCategory.NETWORK_ERROR:
            base_probs[RecoveryAction.RETRY_NOW.value] = 0.85
            base_probs[RecoveryAction.RETRY_LATER.value] = 0.70
            base_probs[RecoveryAction.NOTIFY_CUSTOMER.value] = 0.20
        elif failure_cat == FailureCategory.TEMPORARY_FAILURE:
            base_probs[RecoveryAction.RETRY_NOW.value] = 0.60
            base_probs[RecoveryAction.RETRY_LATER.value] = 0.75
            base_probs[RecoveryAction.NOTIFY_CUSTOMER.value] = 0.30
        elif failure_cat == FailureCategory.INSUFFICIENT_FUNDS:
            base_probs[RecoveryAction.RETRY_NOW.value] = 0.15
            base_probs[RecoveryAction.RETRY_LATER.value] = 0.65  # Customer deposits money after payday
            base_probs[RecoveryAction.NOTIFY_CUSTOMER.value] = (
                0.55 if cust.consent_to_contact else 0.05
            )
        elif failure_cat == FailureCategory.EXPIRED_PAYMENT_METHOD:
            base_probs[RecoveryAction.RETRY_NOW.value] = 0.00
            base_probs[RecoveryAction.RETRY_LATER.value] = 0.05
            base_probs[RecoveryAction.NOTIFY_CUSTOMER.value] = (
                0.80 if cust.consent_to_contact else 0.00
            )
            base_probs[RecoveryAction.ESCALATE.value] = 0.40
        elif failure_cat == FailureCategory.LIMIT_EXCEEDED:
            base_probs[RecoveryAction.RETRY_NOW.value] = 0.05
            base_probs[RecoveryAction.RETRY_LATER.value] = 0.60
            base_probs[RecoveryAction.NOTIFY_CUSTOMER.value] = (
                0.50 if cust.consent_to_contact else 0.00
            )
        elif failure_cat == FailureCategory.BANK_DECLINED:
            base_probs[RecoveryAction.RETRY_NOW.value] = 0.05
            base_probs[RecoveryAction.RETRY_LATER.value] = 0.20
            base_probs[RecoveryAction.NOTIFY_CUSTOMER.value] = (
                0.45 if cust.consent_to_contact else 0.00
            )
            base_probs[RecoveryAction.ESCALATE.value] = 0.60 if amount > 5000 else 0.20

        # Apply retry decay
        decay = max(0.2, 1.0 - 0.25 * retry_count)
        for act in base_probs:
            if act != RecoveryAction.STOP.value:
                base_probs[act] = round(max(0.0, min(1.0, base_probs[act] * decay)), 3)

        return base_probs
