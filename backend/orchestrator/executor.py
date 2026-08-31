from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from backend.agent.agent import RevenueGuardAgent
from backend.audit.logger import AuditLogger
from backend.decisioning.decision import DecisionEngine
from backend.ingestion.schemas import (
    Customer,
    DecisionResult,
    Merchant,
    Payment,
    PaymentFailure,
    PolicyEvaluation,
    PolicyResultType,
    RecoveryAction,
    RecoveryOutcome,
)
from backend.intelligence.failure_diagnosis import FailureDiagnoser
from backend.orchestrator.idempotency import IdempotencyStore
from backend.policy.approvals import ApprovalManager
from backend.policy.engine import PolicyEngine
from backend.security.kill_switch import KillSwitchManager
from backend.security.threat_detection import ThreatDetector
from backend.simulator.recovery import RecoverySimulator

logger = logging.getLogger("revenueguard")


class ActionExecutor:
    """Action Orchestrator governing decisioning, policy validation, approval gating, execution, and audit logging."""

    def __init__(
        self,
        diagnoser: FailureDiagnoser | None = None,
        decision_engine: DecisionEngine | None = None,
        policy_engine: PolicyEngine | None = None,
        agent: RevenueGuardAgent | None = None,
        simulator: RecoverySimulator | None = None,
        audit_logger: AuditLogger | None = None,
        approval_manager: ApprovalManager | None = None,
    ):
        self.diagnoser = diagnoser or FailureDiagnoser()
        self.decision_engine = decision_engine or DecisionEngine()
        self.policy_engine = policy_engine or PolicyEngine()
        self.agent = agent or RevenueGuardAgent()
        self.simulator = simulator or RecoverySimulator()
        self.audit_logger = audit_logger or AuditLogger()
        self.approval_manager = approval_manager or ApprovalManager()
        self.idempotency_store = IdempotencyStore()
        self.threat_detector = ThreatDetector()
        self.kill_switch = KillSwitchManager()

    def process_failed_payment(
        self,
        payment: Payment,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
        merchant: Merchant | None = None,
        raw_message: str | None = None,
    ) -> dict[str, Any]:
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"

        # 1. Emergency Kill Switch Check
        if self.kill_switch.is_active():
            self.audit_logger.log_event(
                transaction_id=payment.payment_id,
                event_type="KILL_SWITCH_BLOCKED",
                decision_id=decision_id,
                selected_action=RecoveryAction.STOP,
                policy_result=PolicyResultType.DENY,
                execution_result="BLOCKED_BY_KILL_SWITCH",
                metadata={"reason": "Emergency kill switch active"},
            )
            return {
                "decision_id": decision_id,
                "status": "BLOCKED",
                "reason": "Global emergency Kill Switch is active",
                "recommended_action": RecoveryAction.STOP.value,
                "outcome": None,
            }

        # 2. Threat & Security Inspection
        threats = self.threat_detector.inspect_payment_request(payment, raw_message)
        if threats:
            self.audit_logger.log_event(
                transaction_id=payment.payment_id,
                event_type="SECURITY_THREAT_DETECTED",
                decision_id=decision_id,
                selected_action=RecoveryAction.STOP,
                policy_result=PolicyResultType.DENY,
                execution_result="BLOCKED_BY_SECURITY",
                metadata={"threats": threats},
            )
            return {
                "decision_id": decision_id,
                "status": "SECURITY_BLOCKED",
                "reason": f"Security threats detected: {'; '.join(threats)}",
                "recommended_action": RecoveryAction.STOP.value,
                "outcome": None,
            }

        # 3. Failure Diagnosis
        if failure is None:
            cat, conf = self.diagnoser.diagnose(payment.failure_code, payment=payment, message=raw_message)
            failure = PaymentFailure(
                payment_id=payment.payment_id,
                failure_code=payment.failure_code or "UNKNOWN",
                failure_category=cat,
                occurred_at=payment.created_at,
                confidence=conf,
            )

        # 4. EV Decisioning
        decision_result: DecisionResult = self.decision_engine.make_decision(
            payment=payment, failure=failure, customer=customer
        )

        # 5. Deterministic Policy Validation
        proposed_action = decision_result.recommended_action
        policy_eval: PolicyEvaluation = self.policy_engine.evaluate_action(
            payment=payment, action=proposed_action, customer=customer
        )

        # 6. Bounded AI Agent Recommendation
        agent_rec = self.agent.evaluate_and_recommend(
            payment=payment,
            decision_result=decision_result,
            policy_eval=policy_eval,
            failure=failure,
            customer=customer,
        )

        # Final Action Selection
        action_to_execute = agent_rec.recommended_action

        # 7. Policy Enforcement Guard: LLM recommendation MUST pass policy
        if action_to_execute != RecoveryAction.STOP:
            policy_re_eval = self.policy_engine.evaluate_action(
                payment=payment, action=action_to_execute, customer=customer
            )

            if policy_re_eval.result == PolicyResultType.DENY:
                logger.warning(
                    "Policy DENIED recommended action %s for payment %s. Violations: %s",
                    action_to_execute,
                    payment.payment_id,
                    policy_re_eval.violations,
                )
                action_to_execute = RecoveryAction.STOP
                policy_eval = policy_re_eval

            elif policy_re_eval.result == PolicyResultType.NEEDS_HUMAN_APPROVAL:
                # Queue human approval
                app_req = self.approval_manager.create_approval_request(
                    payment_id=payment.payment_id,
                    merchant_id=payment.merchant_id,
                    action=action_to_execute,
                    amount=payment.amount,
                    reason="; ".join(policy_re_eval.violations),
                )
                self.audit_logger.log_event(
                    transaction_id=payment.payment_id,
                    event_type="APPROVAL_QUEUED",
                    decision_id=decision_id,
                    selected_action=action_to_execute,
                    policy_result=PolicyResultType.NEEDS_HUMAN_APPROVAL,
                    execution_result="PENDING_HUMAN_APPROVAL",
                    metadata={"approval_id": app_req.approval_id, "reason": app_req.reason},
                )
                return {
                    "decision_id": decision_id,
                    "status": "NEEDS_HUMAN_APPROVAL",
                    "approval_id": app_req.approval_id,
                    "recommended_action": action_to_execute.value,
                    "reason": app_req.reason,
                    "outcome": None,
                }

        # 8. Idempotency Check
        idempotency_key = self.idempotency_store.generate_key(
            payment.payment_id, action_to_execute.value, payment.retry_count
        )
        if self.idempotency_store.is_duplicate(idempotency_key) and action_to_execute != RecoveryAction.STOP:
            self.audit_logger.log_event(
                transaction_id=payment.payment_id,
                event_type="IDEMPOTENCY_BLOCKED",
                decision_id=decision_id,
                selected_action=action_to_execute,
                policy_result=PolicyResultType.DENY,
                execution_result="DUPLICATE_EXECUTION_BLOCKED",
            )
            return {
                "decision_id": decision_id,
                "status": "DUPLICATE_BLOCKED",
                "recommended_action": RecoveryAction.STOP.value,
                "outcome": None,
            }

        self.idempotency_store.register(idempotency_key)

        # 9. Action Execution & Simulation
        outcome: RecoveryOutcome = self.simulator.simulate_action(
            payment=payment,
            action=action_to_execute,
            customer=customer,
            failure=failure,
        )

        # 10. Audit Logging
        self.audit_logger.log_event(
            transaction_id=payment.payment_id,
            event_type="ACTION_EXECUTED",
            decision_id=decision_id,
            selected_action=action_to_execute,
            policy_result=policy_eval.result,
            execution_result="RECOVERED" if outcome.recovered else "NOT_RECOVERED",
            metadata={
                "recovered_amount": outcome.recovered_amount,
                "action_cost": outcome.action_cost,
                "reasoning_summary": agent_rec.reasoning_summary,
            },
        )

        return {
            "decision_id": decision_id,
            "status": "EXECUTED",
            "recommended_action": action_to_execute.value,
            "reasoning": agent_rec.reasoning_summary,
            "policy_result": policy_eval.result.value,
            "outcome": outcome.model_dump(mode="json"),
        }
