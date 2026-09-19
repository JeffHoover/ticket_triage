from ticket_triage.coordinator import CONFIDENCE_THRESHOLD, coordinator
from ticket_triage.schemas import Classification


def test_low_confidence_escalates_and_skips_dispatch(stubs, install_classify):
    install_classify(
        Classification(
            domain="billing",
            confidence=CONFIDENCE_THRESHOLD - 0.01,
            reasoning="borderline",
        )
    )

    reply = coordinator("customer message")

    assert reply.status == "escalated"
    assert len(stubs["escalate"]) == 1
    assert stubs["escalate"][0]["reason"] == "low_confidence"
    assert stubs["subagent"] == []


def test_unknown_domain_escalates_regardless_of_confidence(stubs, install_classify):
    install_classify(
        Classification(domain="unknown", confidence=0.99, reasoning="unclear")
    )

    reply = coordinator("customer message")

    assert reply.status == "escalated"
    assert stubs["escalate"][0]["reason"] == "low_confidence"
    assert stubs["subagent"] == []
