import os
from backend.audit.logger import AuditLogger
from backend.ingestion.schemas import PolicyResultType, RecoveryAction


def test_audit_logger_masks_pii():
    log_file = "data/test_audit_log.jsonl"
    if os.path.exists(log_file):
        os.remove(log_file)

    logger = AuditLogger(log_file=log_file)
    entry = logger.log_event(
        transaction_id="pay_audit_1",
        event_type="TEST_ACTION",
        selected_action=RecoveryAction.RETRY_NOW,
        policy_result=PolicyResultType.ALLOW,
        execution_result="SUCCESS",
        metadata={
            "card_number": "4111111111111111",
            "cvv": "123",
            "amount": 2500.0,
        },
    )

    assert entry.metadata["card_number"] == "***MASKED***"
    assert entry.metadata["cvv"] == "***MASKED***"
    assert entry.metadata["amount"] == 2500.0

    if os.path.exists(log_file):
        os.remove(log_file)
