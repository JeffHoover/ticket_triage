from ticket_triage.coordinator import CONFIDENCE_THRESHOLD, coordinator
from ticket_triage.schemas import Classification


def test_confidence_exactly_at_threshold_dispatches(stubs, install_classify):
    install_classify(
        Classification(
            domain="billing",
            confidence=CONFIDENCE_THRESHOLD,
            reasoning="right at cutoff",
        )
    )

    reply = coordinator("customer message")

    assert reply.status == "resolved"
    assert stubs["escalate"] == []
    assert len(stubs["subagent"]) == 1


def test_confident_known_domain_dispatches(stubs, install_classify):
    install_classify(
        Classification(
            domain="billing", confidence=0.95, reasoning="clearly billing"
        )
    )

    reply = coordinator("charge me twice")

    assert reply.status == "resolved"
    assert stubs["escalate"] == []
    assert stubs["subagent"][0]["ticket"] == "charge me twice"
