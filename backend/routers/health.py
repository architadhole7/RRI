import logging

from fastapi import APIRouter

from backend.config import settings
from backend.security.kill_switch import KillSwitchManager

logger = logging.getLogger("revenueguard")

router = APIRouter(tags=["Health"])
kill_switch = KillSwitchManager()


@router.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "healthy"}


@router.get("/system/status")
def system_status():
    """Returns system safety status, operator configuration, and subsystem operational metrics."""
    return {
        "status": "operational",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "operator": {
            "name": settings.operator_name,
            "role": settings.operator_role,
            "auth_status": "configured_identity",
            "auth_note": "Authentication intentionally deferred for MVP",
        },
        "safety": {
            "policy_engine": "ACTIVE",
            "kill_switch_active": kill_switch.is_active(),
            "deterministic_guards": True,
            "human_approval_gate": True,
            "tamper_evident_audit": "ACTIVE",
        },
    }

