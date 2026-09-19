from ticket_triage.coordinator import escalate
from ticket_triage.schemas import Classification


def test_escalate_returns_reply_with_escalated_status(recorded_log):
    reply = escalate("customer ticket text", reason="low_confidence")

    assert reply.status == "escalated"
    assert reply.escalation_reason == "low_confidence"


def test_escalate_reply_includes_customer_facing_text(recorded_log):
    reply = escalate("customer ticket text", reason="low_confidence")

    assert reply.text is not None
    assert reply.text.strip() != ""


def test_escalate_emits_log_event_with_ticket_and_reason(recorded_log):
    escalate("customer ticket text", reason="policy_violation")

    escalated_events = [event for event in recorded_log if event["event"] == "escalated"]
    assert len(escalated_events) == 1
    assert escalated_events[0]["ticket"] == "customer ticket text"
    assert escalated_events[0]["reason"] == "policy_violation"


def test_escalate_log_event_includes_passed_context(recorded_log):
    classification = Classification(
        domain="refund", confidence=0.9, reasoning="wants money back"
    )

    escalate("ticket text", reason="policy_violation", classification=classification)

    escalated_events = [event for event in recorded_log if event["event"] == "escalated"]
    assert escalated_events[0]["classification"] == classification
