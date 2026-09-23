import pytest
from pydantic import ValidationError

from ticket_triage.schemas import AgentOutcome


def test_resolved_outcome_requires_reply_draft():
    with pytest.raises(ValidationError):
        AgentOutcome(status="resolved", reply_draft=None)


def test_escalate_outcome_requires_escalation_reason():
    with pytest.raises(ValidationError):
        AgentOutcome(status="escalate", escalation_reason=None)


def test_resolved_outcome_accepts_reply_draft():
    outcome = AgentOutcome(status="resolved", reply_draft="Your issue has been resolved.")
    assert outcome.reply_draft is not None


def test_escalate_outcome_accepts_escalation_reason():
    outcome = AgentOutcome(status="escalate", escalation_reason="Requires human review.")
    assert outcome.escalation_reason is not None


def test_needs_info_outcome_is_valid_without_reply_draft():
    outcome = AgentOutcome(status="needs_info")
    assert outcome.status == "needs_info"


def test_failed_outcome_is_valid_without_reply_draft():
    outcome = AgentOutcome(status="failed")
    assert outcome.status == "failed"
