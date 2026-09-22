"""Tests documenting FIXED behavioral gaps in run_agent_loop.

Each test asserts the correct behavior; 
These are the targets for the AgentLoop
refactor (REVIEW_RESPONSE.md findings 2, 5, 6, 7, 8).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from ticket_triage.schemas import Classification
from ticket_triage.subagents import RESPONSE_TOOL_NAME, billing_agent

CLASSIFICATION = Classification(domain="billing", confidence=0.9, reasoning="test")


def _tool_use_block(name: str, tool_input: dict, block_id: str = "tool-1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)


def _message_response(content_blocks: list, stop_reason: str = "tool_use"):
    return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)


def _resolved_submit(block_id: str = "tool-submit"):
    return _message_response([
        _tool_use_block(
            RESPONSE_TOOL_NAME,
            {"status": "resolved", "reply_draft": "Done.", "evidence": []},
            block_id,
        )
    ])


# ── Finding 5a ─────────────────────────────────────────────────────────────
# Unknown tool name crashes with KeyError instead of returning a structured failure.

def test_run_agent_loop_returns_failed_for_unknown_tool_name(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _message_response([
        _tool_use_block("nonexistent_tool", {"foo": "bar"}, "tool-1")
    ])
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = billing_agent("ticket", CLASSIFICATION)

    assert result.status == "failed"


# ── Finding 5b ─────────────────────────────────────────────────────────────
# Malformed tool input crashes with ValidationError instead of returning a structured failure.

def test_run_agent_loop_returns_failed_for_invalid_tool_input(monkeypatch):
    fake_client = MagicMock()
    # FindOrderByIdInput requires order_id with min_length=1; empty string is invalid.
    fake_client.messages.create.return_value = _message_response([
        _tool_use_block("find_order_by_id", {"order_id": ""}, "tool-1")
    ])
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = billing_agent("ticket", CLASSIFICATION)

    assert result.status == "failed"


# ── Finding 2 ──────────────────────────────────────────────────────────────
# When submit_response and a domain tool appear in the same parallel block,
# the loop returns immediately on submit_response and skips the domain tool.

def test_run_agent_loop_executes_domain_tool_when_parallel_with_submit_response(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        # First response: domain tool and submit_response in the same block.
        _message_response([
            _tool_use_block("find_order_by_id", {"order_id": "ORD-001"}, "tool-domain"),
            _tool_use_block(
                RESPONSE_TOOL_NAME,
                {"status": "resolved", "reply_draft": "Done.", "evidence": []},
                "tool-response",
            ),
        ]),
        # Second response: returned after domain tool result is sent back.
        _resolved_submit("tool-final"),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_agent("ticket", CLASSIFICATION)

    # Domain tool must have been dispatched before submit_response was accepted,
    # which requires a second API call with the tool result.
    assert fake_client.messages.create.call_count == 2


# ── Finding 6 ──────────────────────────────────────────────────────────────
# When retrying after an invalid submit_response, only that block gets a tool
# result; other tool_use blocks in the same turn are left without results,
# making the next Messages API request malformed.

def test_run_agent_loop_sends_all_tool_results_when_retrying_invalid_submit_response(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        # First response: domain tool + invalid submit_response in the same block.
        _message_response([
            _tool_use_block("find_order_by_id", {"order_id": "ORD-001"}, "tool-domain"),
            _tool_use_block(RESPONSE_TOOL_NAME, {"status": "not_a_real_status"}, "tool-bad"),
        ]),
        # Second response: valid submit_response after retry.
        _resolved_submit("tool-final"),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_agent("ticket", CLASSIFICATION)

    # The user message preceding the second API call must contain results for
    # every tool_use block in the failed turn, not just the bad submit_response.
    second_call_messages = fake_client.messages.create.call_args_list[1].kwargs["messages"]
    last_user_message = second_call_messages[-1]
    tool_result_ids = {entry["tool_use_id"] for entry in last_user_message["content"]}
    assert "tool-domain" in tool_result_ids
    assert "tool-bad" in tool_result_ids


# ── Finding 7 ──────────────────────────────────────────────────────────────
# SDK/network exceptions propagate uncaught instead of being converted to
# a structured failure that the coordinator can retry or escalate.

def test_run_agent_loop_returns_failed_on_sdk_exception(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = Exception("network timeout")
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    result = billing_agent("ticket", CLASSIFICATION)

    assert result.status == "failed"


# ── Finding 8 ──────────────────────────────────────────────────────────────
# Tool dispatch is not logged. The observability contract in CLAUDE.md says
# every tool call is logged, but run_agent_loop emits no log events.

def test_run_agent_loop_logs_tool_calls(monkeypatch, tmp_path):
    log_path = tmp_path / "triage.jsonl"
    monkeypatch.setenv("TICKET_TRIAGE_LOG_PATH", str(log_path))

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _message_response([
            _tool_use_block("find_order_by_id", {"order_id": "ORD-001"}, "tool-1")
        ]),
        _resolved_submit(),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_agent("ticket", CLASSIFICATION)

    log_events = []
    if log_path.exists():
        log_events = [json.loads(line) for line in log_path.read_text().splitlines()]
    tool_events = [e for e in log_events if e["event"] == "tool_called"]
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "find_order_by_id"
    assert tool_events[0]["tool_use_id"] == "tool-1"
