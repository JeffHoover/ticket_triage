from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Classification(BaseModel):
    domain: Literal["billing", "technical", "refund", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class AgentOutcome(BaseModel):
    status: Literal["resolved", "needs_info", "escalate", "failed"]
    reply_draft: str | None = None
    evidence: list[dict] = Field(default_factory=list)
    escalation_reason: str | None = None

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "AgentOutcome":
        if self.status == "resolved" and self.reply_draft is None:
            raise ValueError("reply_draft is required when status='resolved'")
        if self.status == "escalate" and self.escalation_reason is None:
            raise ValueError("escalation_reason is required when status='escalate'")
        return self


class TriageReply(BaseModel):
    text: str | None
    status: Literal["resolved", "needs_info", "escalated"]
    escalation_reason: str | None = None
