import json
import pytest
from backend.audit.logger import AuditLogger, GENESIS_HASH
from backend.ingestion.schemas import PolicyResultType, RecoveryAction


def test_audit_hash_chain_creation(tmp_path):
    log_file = str(tmp_path / "test_audit.jsonl")
    audit = AuditLogger(log_file=log_file)

    # 1. First event should chain from GENESIS_HASH
    e1 = audit.log_event(
        transaction_id="pay_001",
        event_type="DECISION_EVALUATED",
        selected_action=RecoveryAction.RETRY_NOW,
        policy_result=PolicyResultType.ALLOW,
        execution_result="SUCCESS",
        metadata={"amount": 1500.0},
    )

    assert e1.previous_hash == GENESIS_HASH
    assert e1.current_hash is not None
    assert len(e1.current_hash) == 64

    # 2. Second event should chain from e1.current_hash
    e2 = audit.log_event(
        transaction_id="pay_002",
        event_type="ACTION_EXECUTED",
        selected_action=RecoveryAction.RETRY_LATER,
        policy_result=PolicyResultType.ALLOW,
        execution_result="RECOVERED",
        metadata={"amount": 2500.0, "card_number": "4111222233334444"},
    )

    assert e2.previous_hash == e1.current_hash
    assert e2.current_hash is not None
    assert e2.metadata["card_number"] == "***MASKED***"

    # Verify integrity
    valid, detail = audit.verify_integrity()
    assert valid is True
    assert detail is None


def test_audit_hash_chain_detects_tampering(tmp_path):
    log_file = str(tmp_path / "test_audit_tamper.jsonl")
    audit = AuditLogger(log_file=log_file)

    audit.log_event(
        transaction_id="pay_001",
        event_type="DECISION_EVALUATED",
        selected_action=RecoveryAction.RETRY_NOW,
        policy_result=PolicyResultType.ALLOW,
    )
    audit.log_event(
        transaction_id="pay_002",
        event_type="DECISION_EVALUATED",
        selected_action=RecoveryAction.STOP,
        policy_result=PolicyResultType.DENY,
    )

    # Validate intact
    valid, _ = audit.verify_integrity()
    assert valid is True

    # Tamper with the first entry's execution result in memory
    audit.logs[0].execution_result = "TAMPERED_RESULT"

    # Verification must now fail and detect the tampered record
    valid, detail = audit.verify_integrity()
    assert valid is False
    assert "Tampered record at index 0" in detail


def test_audit_hash_chain_detects_broken_chain(tmp_path):
    log_file = str(tmp_path / "test_audit_break.jsonl")
    audit = AuditLogger(log_file=log_file)

    audit.log_event(transaction_id="pay_001", event_type="E1")
    audit.log_event(transaction_id="pay_002", event_type="E2")

    # Manually break previous_hash pointer
    audit.logs[1].previous_hash = "f" * 64

    valid, detail = audit.verify_integrity()
    assert valid is False
    assert "Hash chain broken at index 1" in detail
