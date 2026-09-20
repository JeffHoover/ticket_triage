from types import SimpleNamespace
from unittest.mock import MagicMock

from ticket_triage.schemas import Classification, SubagentResult
from ticket_triage.subagents import RESPONSE_TOOL_NAME, billing_agent

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
