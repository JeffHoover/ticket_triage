from typing import Callable

from ticket_triage.schemas import Classification, Reply, SubagentResult

CONFIDENCE_THRESHOLD = 0.7
MAX_RETRIES = 2

SUBAGENTS: dict[str, Callable[[str, Classification], SubagentResult]] = {}


def classify(ticket: str) -> Classification:
    raise NotImplementedError


def escalate(ticket: str, reason: str, **context) -> Reply:
    log("escalated", ticket=ticket, reason=reason, **context)
    return Reply(text="Your ticket has been escalated.", status="escalated", escalation_reason=reason)


def retry_or_escalate(
    ticket: str, classification: Classification, retry_count: int
) -> Reply:
    if retry_count > MAX_RETRIES:
        return escalate(
            ticket,
            reason="repeated_failure",
            classification=classification,
            attempts=retry_count,
        )

    log(
        "retry_attempted",
        retry_count=retry_count,
        ticket=ticket,
        domain=classification.domain,
    )
    result = SUBAGENTS[classification.domain](ticket, classification)
    log("returned", domain=classification.domain, **result.model_dump())
    if result.status == "failed":
        return retry_or_escalate(
            ticket, classification, retry_count=retry_count + 1
        )
    if result.status == "escalate":
        return escalate(
            ticket, reason=result.escalation_reason, evidence=result.evidence
        )
    return Reply(text=result.reply_draft, status=result.status)

def log(event: str, **fields) -> None:
    raise NotImplementedError


def coordinator(ticket: str) -> Reply:
    log("received", ticket=ticket)

    classification = classify(ticket)
    log("classified", **classification.model_dump())

    if (
        classification.domain == "unknown"
        or classification.confidence < CONFIDENCE_THRESHOLD
    ):
        return escalate(ticket, reason="low_confidence", classification=classification)

    result = SUBAGENTS[classification.domain](ticket, classification)
    log("returned", domain=classification.domain, **result.model_dump())

    if result.status == "escalate":
        return escalate(
            ticket, reason=result.escalation_reason, evidence=result.evidence
        )
    if result.status == "failed":
        return retry_or_escalate(ticket, classification, retry_count=1)

    return Reply(
        text=result.reply_draft,
        status="resolved" if result.status == "resolved" else "needs_info",
    )
