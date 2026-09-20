from ticket_triage.coordinator import CONFIDENCE_THRESHOLD, MAX_RETRIES, coordinator
from ticket_triage.schemas import Classification, SubagentResult


def event_names(events: list[dict]) -> list[str]:
    return [event["event"] for event in events]


def test_happy_path_emits_received_classified_returned(
    observability_environment, install_classify
):
    install_classify(
        Classification(domain="billing", confidence=0.9, reasoning="clear")
    )
    observability_environment["queue"].append(
        SubagentResult(status="resolved", reply_draft="ok")
    )

    coordinator("ticket text")

    events = observability_environment["events"]
    assert event_names(events) == ["received", "classified", "returned"]
    assert events[0]["ticket"] == "ticket text"
    assert events[1]["domain"] == "billing"
    assert events[2]["domain"] == "billing"


def test_low_confidence_gate_emits_received_classified_escalated(
    observability_environment, install_classify
):
    install_classify(
        Classification(
            domain="billing",
            confidence=CONFIDENCE_THRESHOLD - 0.01,
            reasoning="borderline",
        )
    )

    coordinator("ticket text")

    assert event_names(observability_environment["events"]) == [
        "received",
        "classified",
        "escalated",
    ]


def test_unknown_domain_gate_emits_received_classified_escalated(
    observability_environment, install_classify
):
    install_classify(
        Classification(domain="unknown", confidence=0.99, reasoning="unclear")
    )

    coordinator("ticket text")

    assert event_names(observability_environment["events"]) == [
        "received",
        "classified",
        "escalated",
    ]


def test_needs_info_path_emits_received_classified_returned(
    observability_environment, install_classify
):
    install_classify(
        Classification(domain="billing", confidence=0.9, reasoning="clear")
    )
    observability_environment["queue"].append(
        SubagentResult(status="needs_info", reply_draft="please clarify")
    )

    coordinator("ticket text")

    assert event_names(observability_environment["events"]) == [
        "received",
        "classified",
        "returned",
    ]


def test_subagent_escalate_emits_received_classified_returned_escalated(
    observability_environment, install_classify
):
    install_classify(
        Classification(domain="billing", confidence=0.9, reasoning="clear")
    )
    observability_environment["queue"].append(
        SubagentResult(
            status="escalate",
            escalation_reason="policy_violation",
            evidence=[],
        )
    )

    coordinator("ticket text")

    assert event_names(observability_environment["events"]) == [
        "received",
        "classified",
        "returned",
        "escalated",
    ]


def test_fail_then_success_emits_retry_attempted_between_returns(
    observability_environment, install_classify
):
    install_classify(
        Classification(domain="billing", confidence=0.9, reasoning="clear")
    )
    observability_environment["queue"].extend(
        [
            SubagentResult(status="failed"),
            SubagentResult(status="resolved", reply_draft="fixed on retry"),
        ]
    )

    coordinator("ticket text")

    assert event_names(observability_environment["events"]) == [
        "received",
        "classified",
        "returned",
        "retry_attempted",
        "returned",
    ]


def test_exhausted_retries_emit_full_retry_trail_then_escalated(
    observability_environment, install_classify
):
    install_classify(
        Classification(domain="billing", confidence=0.9, reasoning="clear")
    )
    for _ in range(MAX_RETRIES + 1):
        observability_environment["queue"].append(SubagentResult(status="failed"))

    coordinator("ticket text")

    assert event_names(observability_environment["events"]) == [
        "received",
        "classified",
        "returned",
        "retry_attempted",
        "returned",
        "retry_attempted",
        "returned",
        "escalated",
    ]
