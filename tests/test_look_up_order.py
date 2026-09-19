import pytest
from pydantic import ValidationError

from ticket_triage.tools import (
    LookUpOrderFailure,
    LookUpOrderInput,
    LookUpOrderSuccess,
    look_up_order,
)


def test_look_up_order_returns_typed_success_for_known_id():
    result = look_up_order(LookUpOrderInput(order_id="ORD-001"))

    assert isinstance(result, LookUpOrderSuccess)
    assert result.status == "ok"
    assert result.order.order_id == "ORD-001"
    assert result.order.customer_id == "CUST-01"
    assert result.order.total == 100.00
    assert result.order.status == "shipped"


def test_look_up_order_returns_typed_failure_for_unknown_id():
    result = look_up_order(LookUpOrderInput(order_id="ORD-NOPE"))

    assert isinstance(result, LookUpOrderFailure)
    assert result.status == "error"
    assert result.error.code == "order_not_found"
    assert "ORD-NOPE" in result.error.message


def test_look_up_order_rejects_empty_order_id_at_input_validation():
    with pytest.raises(ValidationError):
        LookUpOrderInput(order_id="")
