"""Integration tests — exercise the coordinator + subagent + tool loop together
with only the external boundaries (classify, write_audit_event, Anthropic client) mocked."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ticket_triage.coordinator import coordinator
from ticket_triage.schemas import Classification
from ticket_triage.subagents import RESPONSE_TOOL_NAME


def test_coordinator_dispatches_billing_ticket_end_to_end(
    monkeypatch, install_classify, recorded_log
):
    install_classify(
        Classification(
            domain="billing", confidence=0.9, reasoning="refund request"
        )
    )

    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name=RESPONSE_TOOL_NAME,
                input={
                    "status": "resolved",
                    "reply_draft": "Refund processed.",
                    "evidence": [],
                },
                id="tool-1",
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    reply = coordinator("I want a refund on ORD-001")

    assert reply.status == "resolved"
    assert reply.text == "Refund processed."
    assert fake_client.messages.create.call_count == 1


def test_coordinator_dispatches_technical_ticket_end_to_end(
    monkeypatch, install_classify, recorded_log
):
    install_classify(
        Classification(domain="technical", confidence=0.9, reasoning="connectivity issue")
    )

    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name=RESPONSE_TOOL_NAME,
                input={"status": "resolved", "reply_draft": "Issue diagnosed.", "evidence": []},
                id="tool-1",
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    reply = coordinator("App keeps crashing on login")

    assert reply.status == "resolved"
    assert reply.text == "Issue diagnosed."


def test_coordinator_dispatches_refund_ticket_end_to_end(
    monkeypatch, install_classify, recorded_log
):
    install_classify(
        Classification(domain="refund", confidence=0.9, reasoning="refund eligibility")
    )

    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name=RESPONSE_TOOL_NAME,
                input={"status": "resolved", "reply_draft": "Refund approved.", "evidence": []},
                id="tool-1",
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    reply = coordinator("I want my money back for ORD-001")

    assert reply.status == "resolved"
    assert reply.text == "Refund approved."


def test_technical_agent_calls_search_docs_then_resolves_end_to_end(
    monkeypatch, install_classify, recorded_log
):
    """Technical subagent retrieves from product docs before responding.
    Verifies the full loop: coordinator → technical subagent → search_docs
    tool call → submit_response."""
    install_classify(
        Classification(domain="technical", confidence=0.9, reasoning="login issue")
    )

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name="search_docs",
                    input={"query": "cannot log in to my account"},
                    id="tool-search",
                )
            ],
            stop_reason="tool_use",
        ),
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name=RESPONSE_TOOL_NAME,
                    input={
                        "status": "resolved",
                        "reply_draft": "Per our docs, locked accounts unlock after 30 minutes.",
                        "evidence": [],
                    },
                    id="tool-response",
                )
            ],
            stop_reason="tool_use",
        ),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    reply = coordinator("I cannot log in to my account")

    assert reply.status == "resolved"
    assert reply.text == "Per our docs, locked accounts unlock after 30 minutes."
    assert fake_client.messages.create.call_count == 2
