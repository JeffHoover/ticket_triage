"""Tests for the technical subagent.

Same agentic-loop contract as billing_agent: resolve via submit_response,
dispatch domain tools, retry on invalid output, exhaust retries → failed.
Technical agent only has find_order_by_id (read-only); issue_refund is out of scope.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ticket_triage.schemas import AgentOutcomeBase, Classification
from ticket_triage.subagents import (
    MAX_VALIDATION_RETRIES,
    RESPONSE_TOOL_NAME,
    billing_agent,
    refund_agent,
    technical_agent,
)

CLASSIFICATION = Classification(
    domain="technical", confidence=0.9, reasoning="clear technical signal"
)


def _tool_use_block(name: str, tool_input: dict, block_id: str = "test-tool-1"):
    return SimpleNamespace(
        type="tool_use", name=name, input=tool_input, id=block_id
    )


def _message_response(content_blocks: list, stop_reason: str):
    return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)


def test_technical_agent_returns_result_when_model_immediately_calls_response_tool(
    monkeypatch,
):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            _tool_use_block(
                name=RESPONSE_TOOL_NAME,
                tool_input={
                    "status": "resolved",
                    "reply_draft": "Your connection issue has been resolved.",
                    "evidence": [],
                },
            )
        ],
        stop_reason="tool_use",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = technical_agent("My app keeps crashing", CLASSIFICATION)

    assert isinstance(result, AgentOutcomeBase)
    assert result.status == "resolved"
    assert result.reply_draft == "Your connection issue has been resolved."


def test_technical_agent_executes_find_order_by_id_then_returns_response(monkeypatch):
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
                    name=RESPONSE_TOOL_NAME,
                    tool_input={
                        "status": "resolved",
                        "reply_draft": "Order ORD-001 found; issue diagnosed.",
                        "evidence": [],
                    },
                )
            ],
            stop_reason="tool_use",
        ),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = technical_agent("Can you check ORD-001?", CLASSIFICATION)

    assert result.status == "resolved"
    assert fake_client.messages.create.call_count == 2


def test_technical_agent_retries_when_submit_response_has_invalid_input(monkeypatch):
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

    result = technical_agent("ticket", CLASSIFICATION)

    assert result.status == "resolved"
    assert fake_client.messages.create.call_count == 2


def test_technical_agent_returns_failed_when_validation_retries_exhausted(monkeypatch):
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

    result = technical_agent("ticket", CLASSIFICATION)

    assert result.status == "failed"
    assert fake_client.messages.create.call_count == MAX_VALIDATION_RETRIES + 1


def test_technical_agent_raises_when_model_returns_no_tool_use(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response(
        content_blocks=[
            SimpleNamespace(type="text", text="I don't know what to do")
        ],
        stop_reason="end_turn",
    )
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    with pytest.raises(RuntimeError):
        technical_agent("ticket", CLASSIFICATION)


def test_technical_agent_does_not_have_issue_refund_tool(monkeypatch):
    """issue_refund is billing/refund domain only — must not appear in technical agent tools."""
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

    technical_agent("ticket", CLASSIFICATION)

    kwargs = fake_client.messages.create.call_args.kwargs
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert "issue_refund" not in tool_names
    assert "find_order_by_id" in tool_names


def _resolved_response():
    return _message_response(
        content_blocks=[
            _tool_use_block(
                name=RESPONSE_TOOL_NAME,
                tool_input={"status": "resolved", "reply_draft": "Done.", "evidence": []},
            )
        ],
        stop_reason="tool_use",
    )


def test_technical_agent_includes_search_docs_tool(monkeypatch):
    """search_docs is wired into the technical subagent — it is the only subagent
    with access to product-doc retrieval."""
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _resolved_response()
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    technical_agent("ticket", CLASSIFICATION)

    tool_names = {t["name"] for t in fake_client.messages.create.call_args.kwargs["tools"]}
    assert "search_docs" in tool_names


def test_billing_agent_does_not_include_search_docs_tool(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _resolved_response()
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_classification = Classification(
        domain="billing", confidence=0.9, reasoning="billing"
    )
    billing_agent("ticket", billing_classification)

    tool_names = {t["name"] for t in fake_client.messages.create.call_args.kwargs["tools"]}
    assert "search_docs" not in tool_names


def test_refund_agent_does_not_include_search_docs_tool(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _resolved_response()
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    refund_classification = Classification(
        domain="refund", confidence=0.9, reasoning="refund"
    )
    refund_agent("ticket", refund_classification)

    tool_names = {t["name"] for t in fake_client.messages.create.call_args.kwargs["tools"]}
    assert "search_docs" not in tool_names
