from mcp.server.mcpserver import MCPServer

from ticket_triage.tools import (
    IssueRefundInput,
    LookUpOrderInput,
    issue_refund as _issue_refund,
    look_up_order as _look_up_order,
)

mcp = MCPServer("ticket-triage-tools")


@mcp.tool()
def look_up_order(order_id: str) -> dict:
    """Look up an order by its ID. Returns order details or a structured error."""
    result = _look_up_order(LookUpOrderInput(order_id=order_id))
    return result.model_dump()


@mcp.tool()
def issue_refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a refund for an order. Returns refund details on success or a structured error."""
    result = _issue_refund(
        IssueRefundInput(order_id=order_id, amount=amount, reason=reason),
        _refunded_orders=set(),
    )
    return result.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")
