"""Server-side tests for the MCP tool server — verify tools are registered
correctly and the wrappers return the same shape as calling the underlying
tool functions directly. Runs in-process; no subprocess spun up."""

import asyncio

import pytest

from ticket_triage.mcp_server import (
    issue_refund as mcp_issue_refund,
    look_up_order as mcp_look_up_order,
    mcp,
)
from ticket_triage.tools import (
    IssueRefundInput,
    LookUpOrderInput,
    issue_refund,
    look_up_order,
)


@pytest.fixture(autouse=True)
def reset_refund_state():
    from ticket_triage.tools import _REFUNDED_ORDERS

    _REFUNDED_ORDERS.clear()
    yield
    _REFUNDED_ORDERS.clear()


def test_mcp_server_registers_look_up_order_and_issue_refund():
    tools = asyncio.run(mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "look_up_order" in tool_names
    assert "issue_refund" in tool_names


def test_mcp_look_up_order_wrapper_matches_direct_call():
    wrapper_result = mcp_look_up_order(order_id="ORD-001")
    direct_result = look_up_order(
        LookUpOrderInput(order_id="ORD-001")
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
