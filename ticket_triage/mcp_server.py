from mcp.server.mcpserver import MCPServer

from ticket_triage.tools import (
    FindOrderByIdInput,
    IssueRefundInput,
    find_order_by_id as _find_order_by_id,
    issue_refund as _issue_refund,
)

mcp = MCPServer("ticket-triage-tools")


@mcp.tool()
def find_order_by_id(order_id: str) -> dict:
    """Find an order by its ID. Returns order details or a structured not-found error."""
    tool_result = _find_order_by_id(FindOrderByIdInput(order_id=order_id))
    return tool_result.model_dump()


@mcp.tool()
def issue_refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a refund for an order. Returns refund details on success or a structured error."""
    tool_result = _issue_refund(
        IssueRefundInput(order_id=order_id, amount=amount, reason=reason),
        refunded_order_ids=set(),
    )
    return tool_result.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")
