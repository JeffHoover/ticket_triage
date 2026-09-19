from typing import Literal

from pydantic import BaseModel, Field


class Classification(BaseModel):
    domain: Literal["billing", "technical", "refund", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SubagentResult(BaseModel):
    status: Literal["resolved", "needs_info", "escalate", "failed"]
    reply_draft: str | None = None
    evidence: list[dict] = Field(default_factory=list)
    escalation_reason: str | None = None


class Reply(BaseModel):
    text: str | None
    status: Literal["resolved", "needs_info", "escalated"]
    escalation_reason: str | None = None
