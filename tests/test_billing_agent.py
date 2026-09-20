from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ticket_triage.schemas import Classification, SubagentResult
from ticket_triage.subagents import (
    MAX_VALIDATION_RETRIES,
    RESPONSE_TOOL_NAME,
    billing_agent,
)

CLASSIFICATION = Classification(
    domain="billing", confidence=0.9, reasoning="clear billing signal"
)


def _tool_use_block(name: str, tool_input: dict, block_id: str = "test-tool-1"):
    return SimpleNamespace(
        type="tool_use", name=name, input=tool_input, id=block_id
    )


def _message_response(content_blocks: list, stop_reason: str):
    return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)


def test_billing_agent_returns_result_when_model_immediately_calls_response_tool(
    monkeypatch,
):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            _tool_use_block(
                name=RESPONSE_TOOL_NAME,
                tool_input={
                    "status": "resolved",
                    "reply_draft": "Your refund has been processed.",
                    "evidence": [],
                },
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = billing_agent("I want a refund on ORD-001", CLASSIFICATION)

    assert isinstance(result, SubagentResult)
    assert result.status == "resolved"
    assert result.reply_draft == "Your refund has been processed."


def test_billing_agent_executes_domain_tool_then_returns_response(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name="look_up_order",
                    tool_input={"order_id": "ORD-001"},
                    block_id="tool-1",
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
                        "reply_draft": "Order ORD-001 shipped on time.",
                        "evidence": [],
                    },
                )
            ],
            stop_reason="tool_use",
        ),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = billing_agent("Status of ORD-001?", CLASSIFICATION)

    assert result.status == "resolved"
    assert result.reply_draft == "Order ORD-001 shipped on time."
    assert fake_client.messages.create.call_count == 2


def test_billing_agent_retries_when_submit_response_has_invalid_input(
    monkeypatch,
):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _message_response(
            content_blocks=[
                _tool_use_block(
                    name=RESPONSE_TOOL_NAME,
                    tool_input={
                        "status": "not_a_real_status",
                        "reply_draft": "x",
                    },
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

    result = billing_agent("ticket", CLASSIFICATION)

    assert result.status == "resolved"
    assert result.reply_draft == "Fixed on retry."
    assert fake_client.messages.create.call_count == 2


def test_billing_agent_returns_failed_status_when_validation_retries_exhausted(
    monkeypatch,
):
    def invalid_response():
        return _message_response(
            content_blocks=[
                _tool_use_block(
                    name=RESPONSE_TOOL_NAME,
                    tool_input={
                        "status": "not_a_real_status",
                        "reply_draft": "x",
                    },
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

    result = billing_agent("ticket", CLASSIFICATION)

    assert result.status == "failed"
    assert fake_client.messages.create.call_count == MAX_VALIDATION_RETRIES + 1


def test_billing_agent_raises_when_model_returns_no_tool_use(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            SimpleNamespace(type="text", text="I don't know what to do")
        ],
        stop_reason="end_turn",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    with pytest.raises(RuntimeError):
        billing_agent("ticket", CLASSIFICATION)
