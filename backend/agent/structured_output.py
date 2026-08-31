from pydantic import BaseModel, Field
from backend.ingestion.schemas import AgentRecommendation, RecoveryAction


class AgentResponsePayload(BaseModel):
    recommended_action: RecoveryAction
    reasoning_summary: str = Field(description="Concise summary explaining why this action is recommended")
    key_signals: list[str] = Field(default_factory=list, description="Key empirical signals influencing the decision")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    def to_domain_recommendation(self) -> AgentRecommendation:
        return AgentRecommendation(
            recommended_action=self.recommended_action,
            reasoning_summary=self.reasoning_summary,
            key_signals=self.key_signals,
            confidence=self.confidence,
        )
