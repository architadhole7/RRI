from typing import Any
from fastapi import APIRouter
from backend.security.kill_switch import KillSwitchManager

router = APIRouter(prefix="/security", tags=["Security"])
kill_switch = KillSwitchManager()


@router.get("/kill-switch")
def get_kill_switch_status() -> dict[str, Any]:
    return {"active": kill_switch.is_active()}


@router.post("/kill-switch/toggle")
def toggle_kill_switch(enable: bool, reason: str = "Manual security toggle") -> dict[str, Any]:
    if enable:
        kill_switch.enable(reason)
    else:
        kill_switch.disable()
    return {"active": kill_switch.is_active(), "message": f"Kill switch {'activated' if enable else 'deactivated'}"}
