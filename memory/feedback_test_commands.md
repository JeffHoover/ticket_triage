---
name: feedback-test-commands
description: How to format coverage and mutation test commands for this user
metadata:
  type: feedback
---

When giving coverage or mutation test commands, give the most compact form that still surfaces all the information needed to assess results — suppress intermediate progress lines, show only the summary.

**Why:** User prefers to run commands themselves and doesn't want to scroll through verbose intermediate output.

**How to apply:**
- Coverage: use `--no-header -q` and pipe through `tail` or use `--tb=no` to suppress tracebacks when only the summary matters. Example: `pytest --cov=ticket_triage --cov-report=term-missing -q 2>&1 | tail -20`
- Mutation (mutmut): use `mutmut results` after a run rather than watching the live output; or pipe `mutmut run` through `tail` for just the final summary.
- Adjust flags per tool — the goal is: fewest lines, complete answer.
