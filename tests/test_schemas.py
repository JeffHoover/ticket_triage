import pytest
from pydantic import ValidationError

from ticket_triage.schemas import (
    AGENT_OUTCOME_ADAPTER,
    AgentOutcome,
    AgentOutcomeBase,
    EscalateOutcome,
    FailedOutcome,
    NeedsInfoOutcome,
    ResolvedOutcome,
)


def test_resolved_outcome_requires_reply_draft():
    with pytest.raises(ValidationError):
        ResolvedOutcome(reply_draft=None)


def test_escalate_outcome_requires_escalation_reason():
    with pytest.raises(ValidationError):
        EscalateOutcome(escalation_reason=None)


def test_resolved_outcome_accepts_reply_draft():
    outcome = ResolvedOutcome(reply_draft="Your issue has been resolved.")
    assert outcome.reply_draft is not None


def test_escalate_outcome_accepts_escalation_reason():
    outcome = EscalateOutcome(escalation_reason="Requires human review.")
    assert outcome.escalation_reason is not None


def test_needs_info_outcome_is_valid_without_reply_draft():
    outcome = NeedsInfoOutcome()
    assert outcome.status == "needs_info"


def test_failed_outcome_is_valid_without_reply_draft():
    outcome = FailedOutcome()
    assert outcome.status == "failed"


# --- Finding 4: discriminated-union variant tests ---


def test_resolved_parses_to_resolved_type():
    outcome = AGENT_OUTCOME_ADAPTER.validate_python({"status": "resolved", "reply_draft": "Fixed."})
    assert isinstance(outcome, ResolvedOutcome)


def test_escalate_parses_to_escalate_type():
    outcome = AGENT_OUTCOME_ADAPTER.validate_python({"status": "escalate", "escalation_reason": "Needs human."})
    assert isinstance(outcome, EscalateOutcome)


def test_needs_info_parses_to_needs_info_type():
    outcome = AGENT_OUTCOME_ADAPTER.validate_python({"status": "needs_info"})
    assert isinstance(outcome, NeedsInfoOutcome)


def test_failed_parses_to_failed_type():
    outcome = AGENT_OUTCOME_ADAPTER.validate_python({"status": "failed"})
    assert isinstance(outcome, FailedOutcome)


def test_resolved_outcome_has_no_escalation_reason_field():
    outcome = AGENT_OUTCOME_ADAPTER.validate_python({"status": "resolved", "reply_draft": "Fixed."})
    assert isinstance(outcome, ResolvedOutcome)
    assert not hasattr(outcome, "escalation_reason")


def test_escalate_outcome_has_no_reply_draft_field():
    outcome = AGENT_OUTCOME_ADAPTER.validate_python({"status": "escalate", "escalation_reason": "Needs human."})
    assert isinstance(outcome, EscalateOutcome)
    assert not hasattr(outcome, "reply_draft")


def test_resolved_reply_draft_is_required_str():
    """reply_draft must be str (not str | None) on ResolvedOutcome."""
    with pytest.raises(ValidationError):
        ResolvedOutcome()


def test_escalate_escalation_reason_is_required_str():
    """escalation_reason must be str (not str | None) on EscalateOutcome."""
    with pytest.raises(ValidationError):
        EscalateOutcome()


def test_all_variants_are_agent_outcome_base_instances():
    assert isinstance(ResolvedOutcome(reply_draft="ok"), AgentOutcomeBase)
    assert isinstance(NeedsInfoOutcome(), AgentOutcomeBase)
    assert isinstance(EscalateOutcome(escalation_reason="x"), AgentOutcomeBase)
    assert isinstance(FailedOutcome(), AgentOutcomeBase)
