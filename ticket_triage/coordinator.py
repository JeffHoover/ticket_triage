from typing import Callable

from anthropic import Anthropic

from ticket_triage.observability import write_audit_event
from ticket_triage.schemas import AgentOutcome, Classification, TriageReply
from ticket_triage.subagents import CLASSIFIER_MODEL, billing_agent, refund_agent, technical_agent

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client

CONFIDENCE_THRESHOLD = 0.7
MAX_RETRIES = 2

SUBAGENTS: dict[str, Callable[..., AgentOutcome]] = {
    "billing": billing_agent,
    "technical": technical_agent,
    "refund": refund_agent,
}


_CLASSIFY_SYSTEM = (
    "Classify the support ticket into exactly one domain. "
    "Respond with a JSON object matching this schema: "
    '{"domain": "billing"|"technical"|"refund"|"unknown", '
    '"confidence": 0.0-1.0, "reasoning": "string"}. '
    "No other text."
)


def classify(ticket: str) -> Classification:
    client = _get_client()
    response = client.messages.create(
        model=CLASSIFIER_MODEL,
        max_tokens=256,
        system=_CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": ticket}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return Classification.model_validate_json(text)


def escalate(ticket: str, reason: str, **context) -> TriageReply:
    write_audit_event("escalated", ticket=ticket, reason=reason, **context)
    return TriageReply(text="Your ticket has been escalated.", status="escalated", escalation_reason=reason)


def retry_or_escalate(
    ticket: str, classification: Classification, retry_count: int
) -> TriageReply:
    if retry_count > MAX_RETRIES:
        return escalate(
            ticket,
            reason="repeated_failure",
            classification=classification,
            attempts=retry_count,
        )

    write_audit_event(
        "retry_attempted",
        retry_count=retry_count,
        ticket=ticket,
        domain=classification.domain,
    )
    agent_outcome = SUBAGENTS[classification.domain](ticket, classification)
    write_audit_event("returned", domain=classification.domain, **agent_outcome.model_dump())
    if agent_outcome.status == "failed":
        return retry_or_escalate(
            ticket, classification, retry_count=retry_count + 1
        )
    if agent_outcome.status == "escalate":
        return escalate(
            ticket, reason=agent_outcome.escalation_reason, evidence=agent_outcome.evidence
        )
    return TriageReply(text=agent_outcome.reply_draft, status=agent_outcome.status)

def coordinator(ticket: str) -> TriageReply:
    write_audit_event("received", ticket=ticket)

    classification = classify(ticket)
    write_audit_event("classified", **classification.model_dump())

    if (
        classification.domain == "unknown"
        or classification.confidence < CONFIDENCE_THRESHOLD
    ):
        return escalate(ticket, reason="low_confidence", classification=classification)

    agent_outcome = SUBAGENTS[classification.domain](ticket, classification)
    write_audit_event("returned", domain=classification.domain, **agent_outcome.model_dump())

    if agent_outcome.status == "escalate":
        return escalate(
            ticket, reason=agent_outcome.escalation_reason, evidence=agent_outcome.evidence
        )
    if agent_outcome.status == "failed":
        return retry_or_escalate(ticket, classification, retry_count=1)

    return TriageReply(
        text=agent_outcome.reply_draft,
        status="resolved" if agent_outcome.status == "resolved" else "needs_info",
    )
