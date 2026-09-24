from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class Classification(BaseModel):
    domain: Literal["billing", "technical", "refund", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class AgentOutcomeBase(BaseModel):
    """Marker base class — enables isinstance checks across all AgentOutcome variants."""


class ResolvedOutcome(AgentOutcomeBase):
    status: Literal["resolved"] = "resolved"
    reply_draft: str
    evidence: list[dict] = Field(default_factory=list)


class NeedsInfoOutcome(AgentOutcomeBase):
    status: Literal["needs_info"] = "needs_info"
    reply_draft: str | None = None
    evidence: list[dict] = Field(default_factory=list)


class EscalateOutcome(AgentOutcomeBase):
    status: Literal["escalate"] = "escalate"
    escalation_reason: str
    evidence: list[dict] = Field(default_factory=list)


class FailedOutcome(AgentOutcomeBase):
    status: Literal["failed"] = "failed"


AgentOutcome = Annotated[
    Union[ResolvedOutcome, NeedsInfoOutcome, EscalateOutcome, FailedOutcome],
    Field(discriminator="status"),
]

AGENT_OUTCOME_ADAPTER = TypeAdapter(AgentOutcome)


class TriageReply(BaseModel):
    text: str | None
    status: Literal["resolved", "needs_info", "escalated"]
    escalation_reason: str | None = None
