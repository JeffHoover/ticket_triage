"""Tests for the refund-eligibility subagent.

Refund agent has find_order_by_id + issue_refund (same tools as billing,
different system prompt focused on eligibility determination).
Same agentic-loop contract as the other subagents.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ticket_triage.schemas import AgentOutcome, Classification
from ticket_triage.subagents import (
    MAX_VALIDATION_RETRIES,
    RESPONSE_TOOL_NAME,
    refund_agent,
)

CLASSIFICATION = Classification(
    domain="refund", confidence=0.9, reasoning="customer requesting refund"
)


def _tool_use_block(name: str, tool_input: dict, block_id: str = "test-tool-1"):
    return SimpleNamespace(
        type="tool_use", name=name, input=tool_input, id=block_id
    )


def _message_response(content_blocks: list, stop_reason: str):
    return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)


def test_refund_agent_returns_result_when_model_immediately_calls_response_tool(
    monkeypatch,
):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            _tool_use_block(
                name=RESPONSE_TOOL_NAME,
                tool_input={
                    "status": "resolved",
                    "reply_draft": "Your refund of $50 has been approved.",
                    "evidence": [],
                },
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = refund_agent("I want a refund on ORD-001", CLASSIFICATION)

    assert isinstance(result, AgentOutcome)
    assert result.status == "resolved"


def test_refund_agent_executes_find_order_by_id_and_issue_refund_then_responds(
    monkeypatch,
):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name="find_order_by_id",
                    tool_input={"order_id": "ORD-001"},
                    block_id="tool-1",
                )
            ],
            stop_reason="tool_use",
        ),
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name="issue_refund",
                    tool_input={"order_id": "ORD-001", "amount": 50.0, "reason": "damaged"},
                    block_id="tool-2",
                )
            ],
            stop_reason="tool_use",
        ),
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name=RESPONSE_TOOL_NAME,
                    tool_input={
                        "status": "resolved",
                        "reply_draft": "Refund issued for ORD-001.",
                        "evidence": [],
                    },
                )
            ],
            stop_reason="tool_use",
        ),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = refund_agent("Refund ORD-001 $50 damaged item", CLASSIFICATION)

    assert result.status == "resolved"
    assert fake_client.messages.create.call_count == 3


def test_refund_agent_retries_when_submit_response_has_invalid_input(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name=RESPONSE_TOOL_NAME,
                    tool_input={"status": "not_a_real_status", "reply_draft": "x"},
                    block_id="tool-invalid",
                )
            ],
            stop_reason="tool_use",
        ),
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name=RESPONSE_TOOL_NAME,
                    tool_input={
                        "status": "resolved",
                        "reply_draft": "Fixed on retry.",
                        "evidence": [],
                    },
                    block_id="tool-valid",
                )
            ],
            stop_reason="tool_use",
        ),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = refund_agent("ticket", CLASSIFICATION)

    assert result.status == "resolved"
    assert fake_client.messages.create.call_count == 2


def test_refund_agent_returns_failed_when_validation_retries_exhausted(monkeypatch):
    def invalid_response():
        return _message_response(
            content_blocks=[
                _tool_use_block(
                    name=RESPONSE_TOOL_NAME,
                    tool_input={"status": "not_a_real_status", "reply_draft": "x"},
                    block_id="tool-invalid",
                )
            ],
            stop_reason="tool_use",
        )

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        invalid_response() for _ in range(MAX_VALIDATION_RETRIES + 1)
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = refund_agent("ticket", CLASSIFICATION)

    assert result.status == "failed"
    assert fake_client.messages.create.call_count == MAX_VALIDATION_RETRIES + 1


def test_refund_agent_raises_when_model_returns_no_tool_use(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            SimpleNamespace(type="text", text="I don't know what to do")
        ],
        stop_reason="end_turn",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    with pytest.raises(RuntimeError):
        refund_agent("ticket", CLASSIFICATION)


def test_refund_agent_has_both_find_order_by_id_and_issue_refund_tools(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            _tool_use_block(
                name=RESPONSE_TOOL_NAME,
                tool_input={"status": "resolved", "reply_draft": "Done.", "evidence": []},
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    refund_agent("ticket", CLASSIFICATION)

    kwargs = fake_client.messages.create.call_args.kwargs
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert "find_order_by_id" in tool_names
    assert "issue_refund" in tool_names
