import json
import os
from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel

from ticket_triage.schemas import Classification, Reply, SubagentResult


def _json_default(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )

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
    path = os.environ.get("TICKET_TRIAGE_LOG_PATH", "ticket_triage.log.jsonl")
    entry = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    with open(path, "a") as output_file:
        output_file.write(json.dumps(entry, default=_json_default) + "\n")


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
