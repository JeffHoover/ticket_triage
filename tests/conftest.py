import sys
from pathlib import Path

import pytest

from ticket_triage.schemas import AgentOutcomeBase, Classification, ResolvedOutcome, TriageReply

# Find the project root by walking up until we find the `hooks/` directory.
# A fixed parent.parent would resolve to mutants/ when mutmut runs tests,
# so we search upward to stay correct regardless of nesting depth.
_here = Path(__file__).resolve()
_project_root = next(p for p in [_here, *_here.parents] if (p / "hooks").is_dir())
sys.path.insert(0, str(_project_root))


@pytest.fixture
def stubs(monkeypatch):
    recorded = {"escalate": [], "write_audit_event": [], "subagent": []}

    def fake_escalate(ticket, reason, **context):
        recorded["escalate"].append({"ticket": ticket, "reason": reason, **context})
        return TriageReply(text=None, status="escalated", escalation_reason=reason)

    def fake_write_audit_event(event, **fields):
        recorded["write_audit_event"].append({"event": event, **fields})

    def fake_subagent(ticket, classification):
        recorded["subagent"].append(
            {"ticket": ticket, "classification": classification}
        )
        return ResolvedOutcome(reply_draft="handled")

    monkeypatch.setattr("ticket_triage.coordinator.escalate", fake_escalate)
    monkeypatch.setattr("ticket_triage.coordinator.write_audit_event", fake_write_audit_event)
    monkeypatch.setattr(
        "ticket_triage.coordinator.SUBAGENTS",
        {
            "billing": fake_subagent,
            "technical": fake_subagent,
            "refund": fake_subagent,
        },
    )
    return recorded


@pytest.fixture
def install_classify(monkeypatch):
    def _install(classification: Classification) -> None:
        def fake_classify(ticket):
            return classification

        monkeypatch.setattr("ticket_triage.coordinator.classify", fake_classify)

    return _install


@pytest.fixture
def recorded_log(monkeypatch):
    events = []

    def fake_write_audit_event(event, **fields):
        events.append({"event": event, **fields})

    monkeypatch.setattr("ticket_triage.coordinator.write_audit_event", fake_write_audit_event)
    return events


@pytest.fixture
def distinct_subagents(monkeypatch):
    """Each domain gets its own recording stub — for testing per-domain routing."""
    call_log: dict[str, list[dict]] = {
        "billing": [],
        "technical": [],
        "refund": [],
    }

    def make_stub(domain):
        def stub(ticket, classification):
            call_log[domain].append(
                {"ticket": ticket, "classification": classification}
            )
            return ResolvedOutcome(reply_draft=f"{domain} handled")

        return stub

    monkeypatch.setattr(
        "ticket_triage.coordinator.SUBAGENTS",
        {domain: make_stub(domain) for domain in call_log},
    )
    monkeypatch.setattr(
        "ticket_triage.coordinator.write_audit_event", lambda event, **fields: None
    )
    return call_log


@pytest.fixture
def observability_environment(monkeypatch):
    """Environment for observability contract tests — real escalate (so its log fires), captured log, queue-driven subagent."""
    events: list[dict] = []
    subagent_calls: list[dict] = []
    subagent_responses: list[AgentOutcomeBase] = []

    def fake_write_audit_event(event, **fields):
        events.append({"event": event, **fields})

    def fake_subagent(ticket, classification):
        subagent_calls.append({"ticket": ticket, "classification": classification})
        if not subagent_responses:
            raise AssertionError(
                "Test bug: fake_subagent called with no queued response"
            )
        return subagent_responses.pop(0)

    monkeypatch.setattr("ticket_triage.coordinator.write_audit_event", fake_write_audit_event)
    monkeypatch.setattr(
        "ticket_triage.coordinator.SUBAGENTS",
        {
            "billing": fake_subagent,
            "technical": fake_subagent,
            "refund": fake_subagent,
        },
    )

    return {
        "events": events,
        "queue": subagent_responses,
        "subagent_calls": subagent_calls,
    }


@pytest.fixture
def retry_environment(monkeypatch):
    """Queue-driven subagent + stubbed escalate — for retry_or_escalate tests."""
    subagent_calls: list[dict] = []
    subagent_responses: list[AgentOutcomeBase] = []
    escalate_calls: list[dict] = []

    def fake_subagent(ticket, classification):
        subagent_calls.append({"ticket": ticket, "classification": classification})
        if not subagent_responses:
            raise AssertionError(
                "Test bug: fake_subagent called with no queued response"
            )
        return subagent_responses.pop(0)

    def fake_escalate(ticket, reason, **context):
        escalate_calls.append({"ticket": ticket, "reason": reason, **context})
        return TriageReply(text=None, status="escalated", escalation_reason=reason)

    monkeypatch.setattr(
        "ticket_triage.coordinator.SUBAGENTS",
        {
            "billing": fake_subagent,
            "technical": fake_subagent,
            "refund": fake_subagent,
        },
    )
    monkeypatch.setattr("ticket_triage.coordinator.escalate", fake_escalate)
    monkeypatch.setattr(
        "ticket_triage.coordinator.write_audit_event", lambda event, **fields: None
    )

    return {
        "queue": subagent_responses,
        "subagent_calls": subagent_calls,
        "escalate_calls": escalate_calls,
    }
