import pytest
from pydantic import ValidationError

from ticket_triage.tools import (
    IssueRefundFailure,
    IssueRefundInput,
    IssueRefundSuccess,
    issue_refund,
)


@pytest.fixture(autouse=True)
def reset_refund_state():
    from ticket_triage.tools import _REFUNDED_ORDERS

    _REFUNDED_ORDERS.clear()
    yield
    _REFUNDED_ORDERS.clear()


def test_issue_refund_returns_typed_success_for_valid_request():
    result = issue_refund(
        IssueRefundInput(order_id="ORD-001", amount=50.00, reason="damaged item")
    )

    assert isinstance(result, IssueRefundSuccess)
    assert result.status == "ok"
    assert result.refund.order_id == "ORD-001"
    assert result.refund.amount_refunded == 50.00
    assert result.refund.refund_id  # non-empty


def test_issue_refund_returns_failure_for_unknown_order():
    result = issue_refund(
        IssueRefundInput(order_id="ORD-NOPE", amount=10.00, reason="test")
    )

    assert isinstance(result, IssueRefundFailure)
    assert result.error.code == "order_not_found"
    assert "ORD-NOPE" in result.error.message


def test_issue_refund_returns_failure_when_amount_exceeds_order_total():
    result = issue_refund(
        IssueRefundInput(order_id="ORD-001", amount=150.00, reason="test")
    )

    assert isinstance(result, IssueRefundFailure)
    assert result.error.code == "refund_exceeds_order_total"


def test_issue_refund_returns_failure_on_duplicate_refund_for_same_order():
    request = IssueRefundInput(
        order_id="ORD-001", amount=50.00, reason="damaged item"
    )

    first = issue_refund(request)
    second = issue_refund(request)

    assert isinstance(first, IssueRefundSuccess)
    assert isinstance(second, IssueRefundFailure)
    assert second.error.code == "already_refunded"


def test_issue_refund_rejects_non_positive_amount_at_input_validation():
    with pytest.raises(ValidationError):
        IssueRefundInput(order_id="ORD-001", amount=0.00, reason="test")
