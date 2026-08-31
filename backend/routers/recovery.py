from datetime import datetime, timezone
import logging
from typing import Any
import uuid
from fastapi import APIRouter, HTTPException, Query, status
from backend.audit.logger import AuditLogger
from backend.ingestion.loaders import load_dataset
from backend.ingestion.schemas import (
    BlockedActionRecord,
    Customer,
    HumanApprovalRequest,
    Payment,
    PaymentFailure,
    PolicyResultType,
    RecoveryAction,
    RecoveryEvaluationRequest,
    RecoverySimulationRequest,
)
from backend.orchestrator.executor import ActionExecutor
from backend.routers.payments import payments_db
from backend.simulator.recovery import RecoverySimulator

logger = logging.getLogger("revenueguard")

router = APIRouter(prefix="/recovery", tags=["Recovery"])

executor = ActionExecutor()
simulator = RecoverySimulator()


customers_db: dict[str, Customer] = {}


@router.post("/demo/transaction")
def create_demo_transaction() -> dict[str, Any]:
    """Generates a controlled high-value failed transaction that triggers the full decisioning and human approval flow."""
    demo_id = f"pay_demo_{uuid.uuid4().hex[:6]}"
    cust_id = "cust_demo_vip"

    customer = Customer(
        customer_id=cust_id,
        merchant_id="mer_001",
        payment_method="CARD",
        total_successful_payments=15,
        total_failed_payments=1,
        consent_to_contact=True,
        subscription_status="ACTIVE",
        avg_transaction_value=12500.0,
        risk_score=0.15,
        contact_count=0,
    )
    customers_db[cust_id] = customer

    payment = Payment(
        payment_id=demo_id,
        merchant_id="mer_001",
        customer_id=cust_id,
        amount=12500.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        failure_code="ERR_INSUFFICIENT_FUNDS",
        created_at=datetime.now(timezone.utc),
        retry_count=0,
        attempt_number=1,
    )
    payments_db[demo_id] = payment

    # Process through full end-to-end pipeline
    res = executor.process_failed_payment(payment=payment, customer=customer)
    return {
        "payment_id": demo_id,
        "amount": payment.amount,
        "customer_id": cust_id,
        "status": res.get("status"),
        "decision_id": res.get("decision_id"),
        "approval_id": res.get("approval_id"),
        "recommended_action": res.get("recommended_action"),
        "reason": res.get("reason"),
    }


@router.post("/demo/blocked")
def create_demo_blocked_scenario() -> dict[str, Any]:
    """Generates a controlled unsafe recovery scenario that triggers a deterministic policy block."""
    demo_id = f"pay_block_{uuid.uuid4().hex[:6]}"
    cust_id = "cust_opted_out"

    customer = Customer(
        customer_id=cust_id,
        merchant_id="mer_001",
        payment_method="UPI",
        total_successful_payments=2,
        total_failed_payments=4,
        consent_to_contact=False,  # Explicitly opted out
        subscription_status="CANCELLED",
        avg_transaction_value=3500.0,
        risk_score=0.85,
        contact_count=3,
    )
    customers_db[cust_id] = customer

    payment = Payment(
        payment_id=demo_id,
        merchant_id="mer_001",
        customer_id=cust_id,
        amount=3500.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_EXCEED_RETRY_LIMIT",
        created_at=datetime.now(timezone.utc),
        retry_count=4,  # Hard retry limit exceeded (4 >= 3)
        attempt_number=5,
    )
    payments_db[demo_id] = payment

    res = executor.process_failed_payment(payment=payment, customer=customer)
    status_str = "BLOCKED" if (res.get("policy_result") == "DENY" or res.get("status") in ("BLOCKED", "SECURITY_BLOCKED")) else res.get("status")

    return {
        "payment_id": demo_id,
        "amount": payment.amount,
        "customer_id": cust_id,
        "status": status_str,
        "guard_decision": "DENY",
        "decision_id": res.get("decision_id"),
        "recommended_action": res.get("recommended_action", "STOP"),
        "reason": "Deterministic Policy DENY: Retry limit exceeded (4 >= 3); Customer opted out of contact",
    }


@router.post("/evaluate")
def evaluate_recovery(request: RecoveryEvaluationRequest) -> dict[str, Any]:
    payment_id = request.payment_id
    payment = payments_db.get(payment_id)
    if not payment:
        dataset = load_dataset()
        payment = dataset.get("payments", {}).get(payment_id)

    if not payment:
        payment = Payment(
            payment_id=payment_id,
            merchant_id=request.merchant_id or "mer_001",
            customer_id="cust_001",
            amount=2500.0,
            currency="INR",
            payment_method="CARD",
            status="FAILED",
            failure_code=request.failure_code or "ERR_INSUFFICIENT_FUNDS",
            created_at=datetime.now(timezone.utc),
        )

    res = executor.process_failed_payment(payment)
    return res


