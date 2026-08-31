from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    NETWORK_ERROR = "NETWORK_ERROR"
    EXPIRED_PAYMENT_METHOD = "EXPIRED_PAYMENT_METHOD"
    BANK_DECLINED = "BANK_DECLINED"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    UNKNOWN = "UNKNOWN"


class RecoveryAction(str, Enum):
    RETRY_NOW = "RETRY_NOW"
    RETRY_LATER = "RETRY_LATER"
    NOTIFY_CUSTOMER = "NOTIFY_CUSTOMER"
    ESCALATE = "ESCALATE"
    STOP = "STOP"


class PolicyResultType(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    NEEDS_HUMAN_APPROVAL = "NEEDS_HUMAN_APPROVAL"


class Merchant(BaseModel):
    merchant_id: str
    name: str = "Default Merchant"
    category: str = "E_COMMERCE"
    risk_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)


class Customer(BaseModel):
    customer_id: str
    merchant_id: str
    payment_method: str = "CARD"
    total_successful_payments: int = Field(default=0, ge=0)
    total_failed_payments: int = Field(default=0, ge=0)
    consent_to_contact: bool = True
    subscription_status: str = "ACTIVE"
    avg_transaction_value: float = Field(default=1000.0, ge=0.0)
    risk_score: float = Field(default=0.1, ge=0.0, le=1.0)
    contact_count: int = Field(default=0, ge=0)


class Payment(BaseModel):
    payment_id: str
    merchant_id: str
    customer_id: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    payment_method: str
    status: str = "FAILED"
    failure_code: str | None = None
    created_at: datetime
    attempt_number: int = Field(default=1, ge=1)
    retry_count: int = Field(default=0, ge=0)


class PaymentFailure(BaseModel):
    payment_id: str
    failure_code: str
    failure_category: FailureCategory
    failure_message: str | None = None
    occurred_at: datetime
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RecoveryAttempt(BaseModel):
    payment_id: str
    action: RecoveryAction
    attempt_number: int = Field(default=1, ge=1)
    attempted_at: datetime
    status: str = "COMPLETED"


class PolicyDecision(BaseModel):
    payment_id: str
    action: RecoveryAction
    decision: PolicyResultType
    reason: str
    evaluated_at: datetime


class RecoveryOutcome(BaseModel):
    payment_id: str
    action: RecoveryAction
    recovered: bool
    recovered_amount: float = Field(default=0.0, ge=0.0)
    recovery_time_hours: float = Field(default=0.0, ge=0.0)
    action_cost: float = Field(default=0.0, ge=0.0)
    customer_friction: float = Field(default=0.0, ge=0.0)
    risk_penalty: float = Field(default=0.0, ge=0.0)
    occurred_at: datetime


class CandidateActionScore(BaseModel):
    action: RecoveryAction
    expected_value: float
    p_recovery: float = Field(ge=0.0, le=1.0)
    action_cost: float = Field(ge=0.0)
    customer_friction: float = Field(ge=0.0)
    risk_penalty: float = Field(ge=0.0)
    reason_codes: list[str] = Field(default_factory=list)


class DecisionResult(BaseModel):
    payment_id: str
    recommended_action: RecoveryAction
    candidate_actions: list[CandidateActionScore]
    selected_value: float
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    evaluated_at: datetime


class PolicyEvaluation(BaseModel):
    payment_id: str
    action: RecoveryAction
    result: PolicyResultType
    violations: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    evaluated_at: datetime


class HumanApprovalRequest(BaseModel):
    approval_id: str
    payment_id: str
    merchant_id: str
    action: RecoveryAction
    amount: float
    reason: str
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer: str | None = None


class AgentRecommendation(BaseModel):
    recommended_action: RecoveryAction
    reasoning_summary: str
    key_signals: list[str]
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class AuditLogEntry(BaseModel):
    entry_id: str
    timestamp: datetime
    transaction_id: str
    decision_id: str | None = None
    event_type: str
    selected_action: RecoveryAction | None = None
    policy_result: PolicyResultType | None = None
    execution_result: str | None = None
    model_version: str = "1.0.0"
    policy_version: str = "1.0.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str | None = None
    current_hash: str | None = None


class BlockedActionRecord(BaseModel):
    transaction_id: str
    amount: float = 0.0
    attempted_action: str
    guard_decision: str
    reason: str
    timestamp: datetime


class EvaluationMetrics(BaseModel):
    total_transactions: int = 0
    total_at_risk_amount: float = 0.0
    baseline_recovered_amount: float = 0.0
    baseline_recovery_rate: float = 0.0
    revenueguard_automated_recovered_amount: float = 0.0
    revenueguard_human_approved_recovered_amount: float = 0.0
    total_recovered_amount: float = 0.0
    recovery_rate: float = 0.0
    incremental_recovery_amount: float = 0.0
    incremental_recovery_lift_pct: float = 0.0
    net_recovery: float = 0.0
    intervention_count: int = 0
    total_action_cost: float = 0.0
    contact_count: int = 0
    escalation_count: int = 0
    action_breakdown: dict[str, int] = Field(default_factory=dict)
    unsafe_actions_blocked: int = 0
    approval_required_count: int = 0
    approval_approved_count: int = 0
    approval_denied_count: int = 0
    policy_denied_count: int = 0


class PolicyConfig(BaseModel):
    max_retries: int = 3
    cooldown_hours: int = 24
    contact_limit: int = 2
    approval_threshold_inr: float = 5000.0
    risk_limit: float = 0.8
    kill_switch_enabled: bool = False


class RecoveryEvaluationRequest(BaseModel):
    payment_id: str
    merchant_id: str | None = None
    failure_code: str | None = None


class RecoverySimulationRequest(BaseModel):
    payment_id: str
    simulation_scenarios: list[str] = Field(default_factory=list)


class PlaceholderResponse(BaseModel):
    status: str = "not_implemented"
    message: str