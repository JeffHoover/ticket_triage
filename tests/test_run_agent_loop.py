"""Tests documenting FIXED behavioral gaps in run_agent_loop.

Each test asserts the correct behavior; 
These are the targets for the AgentLoop
refactor (REVIEW_RESPONSE.md findings 2, 5, 6, 7, 8).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from ticket_triage.schemas import Classification
from ticket_triage.subagents import RESPONSE_TOOL_NAME, _response_input_schema, billing_agent

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

# ── Mutant 161 ─────────────────────────────────────────────────────────────
# The retry path is only entered when submit_response has no domain tools
# alongside it (guarded by `if not domain_blocks:`). So `tool_use_blocks`
# contains only submit_response blocks. The condition `block.name == RESPONSE_TOOL_NAME`
# on line 167 must route the block to the validation-error result. Inverting it
# (`!=`) sends submit_response to `else:` → dispatches it (not in registry →
# None → "Tool execution failed.") instead of the validation error.

def test_validation_retry_result_contains_validation_error_not_tool_failure(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        # Only submit_response with invalid input — no domain tools, so the
        # retry path (`if not domain_blocks:`) is entered.
        _message_response([
            _tool_use_block(RESPONSE_TOOL_NAME, {"status": "not_a_real_status"}, "tool-bad"),
        ]),
        _resolved_submit("tool-final"),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_agent("ticket", CLASSIFICATION)

    retry_turn = fake_client.messages.create.call_args_list[1].kwargs["messages"][-1]
    result_by_id = {entry["tool_use_id"]: entry for entry in retry_turn["content"]}

    assert "Validation error" in result_by_id["tool-bad"]["content"]


# ── Mutant 197 ──────────────────────────────────────────────────────────────
# `continue` → `break` in the main tool-dispatch loop. When submit_response
# appears before a domain tool in the response, `break` exits the loop and the
# domain tool is never dispatched.

def test_domain_tool_dispatched_when_submit_response_appears_first_in_block(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _message_response([
            _tool_use_block(
                RESPONSE_TOOL_NAME,
                {"status": "resolved", "reply_draft": "Done.", "evidence": []},
                "tool-response",
            ),
            _tool_use_block("find_order_by_id", {"order_id": "ORD-001"}, "tool-domain"),
        ]),
        _resolved_submit("tool-final"),
    ]
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_agent("ticket", CLASSIFICATION)

    assert fake_client.messages.create.call_count == 2
    second_call_turn = fake_client.messages.create.call_args_list[1].kwargs["messages"][-1]
    tool_result_ids = {entry["tool_use_id"] for entry in second_call_turn["content"]}
    assert "tool-domain" in tool_result_ids


# ── Live-run fix: tool_choice=any ──────────────────────────────────────────
# Without tool_choice={"type": "any"}, the model can return end_turn with no
# tool_use blocks. The loop's raise RuntimeError was never hit in tests because
# mock responses always included tool_use blocks.

def test_run_agent_loop_passes_tool_choice_any(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _resolved_submit()
    monkeypatch.setattr("ticket_triage.subagents._client", fake_client)

    billing_agent("ticket", CLASSIFICATION)

    assert fake_client.messages.create.call_args.kwargs["tool_choice"] == {"type": "any"}


# ── Live-run fix: flat submit_response input_schema ────────────────────────
# AGENT_OUTCOME_ADAPTER.json_schema() produces a top-level oneOf discriminated
# union. The Anthropic API rejects top-level oneOf in tool input_schema.
# We hand-write a flat object schema instead; Pydantic still validates the
# model's actual tool call via AGENT_OUTCOME_ADAPTER.validate_python().

def test_response_tool_schema_has_object_type_at_top_level():
    assert _response_input_schema.get("type") == "object"


def test_response_tool_schema_has_no_top_level_oneof():
    assert "oneOf" not in _response_input_schema


def test_response_tool_schema_has_required_properties_key():
    assert "properties" in _response_input_schema


def test_response_tool_schema_status_is_required():
    assert "status" in _response_input_schema["required"]


def test_response_tool_schema_status_enum_contains_all_variants():
    enum = _response_input_schema["properties"]["status"]["enum"]
    assert set(enum) == {"resolved", "needs_info", "escalate", "failed"}


# ── Finding 8 ──────────────────────────────────────────────────────────────
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
