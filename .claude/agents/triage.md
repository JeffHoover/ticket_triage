---
name: triage
description: Route a support ticket through the triage pipeline and explain the routing decision step by step
tools: []
---

If $ARGUMENTS is "--help" or empty, print the following and stop:

```
/triage <ticket text>

Routes a support ticket through the triage pipeline and explains each decision.

Steps:
  1. Classify    — domain (billing / technical / refund / unknown) + confidence score
  2. Gate check  — confidence >= 0.7 to proceed; below threshold escalates immediately
  3. Subagent    — which agent handles it and which tools it would call
  4. Outcome     — expected status (resolved / needs_info / escalate) + reply draft

Subagent tools:
  billing    — look_up_order, issue_refund, submit_response
  technical  — look_up_order, search_docs, submit_response
  refund     — look_up_order, issue_refund, submit_response

Examples:
  /triage I was charged twice for order ORD-001
  /triage My app crashes every time I try to log in
  /triage I returned my item two weeks ago and still have no refund
```

Otherwise, route the following support ticket through the triage pipeline and explain the decision:

Ticket: $ARGUMENTS

Walk through each step:
1. **Classify** — which domain (billing / technical / refund / unknown) and confidence. Why?
2. **Gate check** — does it pass the confidence threshold (0.7)? If not, escalate immediately.
3. **Subagent** — which subagent handles it and what tools would it likely call?
4. **Expected outcome** — resolved / needs_info / escalate, and the reply draft you'd expect.

Keep each step to 1–2 sentences. Flag any ambiguity that would cause low confidence.
