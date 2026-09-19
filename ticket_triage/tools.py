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


class LookUpOrderInput(BaseModel):
    order_id: str = Field(min_length=1)


class LookUpOrderSuccess(BaseModel):
    status: Literal["ok"] = "ok"
    order: Order


class LookUpOrderFailure(BaseModel):
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


def look_up_order(
    request: LookUpOrderInput,
) -> LookUpOrderSuccess | LookUpOrderFailure:
    order = _ORDERS.get(request.order_id)
    if order is None:
        return LookUpOrderFailure(
            error=ToolError(
                code="order_not_found",
                message=f"Order '{request.order_id}' not found",
            )
        )
    return LookUpOrderSuccess(order=order)
