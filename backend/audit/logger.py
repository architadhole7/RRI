from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
import uuid

from backend.ingestion.schemas import AuditLogEntry, BlockedActionRecord, PolicyResultType, RecoveryAction

logger = logging.getLogger("revenueguard")

GENESIS_HASH = "0" * 64


class AuditLogger:
    """Logs tamper-evident, structured audit trails for all recovery decisioning and orchestration events."""

    def __init__(self, log_file: str = "data/audit_trail.jsonl"):
        self.log_file = log_file
        self.logs: list[AuditLogEntry] = []
        self.last_hash: str = GENESIS_HASH
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        self._load_existing_logs()

    def _load_existing_logs(self) -> None:
        """Loads existing audit entries from disk and restores the latest hash chain state."""
        log_path = Path(self.log_file)
        if not log_path.exists():
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    entry = AuditLogEntry.model_validate(data)
                    entry.previous_hash = self.last_hash
                    action_val = entry.selected_action.value if entry.selected_action else None
                    policy_val = entry.policy_result.value if entry.policy_result else None
                    entry.current_hash = self._compute_entry_hash(
                        previous_hash=entry.previous_hash,
                        entry_id=entry.entry_id,
                        timestamp_iso=entry.timestamp.isoformat(),
                        transaction_id=entry.transaction_id,
                        event_type=entry.event_type,
                        selected_action=action_val,
                        policy_result=policy_val,
                        execution_result=entry.execution_result,
                        metadata=entry.metadata,
                    )
                    self.logs.append(entry)
                    self.last_hash = entry.current_hash
        except Exception as e:
            logger.warning("Could not fully reload audit trail from disk: %s", str(e))

    def _canonical_timestamp(self, ts: datetime | str) -> str:
        if isinstance(ts, str):
            return ts.replace("+00:00", "Z")
        return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _compute_entry_hash(
        self,
        previous_hash: str,
        entry_id: str,
        timestamp_iso: str,
        transaction_id: str,
        event_type: str,
        selected_action: str | None,
        policy_result: str | None,
        execution_result: str | None,
        metadata: dict[str, Any],
    ) -> str:
        """Computes deterministic SHA-256 hash over canonical audit fields."""
        canon_ts = self._canonical_timestamp(timestamp_iso)
        canonical_str = (
            f"{previous_hash}|{entry_id}|{canon_ts}|{transaction_id}|"
            f"{event_type}|{selected_action or ''}|{policy_result or ''}|"
            f"{execution_result or ''}|{json.dumps(metadata, sort_keys=True)}"
        )
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def log_event(
        self,
        transaction_id: str,
        event_type: str,
        decision_id: str | None = None,
        selected_action: RecoveryAction | None = None,
        policy_result: PolicyResultType | None = None,
        execution_result: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogEntry:
        entry_id = f"aud_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        masked_meta = self._mask_pii(metadata or {})

        action_val = selected_action.value if selected_action else None
        policy_val = policy_result.value if policy_result else None

        prev_hash = self.last_hash
        curr_hash = self._compute_entry_hash(
            previous_hash=prev_hash,
            entry_id=entry_id,
            timestamp_iso=now.isoformat(),
            transaction_id=transaction_id,
            event_type=event_type,
            selected_action=action_val,
            policy_result=policy_val,
            execution_result=execution_result,
            metadata=masked_meta,
        )

        entry = AuditLogEntry(
            entry_id=entry_id,
            timestamp=now,
            transaction_id=transaction_id,
            decision_id=decision_id,
            event_type=event_type,
            selected_action=selected_action,
            policy_result=policy_result,
            execution_result=execution_result,
            metadata=masked_meta,
            previous_hash=prev_hash,
            current_hash=curr_hash,
        )

        self.logs.append(entry)
        self.last_hash = curr_hash
        self._write_to_disk(entry)

        logger.info(
            "AUDIT LOG [%s] %s | Transaction: %s | Result: %s | Hash: %s",
            event_type,
            entry_id,
            transaction_id,
            execution_result,
            curr_hash[:10],
        )
        return entry

    def verify_integrity(self) -> tuple[bool, str | None]:
        """Validates the complete SHA-256 tamper-evident hash chain.
        
        Returns (True, None) if valid, or (False, reason) if any record was modified or deleted.
        """
        expected_prev_hash = GENESIS_HASH

        for idx, entry in enumerate(self.logs):
            if entry.previous_hash != expected_prev_hash:
                return (
                    False,
                    f"Hash chain broken at index {idx} (entry {entry.entry_id}): "
                    f"expected previous_hash '{expected_prev_hash}', got '{entry.previous_hash}'",
                )

            action_val = entry.selected_action.value if entry.selected_action else None
            policy_val = entry.policy_result.value if entry.policy_result else None
            timestamp_iso = entry.timestamp.isoformat()

            recomputed_hash = self._compute_entry_hash(
                previous_hash=entry.previous_hash,
                entry_id=entry.entry_id,
                timestamp_iso=timestamp_iso,
                transaction_id=entry.transaction_id,
                event_type=entry.event_type,
                selected_action=action_val,
                policy_result=policy_val,
                execution_result=entry.execution_result,
                metadata=entry.metadata,
            )

            if entry.current_hash != recomputed_hash:
                return (
                    False,
                    f"Tampered record at index {idx} (entry {entry.entry_id}): "
                    f"stored current_hash '{entry.current_hash}' != recomputed '{recomputed_hash}'",
                )

            expected_prev_hash = entry.current_hash

        return True, None

    def _mask_pii(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Masks sensitive customer and authorization info in audit metadata."""
        masked = dict(meta)
        sensitive_keys = [
            "card_number",
            "cvv",
            "phone",
            "email",
            "secret",
            "password",
            "api_key",
            "token",
            "auth",
            "credentials",
        ]
        for k in list(masked.keys()):
            if any(sk in k.lower() for sk in sensitive_keys):
                masked[k] = "***MASKED***"
        return masked

    def _write_to_disk(self, entry: AuditLogEntry) -> None:
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.model_dump(mode="json")) + "\n")
        except Exception as e:
            logger.error("Failed to append audit log to disk: %s", str(e))

    def get_logs_for_transaction(self, transaction_id: str) -> list[AuditLogEntry]:
        return [entry for entry in self.logs if entry.transaction_id == transaction_id]

    def get_all_logs(self, limit: int = 100) -> list[AuditLogEntry]:
        return list(reversed(self.logs[-limit:]))

    def get_blocked_actions(self, limit: int = 100) -> list[BlockedActionRecord]:
        """Extracts blocked actions from the audit trail."""
        blocked = []
        for entry in reversed(self.logs):
            is_blocked = (
                entry.policy_result == PolicyResultType.DENY
                or entry.event_type in (
                    "KILL_SWITCH_BLOCKED",
                    "SECURITY_THREAT_DETECTED",
                    "IDEMPOTENCY_BLOCKED",
                    "POLICY_DENIED",
                )
                or (entry.execution_result and "BLOCKED" in entry.execution_result.upper())
            )
            if is_blocked:
                amount = float(entry.metadata.get("amount", 0.0) or 0.0)
                reason = (
                    entry.metadata.get("reason")
                    or ("; ".join(entry.metadata.get("threats", [])) if "threats" in entry.metadata else None)
                    or ("; ".join(entry.metadata.get("violations", [])) if "violations" in entry.metadata else None)
                    or entry.execution_result
                    or "Policy violation"
                )
                attempted = entry.selected_action.value if entry.selected_action else "UNKNOWN"
                blocked.append(
                    BlockedActionRecord(
                        transaction_id=entry.transaction_id,
                        amount=amount,
                        attempted_action=attempted,
                        guard_decision=entry.policy_result.value if entry.policy_result else "DENY",
                        reason=str(reason),
                        timestamp=entry.timestamp,
                    )
                )
                if len(blocked) >= limit:
                    break
        return blocked
