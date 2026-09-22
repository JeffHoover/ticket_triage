from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class Order(BaseModel):
    order_id: str
    customer_id: str
    total: float
    status: Literal["pending", "shipped", "delivered", "cancelled"]


class ToolError(BaseModel):
    code: str
    message: str


class FindOrderByIdInput(BaseModel):
    order_id: str = Field(min_length=1)


class FindOrderByIdSuccess(BaseModel):
    status: Literal["ok"] = "ok"
    order: Order


class FindOrderByIdFailure(BaseModel):
    status: Literal["error"] = "error"
    error: ToolError


_ORDERS: dict[str, Order] = {
    "ORD-001": Order(
        order_id="ORD-001",
        customer_id="CUST-01",
        total=100.00,
        status="shipped",
    ),
}


def find_order_by_id(
    request: FindOrderByIdInput,
) -> FindOrderByIdSuccess | FindOrderByIdFailure:
    order = _ORDERS.get(request.order_id)
    if order is None:
        return FindOrderByIdFailure(
            error=ToolError(
                code="order_not_found",
                message=f"Order '{request.order_id}' not found",
            )
        )
    return FindOrderByIdSuccess(order=order)


class SearchDocsInput(BaseModel):
    query: str = Field(min_length=1)


class SearchDocsChunk(BaseModel):
    text: str
    source: str


class SearchDocsResult(BaseModel):
    chunks: list[SearchDocsChunk]


class IssueRefundInput(BaseModel):
    order_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    reason: str = Field(min_length=1)


class Refund(BaseModel):
    refund_id: str
    order_id: str
    amount_refunded: float


class IssueRefundSuccess(BaseModel):
    status: Literal["ok"] = "ok"
    refund: Refund


class IssueRefundFailure(BaseModel):
    status: Literal["error"] = "error"
    error: ToolError


_REFUNDED_ORDER_IDS: set[str] = set()


def issue_refund(
    request: IssueRefundInput,
    *,
    refunded_order_ids: set[str] | None = None,
) -> IssueRefundSuccess | IssueRefundFailure:
    refunded_order_ids = refunded_order_ids if refunded_order_ids is not None else _REFUNDED_ORDER_IDS
    order = _ORDERS.get(request.order_id)
    if order is None:
        return IssueRefundFailure(
            error=ToolError(
                code="order_not_found",
                message=f"Order '{request.order_id}' not found",
            )
        )
    if request.order_id in refunded_order_ids:
        return IssueRefundFailure(
            error=ToolError(
                code="already_refunded",
                message=f"Order '{request.order_id}' has already been refunded",
            )
        )
    if request.amount > order.total:
        return IssueRefundFailure(
            error=ToolError(
                code="refund_exceeds_order_total",
                message=(
                    f"Refund amount {request.amount} exceeds order total "
                    f"{order.total} for '{request.order_id}'"
                ),
            )
        )
    refunded_order_ids.add(request.order_id)
    return IssueRefundSuccess(
        refund=Refund(
            refund_id=f"REF-{request.order_id}",
            order_id=request.order_id,
            amount_refunded=request.amount,
        )
    )
