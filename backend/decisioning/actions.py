from backend.ingestion.schemas import RecoveryAction

ALL_CANDIDATE_ACTIONS = [
    RecoveryAction.RETRY_NOW,
    RecoveryAction.RETRY_LATER,
    RecoveryAction.NOTIFY_CUSTOMER,
    RecoveryAction.ESCALATE,
    RecoveryAction.STOP,
]

ACTION_DESCRIPTIONS = {
    RecoveryAction.RETRY_NOW: "Immediate automated retry through payment gateway",
    RecoveryAction.RETRY_LATER: "Scheduled retry after optimal cooldown window (24h)",
    RecoveryAction.NOTIFY_CUSTOMER: "Send automated payment recovery notification via SMS/Email",
    RecoveryAction.ESCALATE: "Escalate transaction to merchant operations for manual outreach",
    RecoveryAction.STOP: "Cease recovery interventions to prevent unnecessary costs or customer friction",
}
