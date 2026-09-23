from ticket_triage.coordinator import outcome_to_reply
from ticket_triage.schemas import AgentOutcome


def test_resolved_outcome_becomes_resolved_reply():
    outcome = AgentOutcome(status="resolved", reply_draft="Your issue is fixed.")
    reply = outcome_to_reply(outcome)
    assert reply.status == "resolved"
    assert reply.text == "Your issue is fixed."


def test_needs_info_outcome_becomes_needs_info_reply():
    outcome = AgentOutcome(status="needs_info", reply_draft="Can you provide more details?")
    reply = outcome_to_reply(outcome)
    assert reply.status == "needs_info"
    assert reply.text == "Can you provide more details?"
