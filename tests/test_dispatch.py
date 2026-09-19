import pytest

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


@pytest.mark.parametrize("domain", ["billing", "technical", "refund"])
def test_each_domain_routes_to_its_own_subagent(
    distinct_subagents, install_classify, domain
):
    install_classify(
        Classification(domain=domain, confidence=0.9, reasoning="test")
    )

    coordinator("some ticket")

    assert len(distinct_subagents[domain]) == 1
    assert distinct_subagents[domain][0]["ticket"] == "some ticket"
    for other_domain in distinct_subagents:
        if other_domain != domain:
            assert distinct_subagents[other_domain] == []