@router.post("/simulate")
def simulate_recovery(request: RecoverySimulationRequest) -> dict[str, Any]:
    payment = payments_db.get(request.payment_id)
    if not payment:
        dataset = load_dataset()
        payment = dataset.get("payments", {}).get(request.payment_id)

    if not payment:
        payment = Payment(
            payment_id=request.payment_id,
            merchant_id="mer_001",
            customer_id="cust_001",
            amount=1500.0,
            currency="INR",
            payment_method="UPI",
            status="FAILED",
            failure_code="ERR_NETWORK_TIMEOUT",
            created_at=datetime.now(timezone.utc),
        )

    outcomes = []
    actions = request.simulation_scenarios or ["RETRY_NOW", "RETRY_LATER", "NOTIFY_CUSTOMER", "STOP"]
    for act in actions:
        out = simulator.simulate_action(payment, act)
        outcomes.append(out.model_dump(mode="json"))

    return {
        "payment_id": payment.payment_id,
        "scenarios": outcomes,
    }


@router.post("/execute")
def execute_recovery(payment: Payment) -> dict[str, Any]:
    payments_db[payment.payment_id] = payment
    res = executor.process_failed_payment(payment)
    return res


@router.get("/approvals", response_model=list[HumanApprovalRequest])
def list_approvals(merchant_id: str | None = None, include_reviewed: bool = False):
    if include_reviewed:
        requests = list(executor.approval_manager.pending_approvals.values())
        if merchant_id:
            requests = [r for r in requests if r.merchant_id == merchant_id]
        return requests
    return executor.approval_manager.get_pending_approvals(merchant_id)


@router.post("/approvals/{approval_id}/review", response_model=HumanApprovalRequest)
def review_approval(approval_id: str, approve: bool, reviewer: str = "Merchant Operations Admin"):
    try:
        req = executor.approval_manager.review_approval(approval_id, approve, reviewer=reviewer)

        # Look up payment and customer
        payment = payments_db.get(req.payment_id)
        if not payment:
            dataset = load_dataset()
            payment = dataset.get("payments", {}).get(req.payment_id)

        customer = customers_db.get(payment.customer_id if payment else "")
        if not customer:
            dataset = load_dataset()
            customer = dataset.get("customers", {}).get(payment.customer_id if payment else "")

        if approve and payment:
            outcome = executor.simulator.simulate_action(payment, req.action, customer)
            payment.status = "RECOVERED" if outcome.recovered else "FAILED"
            executor.audit_logger.log_event(
                transaction_id=req.payment_id,
                event_type="APPROVAL_RESOLVED_APPROVED",
                selected_action=req.action,
                policy_result=PolicyResultType.ALLOW,
                execution_result="RECOVERED" if outcome.recovered else "NOT_RECOVERED",
                metadata={
                    "approval_id": approval_id,
                    "reviewer": reviewer,
                    "amount": req.amount,
                    "recovered_amount": outcome.recovered_amount,
                },
            )
        else:
            if payment:
                payment.status = "BLOCKED"
            executor.audit_logger.log_event(
                transaction_id=req.payment_id,
                event_type="APPROVAL_RESOLVED_DENIED",
                selected_action=req.action,
                policy_result=PolicyResultType.DENY,
                execution_result="BLOCKED_BY_MERCHANT_DENIAL",
                metadata={
                    "approval_id": approval_id,
                    "reviewer": reviewer,
                    "amount": req.amount,
                    "reason": "Merchant operator denied recovery intervention",
                },
            )

        return req
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")


@router.get("/blocked", response_model=list[BlockedActionRecord])
def list_blocked_actions(limit: int = Query(default=100, ge=1, le=500)):
    """Returns all blocked transactions with violation reasons and guard decisions."""
    blocked = executor.audit_logger.get_blocked_actions(limit=limit)
    return blocked


