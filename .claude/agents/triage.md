---
name: triage
description: Route a support ticket through the triage pipeline and explain the routing decision step by step
tools: []
---

Route the following support ticket through the triage pipeline and explain the decision:

Ticket: $ARGUMENTS

Walk through each step:
1. **Classify** — which domain (billing / technical / refund / unknown) and confidence. Why?
2. **Gate check** — does it pass the confidence threshold (0.7)? If not, escalate immediately.
3. **Subagent** — which subagent handles it and what tools would it likely call?
4. **Expected outcome** — resolved / needs_info / escalate, and the reply draft you'd expect.

Keep each step to 1–2 sentences. Flag any ambiguity that would cause low confidence.
