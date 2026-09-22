#!/usr/bin/env python3
"""PreToolUse hook: blocks issue_refund calls above the approval threshold.

Claude Code invokes this before every tool call. It reads the call payload
from stdin as JSON and exits 2 (with a reason on stderr) to block, or 0 to
allow. Exit 2 is the Claude Code convention for a blocked tool call.

Why a hook instead of a prompt instruction: prompt instructions are
advisory — the model can reason past them. A hook is a deterministic gate
enforced by the harness before the tool ever executes. For compliance-level
controls (dollar thresholds, PII checks), the guarantee must come from
outside the model.
"""

import json
import sys

THRESHOLD = 100.00


def evaluate_refund_threshold(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """Return (allowed, reason). allowed=False causes the hook to block."""
    if tool_name != "issue_refund":
        return True, ""
    amount = tool_input.get("amount", 0)
    if amount > THRESHOLD:
        return (
            False,
            f"Refund of ${amount:.2f} exceeds the ${THRESHOLD:.2f} approval "
            "threshold. Human approval required before this refund can proceed.",
        )
    return True, ""


def main() -> None:
    payload = json.load(sys.stdin)
    allowed, reason = evaluate_refund_threshold(
        payload.get("tool_name", ""),
        payload.get("tool_input", {}),
    )
    if not allowed:
        print(reason, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
