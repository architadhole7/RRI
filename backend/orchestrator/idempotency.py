from datetime import datetime, timezone
import hashlib


class IdempotencyStore:
    """Tracks idempotency keys and prevents duplicate action execution."""

    def __init__(self):
        self._keys: dict[str, datetime] = {}

    def generate_key(self, payment_id: str, action: str, retry_count: int) -> str:
        raw = f"{payment_id}:{action}:{retry_count}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def is_duplicate(self, key: str) -> bool:
        return key in self._keys

    def register(self, key: str) -> None:
        self._keys[key] = datetime.now(timezone.utc)