@router.get("/transactions")
def list_transactions(
    status_filter: str = Query(default="ALL", alias="status"),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Provides a searchable, filterable transaction explorer with real operational data."""
    dataset = load_dataset()
    payments_map = dataset.get("payments", {})
    failures_map = dataset.get("failures", {})

    # Ensure payments_db has baseline dataset
    if not payments_db:
        for p_id, p in payments_map.items():
            payments_db[p_id] = p

    # Sort payments: demo/recent payments first
    def get_sort_key(p: Payment):
        if hasattr(p.created_at, "timestamp"):
            return p.created_at.timestamp()
        try:
            return datetime.fromisoformat(str(p.created_at)).timestamp()
        except Exception:
            return 0.0

    all_payments = sorted(payments_db.values(), key=get_sort_key, reverse=True)

    # Enrich and filter
    results = []
    for p in all_payments:
        fail = failures_map.get(p.payment_id)
        fail_cat = fail.failure_category.value if fail else (p.failure_code or "UNKNOWN")

        # Search match
        if search:
            q = search.lower()
            if q not in p.payment_id.lower() and q not in p.customer_id.lower() and q not in fail_cat.lower():
                continue

        # Real-time Status Resolution
        approval_req = next((a for a in executor.approval_manager.pending_approvals.values() if a.payment_id == p.payment_id), None)

        if approval_req:
            if approval_req.status == "PENDING":
                txn_status = "NEEDS_HUMAN_APPROVAL"
            elif approval_req.status == "APPROVED":
                txn_status = "RECOVERED" if p.status == "RECOVERED" else "EXECUTED"
            elif approval_req.status == "REJECTED":
                txn_status = "BLOCKED"
            else:
                txn_status = p.status
        elif p.status == "RECOVERED":
            txn_status = "RECOVERED"
        elif p.retry_count >= 3:
            txn_status = "BLOCKED"
        elif p.amount >= 5000:
            txn_status = "NEEDS_HUMAN_APPROVAL"
        else:
            txn_status = "EXECUTED"

        if status_filter != "ALL" and txn_status != status_filter.upper():
            continue

        results.append({
            "payment_id": p.payment_id,
            "merchant_id": p.merchant_id,
            "customer_id": p.customer_id,
            "amount": p.amount,
            "currency": p.currency,
            "payment_method": p.payment_method,
            "failure_code": p.failure_code or "ERR_UNKNOWN",
            "failure_category": fail_cat,
            "retry_count": p.retry_count,
            "status": txn_status,
            "created_at": p.created_at.isoformat() if hasattr(p.created_at, "isoformat") else str(p.created_at),
        })

    paginated = results[offset : offset + limit]
    return {
        "total": len(results),
        "offset": offset,
        "limit": limit,
        "transactions": paginated,
    }


@router.get("/transaction/{payment_id}/journey")
def get_transaction_journey(payment_id: str) -> dict[str, Any]:
    """Returns the full 10-step explainable decision journey for a given payment."""
    dataset = load_dataset()
    payments_map = dataset.get("payments", {})
    failures_map = dataset.get("failures", {})
    customers_map = dataset.get("customers", {})

    payment = payments_db.get(payment_id) or payments_map.get(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment '{payment_id}' not found",
        )

    failure = failures_map.get(payment_id)
    customer = customers_db.get(payment.customer_id) or customers_map.get(payment.customer_id)

    # 1. Failure Diagnosis
    cat, conf = executor.diagnoser.diagnose(payment.failure_code, payment=payment)
    if failure is None:
        failure = PaymentFailure(
            payment_id=payment.payment_id,
            failure_code=payment.failure_code or "UNKNOWN",
            failure_category=cat,
            occurred_at=payment.created_at,
            confidence=conf,
        )

    # 2. Decision Engine Candidate Action Scoring
    decision_result = executor.decision_engine.make_decision(
        payment=payment, failure=failure, customer=customer
    )

    # 3. Policy Evaluation
    policy_eval = executor.policy_engine.evaluate_action(
        payment=payment, action=decision_result.recommended_action, customer=customer
    )

    # 4. Agent Reasoning
    agent_rec = executor.agent.evaluate_and_recommend(
        payment=payment,
        decision_result=decision_result,
        policy_eval=policy_eval,
        failure=failure,
        customer=customer,
    )

    # 5. Outcome Simulation
    outcome = executor.simulator.simulate_action(
        payment=payment,
        action=agent_rec.recommended_action,
        customer=customer,
        failure=failure,
    )

    # 6. Audit Trail
    audit_logs = executor.audit_logger.get_logs_for_transaction(payment_id)

    return {
        "payment": payment.model_dump(mode="json"),
        "diagnosis": {
            "failure_category": cat.value,
            "confidence": conf,
            "raw_code": payment.failure_code,
            "human_readable": cat.value.replace("_", " ").title(),
        },
        "candidate_actions": [c.model_dump(mode="json") for c in decision_result.candidate_actions],
        "recommended_action": agent_rec.recommended_action.value,
        "selected_expected_value": decision_result.selected_value,
        "reasoning_summary": agent_rec.reasoning_summary,
        "policy_evaluation": policy_eval.model_dump(mode="json"),
        "outcome": outcome.model_dump(mode="json"),
        "audit_trail": [a.model_dump(mode="json") for a in audit_logs],
    }


