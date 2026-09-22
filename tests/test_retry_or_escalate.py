from ticket_triage.coordinator import MAX_RETRIES, retry_or_escalate
from ticket_triage.schemas import AgentOutcome, Classification

CLASSIFICATION = Classification(
    domain="billing", confidence=0.9, reasoning="test setup"
)


def test_successful_first_retry_returns_reply(retry_environment):
    retry_environment["queue"].append(
        AgentOutcome(status="resolved", reply_draft="fixed on retry")
    )

    reply = retry_or_escalate("ticket text", CLASSIFICATION, retry_count=1)

    assert reply.status == "resolved"
    assert reply.text == "fixed on retry"
    assert len(retry_environment["subagent_calls"]) == 1
    assert retry_environment["escalate_calls"] == []


def test_failure_then_success_returns_reply(retry_environment):
    retry_environment["queue"].extend(
        [
            AgentOutcome(status="failed"),
            AgentOutcome(status="resolved", reply_draft="fixed on second retry"),
        ]
    )

    reply = retry_or_escalate("ticket text", CLASSIFICATION, retry_count=1)

    assert reply.status == "resolved"
    assert reply.text == "fixed on second retry"
    assert len(retry_environment["subagent_calls"]) == 2
    assert retry_environment["escalate_calls"] == []


def test_exhausted_retries_escalate_with_repeated_failure(retry_environment):
    for _ in range(MAX_RETRIES):
        retry_environment["queue"].append(AgentOutcome(status="failed"))

    reply = retry_or_escalate("ticket text", CLASSIFICATION, retry_count=1)

    assert reply.status == "escalated"
    assert len(retry_environment["subagent_calls"]) == MAX_RETRIES
    assert len(retry_environment["escalate_calls"]) == 1
    escalate_call = retry_environment["escalate_calls"][0]
    assert escalate_call["ticket"] == "ticket text"
    assert escalate_call["reason"] == "repeated_failure"
    assert escalate_call["attempts"] == MAX_RETRIES + 1
    assert escalate_call["classification"] == CLASSIFICATION


def test_guard_escalates_immediately_when_retry_count_exceeds_max(retry_environment):
    reply = retry_or_escalate(
        "ticket text", CLASSIFICATION, retry_count=MAX_RETRIES + 1
    )

    assert reply.status == "escalated"
    assert retry_environment["subagent_calls"] == []
    assert len(retry_environment["escalate_calls"]) == 1
    assert retry_environment["escalate_calls"][0]["reason"] == "repeated_failure"


def test_subagent_escalate_status_forwarded_without_retry(retry_environment):
    retry_environment["queue"].append(
        AgentOutcome(
            status="escalate",
            escalation_reason="policy_violation",
            evidence=[{"tool": "find_order_by_id", "result": "flagged"}],
        )
    )

    reply = retry_or_escalate("ticket text", CLASSIFICATION, retry_count=1)

    assert reply.status == "escalated"
    assert len(retry_environment["subagent_calls"]) == 1
    assert len(retry_environment["escalate_calls"]) == 1
    escalate_call = retry_environment["escalate_calls"][0]
    assert escalate_call["reason"] == "policy_violation"
    assert escalate_call["evidence"] == [
        {"tool": "find_order_by_id", "result": "flagged"}
    ]


def test_needs_info_returned_without_retry(retry_environment):
    retry_environment["queue"].append(
        AgentOutcome(status="needs_info", reply_draft="please clarify")
    )

    reply = retry_or_escalate("ticket text", CLASSIFICATION, retry_count=1)

    assert reply.status == "needs_info"
    assert reply.text == "please clarify"
    assert len(retry_environment["subagent_calls"]) == 1
    assert retry_environment["escalate_calls"] == []
