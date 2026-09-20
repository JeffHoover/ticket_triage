"""Integration tests — exercise the coordinator + subagent + tool loop together
with only the external boundaries (classify, log, Anthropic client) mocked."""

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
