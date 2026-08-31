from datetime import datetime, timezone
import logging
from backend.ingestion.schemas import Payment
from backend.security.validation import InputSanitizer

logger = logging.getLogger("revenueguard")


class ThreatDetector:
    """Detects security threats including prompt injections, transaction replays, and excessive retries."""

    def __init__(self):
        self.sanitizer = InputSanitizer()
        self.seen_payment_ids: set[str] = set()

    def inspect_payment_request(self, payment: Payment, raw_message: str | None = None) -> list[str]:
        threats: list[str] = []

        # 1. Prompt Injection Detection
        if raw_message and not self.sanitizer.is_safe_string(raw_message):
            threats.append("PROMPT_INJECTION_ATTEMPT: Malicious override pattern detected in request message")
            logger.warning("Threat detected: Prompt injection in message '%s'", raw_message)

        # 2. Replay Detection
        if payment.payment_id in self.seen_payment_ids:
            threats.append(f"REPLAY_EVENT: Duplicate transaction submission detected for payment_id '{payment.payment_id}'")
            logger.warning("Threat detected: Replay event for payment_id '%s'", payment.payment_id)
        else:
            self.seen_payment_ids.add(payment.payment_id)

        # 3. Excessive Retry Loop Detection
        if payment.retry_count > 5:
            threats.append(f"RETRY_LOOP: Abnormally high retry count ({payment.retry_count}) detected")
            logger.warning("Threat detected: Retry loop for payment_id '%s'", payment.payment_id)

        return threats
