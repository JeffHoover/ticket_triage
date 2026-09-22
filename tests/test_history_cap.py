from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ticket_triage.schemas import Classification
from ticket_triage.subagents import MAX_HISTORY_MESSAGES, RESPONSE_TOOL_NAME, billing_agent

CLASSIFICATION = Classification(
    domain="billing", confidence=0.9, reasoning="billing"
)


def _tool_use_block(name: str, tool_input: dict, block_id: str = "tool-1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)


def _message_response(content_blocks: list, stop_reason: str = "tool_use"):
    return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)


def _find_order_by_id_response(block_id: str):
    return _message_response(
        content_blocks=[
            _tool_use_block(
                name="find_order_by_id",
                tool_input={"order_id": "ORD-001"},
                block_id=block_id,
            )
        ]
    )


def _submit_response():
    return _message_response(
        content_blocks=[
            _tool_use_block(
                name=RESPONSE_TOOL_NAME,
                tool_input={"status": "resolved", "reply_draft": "Done.", "evidence": []},
            )
        ]
    )


def test_run_agent_loop_caps_message_history_by_dropping_oldest_tool_result_pairs(
    monkeypatch,
):
    """
    run_agent_loop must drop oldest assistant+tool-result pairs — not arbitrary
    turns — once messages exceeds MAX_HISTORY_MESSAGES, so that:
      1. messages[0] (the original ticket) is always preserved.
      2. client.messages.create is never called with more than
         MAX_HISTORY_MESSAGES messages.
      3. Roles always alternate user/assistant (no orphaned turns from
         dropping half a pair).

    Pairs are dropped rather than arbitrary turns because the Messages API
    requires strict user/assistant alternation — removing a single turn
    orphans its counterpart and makes the next API call invalid.
    """
    # Each tool round adds 2 messages (assistant + user/tool-results).
    # After (MAX_HISTORY_MESSAGES // 2) + 1 rounds the raw count exceeds
    # the cap, so we need at least that many rounds to exercise truncation.
    num_tool_rounds = (MAX_HISTORY_MESSAGES // 2) + 2

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _find_order_by_id_response(block_id=f"tool-{i}") for i in range(num_tool_rounds)
    ] + [_submit_response()]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = billing_agent("Refund ORD-001", CLASSIFICATION)

    assert result.status == "resolved"

    for call_index, call_kwargs in enumerate(fake_client.messages.create.call_args_list):
        messages_sent = call_kwargs.kwargs["messages"]

        assert len(messages_sent) <= MAX_HISTORY_MESSAGES, (
            f"Call {call_index}: expected at most {MAX_HISTORY_MESSAGES} messages, "
            f"got {len(messages_sent)}"
        )

        # messages[0] is always the original ticket
        assert messages_sent[0]["role"] == "user"

        # roles must alternate user/assistant starting from index 0
        for i, msg in enumerate(messages_sent):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role, (
                f"Call {call_index}, messages[{i}]: "
                f"role={msg['role']!r}, expected {expected_role!r}"
            )
