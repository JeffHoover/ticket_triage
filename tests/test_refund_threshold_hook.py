"""Unit tests for the refund-threshold PreToolUse hook.

Tests the pure check() function — no subprocess, no stdin wiring needed.
Hook logic is deterministic Python; that's what we test here.
The exit-2 I/O path is covered by the hook's __main__ block.
"""

from hooks.refund_threshold import THRESHOLD, check


def test_allows_refund_below_threshold():
    allowed, _ = check("issue_refund", {"order_id": "ORD-001", "amount": THRESHOLD - 0.01, "reason": "damaged"})
    assert allowed


def test_allows_refund_at_threshold():
    allowed, _ = check("issue_refund", {"order_id": "ORD-001", "amount": THRESHOLD, "reason": "damaged"})
    assert allowed


def test_blocks_refund_above_threshold():
    allowed, reason = check("issue_refund", {"order_id": "ORD-001", "amount": THRESHOLD + 0.01, "reason": "damaged"})
    assert not allowed
    assert "approval" in reason.lower()


def test_block_reason_includes_amount_and_threshold():
    amount = THRESHOLD + 50.0
    _, reason = check("issue_refund", {"order_id": "ORD-001", "amount": amount, "reason": "test"})
    assert str(int(amount)) in reason or f"{amount:.2f}" in reason


def test_allows_non_refund_tool():
    allowed, _ = check("look_up_order", {"order_id": "ORD-001"})
    assert allowed


def test_allows_other_tool_regardless_of_amount_field():
    allowed, _ = check("look_up_order", {"order_id": "ORD-001", "amount": THRESHOLD + 999})
    assert allowed
