from datetime import datetime, timezone
import uuid
from backend.ingestion.schemas import HumanApprovalRequest, RecoveryAction


class ApprovalManager:
    """Manages pending, approved, and rejected human approval requests for high-value/flagged interventions."""

    def __init__(self):
        self.pending_approvals: dict[str, HumanApprovalRequest] = {}

    def create_approval_request(
        self,
        payment_id: str,
        merchant_id: str,
        action: RecoveryAction,
        amount: float,
        reason: str,
    ) -> HumanApprovalRequest:
        app_id = f"app_{uuid.uuid4().hex[:8]}"
        request = HumanApprovalRequest(
            approval_id=app_id,
            payment_id=payment_id,
            merchant_id=merchant_id,
            action=action,
            amount=amount,
            reason=reason,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
        )
        self.pending_approvals[app_id] = request
        return request

    def get_pending_approvals(self, merchant_id: str | None = None) -> list[HumanApprovalRequest]:
        requests = list(self.pending_approvals.values())
        if merchant_id:
            requests = [r for r in requests if r.merchant_id == merchant_id]
        return [r for r in requests if r.status == "PENDING"]

    def review_approval(self, approval_id: str, approve: bool, reviewer: str = "merchant_admin") -> HumanApprovalRequest:
        if approval_id not in self.pending_approvals:
            raise KeyError(f"Approval request '{approval_id}' not found")

        req = self.pending_approvals[approval_id]
        req.status = "APPROVED" if approve else "REJECTED"
        req.reviewed_at = datetime.now(timezone.utc)
        req.reviewer = reviewer
        return req
