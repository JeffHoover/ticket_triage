import pytest

from ticket_triage.schemas import Classification, Reply, SubagentResult


@pytest.fixture
def stubs(monkeypatch):
    recorded = {"escalate": [], "log": [], "subagent": []}

    def fake_escalate(ticket, reason, **context):
        recorded["escalate"].append({"ticket": ticket, "reason": reason, **context})
        return Reply(text=None, status="escalated", escalation_reason=reason)

    def fake_log(event, **fields):
        recorded["log"].append({"event": event, **fields})

    def fake_subagent(ticket, classification):
        recorded["subagent"].append(
            {"ticket": ticket, "classification": classification}
        )
        return SubagentResult(status="resolved", reply_draft="handled")

    monkeypatch.setattr("ticket_triage.coordinator.escalate", fake_escalate)
    monkeypatch.setattr("ticket_triage.coordinator.log", fake_log)
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

    def fake_log(event, **fields):
        events.append({"event": event, **fields})

    monkeypatch.setattr("ticket_triage.coordinator.log", fake_log)
    return events


@pytest.fixture
def observability_environment(monkeypatch):
    """Environment for observability contract tests — real escalate (so its log fires), captured log, queue-driven subagent."""
    events: list[dict] = []
    subagent_calls: list[dict] = []
    subagent_responses: list[SubagentResult] = []

    def fake_log(event, **fields):
        events.append({"event": event, **fields})

    def fake_subagent(ticket, classification):
        subagent_calls.append({"ticket": ticket, "classification": classification})
        if not subagent_responses:
            raise AssertionError(
                "Test bug: fake_subagent called with no queued response"
            )
        return subagent_responses.pop(0)

    monkeypatch.setattr("ticket_triage.coordinator.log", fake_log)
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
    subagent_responses: list[SubagentResult] = []
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
        return Reply(text=None, status="escalated", escalation_reason=reason)

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
        "ticket_triage.coordinator.log", lambda event, **fields: None
    )

    return {
        "queue": subagent_responses,
        "subagent_calls": subagent_calls,
        "escalate_calls": escalate_calls,
    }
