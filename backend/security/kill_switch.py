import logging
import threading

logger = logging.getLogger("revenueguard")


class KillSwitchManager:
    """Thread-safe global emergency shut-off switch for RevenueGuard system."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.enabled = False
            return cls._instance

    def enable(self, reason: str = "Manual emergency shutoff triggered") -> None:
        with self._lock:
            self.enabled = True
            logger.critical("KILL SWITCH ACTIVATED: %s", reason)

    def disable(self) -> None:
        with self._lock:
            self.enabled = False
            logger.info("KILL SWITCH DEACTIVATED: Automated recovery resumed")

    def is_active(self) -> bool:
        with self._lock:
            return self.enabled
