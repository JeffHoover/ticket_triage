from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from ticket_triage.subagents import _dispatch_tool_call


def _block(name: str, tool_input: dict, block_id: str = "tool-1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)


class _Input(BaseModel):
    value: str


def _make_registry(tool_fn=None):
    fn = tool_fn or MagicMock(return_value=MagicMock(model_dump_json=lambda: '{"ok": true}'))
    return {"known_tool": (_Input, fn)}


def test_returns_tool_result_dict_on_success():
    registry = _make_registry()
    result = _dispatch_tool_call(_block("known_tool", {"value": "x"}), registry)
    assert result is not None
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tool-1"


def test_returns_none_for_unknown_tool_name():
    result = _dispatch_tool_call(_block("nonexistent", {"value": "x"}), _make_registry())
    assert result is None


def test_returns_none_on_validation_error():
    result = _dispatch_tool_call(_block("known_tool", {"value": 123}), _make_registry())
    assert result is None


def test_calls_write_audit_event_on_success():
    with patch("ticket_triage.subagents.write_audit_event") as mock_log:
        registry = _make_registry()
        _dispatch_tool_call(_block("known_tool", {"value": "x"}, "tid-99"), registry)
        mock_log.assert_called_once_with("tool_called", tool="known_tool", tool_use_id="tid-99")


def test_does_not_call_write_audit_event_on_failure():
    with patch("ticket_triage.subagents.write_audit_event") as mock_log:
        _dispatch_tool_call(_block("nonexistent", {"value": "x"}), _make_registry())
        mock_log.assert_not_called()
