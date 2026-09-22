"""Server-side tests for the MCP tool server — verify tools are registered
correctly and the wrappers return the same shape as calling the underlying
tool functions directly. Runs in-process; no subprocess spun up."""

import asyncio

import pytest

from ticket_triage.mcp_server import (
    find_order_by_id as mcp_find_order_by_id,
    issue_refund as mcp_issue_refund,
    mcp,
)
from ticket_triage.tools import (
    FindOrderByIdInput,
    IssueRefundInput,
    find_order_by_id,
    issue_refund,
)


@pytest.fixture(autouse=True)
def reset_refund_state():
    from ticket_triage.tools import _REFUNDED_ORDER_IDS

    _REFUNDED_ORDER_IDS.clear()
    yield
    _REFUNDED_ORDER_IDS.clear()


def test_mcp_server_registers_find_order_by_id_and_issue_refund():
    tools = asyncio.run(mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "find_order_by_id" in tool_names
    assert "issue_refund" in tool_names


def test_mcp_find_order_by_id_wrapper_matches_direct_call():
    wrapper_result = mcp_find_order_by_id(order_id="ORD-001")
    direct_result = find_order_by_id(
        FindOrderByIdInput(order_id="ORD-001")
    ).model_dump()

    assert wrapper_result == direct_result


def test_mcp_issue_refund_wrapper_matches_direct_call():
    wrapper_result = mcp_issue_refund(
        order_id="ORD-001", amount=50.00, reason="damaged"
    )
    direct_result = issue_refund(
        IssueRefundInput(order_id="ORD-001", amount=50.00, reason="damaged")
    ).model_dump()

    assert wrapper_result == direct_result
