import logging
from typing import Any
from fastapi import APIRouter, Query
from backend.audit.logger import AuditLogger
from backend.ingestion.schemas import AuditLogEntry

from backend.routers.recovery import executor

logger = logging.getLogger("revenueguard")

router = APIRouter(prefix="/audit", tags=["Audit"])

audit_logger = executor.audit_logger



@router.get("/logs", response_model=list[AuditLogEntry])
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)):
    """Returns recent audit log records with tamper-evident hash metadata."""
    return audit_logger.get_all_logs(limit=limit)


@router.get("/verify")
def verify_audit_chain() -> dict[str, Any]:
    """Cryptographically verifies the SHA-256 tamper-evident audit hash chain."""
    valid, reason = audit_logger.verify_integrity()
    return {
        "verified": valid,
        "status": "VALID" if valid else "TAMPERED",
        "total_records": len(audit_logger.logs),
        "latest_hash": audit_logger.last_hash,
        "detail": reason or "All cryptographic hash chain links verified intact.",
    }


@router.get("/transaction/{transaction_id}", response_model=list[AuditLogEntry])
def get_transaction_audit_trail(transaction_id: str):
    """Returns all audit events associated with a specific payment transaction."""
    return audit_logger.get_logs_for_transaction(transaction_id)
