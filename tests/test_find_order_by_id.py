import pytest
from pydantic import ValidationError

from ticket_triage.tools import (
    FindOrderByIdFailure,
    FindOrderByIdInput,
    FindOrderByIdSuccess,
    find_order_by_id,
)


def test_find_order_by_id_returns_typed_success_for_known_id():
    result = find_order_by_id(FindOrderByIdInput(order_id="ORD-001"))

    assert isinstance(result, FindOrderByIdSuccess)
    assert result.status == "ok"
    assert result.order.order_id == "ORD-001"
    assert result.order.customer_id == "CUST-01"
    assert result.order.total == 100.00
    assert result.order.status == "shipped"


def test_find_order_by_id_returns_typed_failure_for_unknown_id():
    result = find_order_by_id(FindOrderByIdInput(order_id="ORD-NOPE"))

    assert isinstance(result, FindOrderByIdFailure)
    assert result.status == "error"
    assert result.error.code == "order_not_found"
    assert "ORD-NOPE" in result.error.message


def test_find_order_by_id_rejects_empty_order_id_at_input_validation():
    with pytest.raises(ValidationError):
        FindOrderByIdInput(order_id="")
