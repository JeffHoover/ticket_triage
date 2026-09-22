# Code Review

## Findings

Ordered by impact.

1. **High — MCP refunds are not duplicate-safe.**  
   [`mcp_server.py:23`](ticket_triage/mcp_server.py#L23) passes a new `set()` into every refund call. Consequently, two identical MCP calls both succeed; the documented `already_refunded` protection never applies over MCP. The existing wrapper test checks only response shape, not repeated calls.

2. **High — a final response can bypass tool execution.**  
   [`_run_agent` at `subagents.py:127`](ticket_triage/subagents.py#L127) returns immediately if any `submit_response` block exists. If the model emits `issue_refund` and `submit_response` in one parallel-tool response, the refund is silently skipped while the customer may be told it succeeded. Process domain tool calls first, and accept `submit_response` only when it is the sole call or after all required results have completed.

3. **High — the refund-threshold control does not protect the application runtime.**  
   The hook in [`refund_threshold.py:21`](hooks/refund_threshold.py#L21) applies to Claude Code's tool harness, while the actual agent invokes `issue_refund` directly at [`subagents.py:169`](ticket_triage/subagents.py#L169), and MCP invokes it directly at [`mcp_server.py:23`](ticket_triage/mcp_server.py#L23). The policy should live inside the refund service/tool boundary; a hook can remain as defense in depth. The hook also fails open when `amount` is absent because it defaults to zero, and crashes for a nonnumeric amount. Current fixture data masks this because its only order total equals the threshold.

4. **High — output validation is syntactic, not semantic.**  
   [`SubagentResult` at `schemas.py:12`](ticket_triage/schemas.py#L12) accepts both `SubagentResult(status="resolved")` with no reply and `SubagentResult(status="escalate")` with no reason. The coordinator can therefore produce a resolved customer reply whose text is `None`, or escalate with `reason=None`. Model this as a discriminated union of separate resolved, needs-info, escalation, and failure outcomes, each with its required fields.

5. **Medium-high — malformed domain tool calls crash instead of becoming structured failures.**  
   At [`subagents.py:168`](ticket_triage/subagents.py#L168), an unknown tool raises `KeyError`, invalid input raises `ValidationError`, and tool implementation failures escape directly. Only `submit_response` validation is handled. Convert these failures into `is_error` tool results, log them, and apply an explicit retry/escalation policy.

6. **Medium-high — mixed invalid tool responses produce incomplete tool-result messages.**  
   The validation-retry branch at [`subagents.py:139`](ticket_triage/subagents.py#L139) supplies a result only for the invalid `submit_response`. If that assistant message contained other tool-use blocks, those calls are left without corresponding results, potentially making the next Messages API request invalid.

7. **Medium — operational failures bypass the documented escalation strategy.**  
   `classify()` assumes a text block and valid JSON at [`coordinator.py:56`](ticket_triage/coordinator.py#L56). `_run_agent()` deliberately raises when no tool call appears at [`subagents.py:158`](ticket_triage/subagents.py#L158). SDK/network exceptions are also uncaught. These paths terminate the request rather than retrying or escalating. Introduce a narrow exception boundary with categorized transient, model-output, and permanent failures.

8. **Medium — observability does not meet its stated contract.**  
   The documentation says every tool call and validation failure is logged, but logging exists only around coordinator lifecycle events. The actual tool loop at [`subagents.py:166`](ticket_triage/subagents.py#L166) records neither inputs/results nor validation failures. The observability tests likewise assert only `received`, `classified`, `returned`, retry, and escalation events.

9. **Medium — money is represented with binary floating-point.**  
   [`tools.py:9`](ticket_triage/tools.py#L9), [`tools.py:71`](ticket_triage/tools.py#L71), and the MCP signature use `float`. Use integer minor units or `Decimal` with explicit precision; threshold checks and totals should use the same representation.

10. **Low-medium — setup and status documentation are stale.**  
    [`README.md:12`](README.md#L12) omits `chromadb` and `mcp`, despite unconditional imports. It also says the subagents are stubs/planned even though they are implemented. `pyproject.toml` contains tool configuration but no project metadata or dependencies, so there is no reproducible installation path.

## Refactoring opportunities

| Size | Smellyness | Refactor |
|---|---:|---|
| Small | Very high | Stop creating a new refund-state set in the MCP wrapper; add a repeated-MCP-call test. |
| Small | High | Replace `SubagentResult`'s optional-field bag with a discriminated outcome union. |
| Small | High | Make threshold validation fail closed and enforce it in `issue_refund`, not only in a harness hook. |
| Medium | Very high | Extract an `AgentLoop` responsible for tool dispatch, input validation, result pairing, logging, history trimming, and final-response acceptance. |
| Medium | High | Replace recursive `retry_or_escalate()` with a bounded loop and a single result-to-reply conversion function. This removes duplicated handling between initial and retry paths. |
| Medium | Medium | Define an `AgentSpec` containing prompt, tools, and handlers; derive billing/technical/refund agents from data rather than maintaining parallel registries and wrapper functions. |
| Large | High | Introduce an `OrderRepository`/`RefundService` with persistent idempotency state, money types, policy enforcement, and injected audit logging. This would eliminate module-global business state. |
| Large | Medium | Inject Anthropic clients, repositories, and audit sinks through an application/service object rather than patching module globals in tests. |

## Naming suggestions

- `look_up_order` → `get_order`, or `find_order_by_id` if absence is expected.
- `_run_agent` → `run_agent_loop`.
- `check` → `evaluate_refund_threshold`.
- `log` → `write_audit_event`.
- `SubagentResult` → `AgentOutcome`.
- `Reply` → `TriageReply`.
- `_refunded_orders` / `refunded` → `refunded_order_ids`.
- `_json_default` → `_serialize_log_value`.
- `result` inside orchestration code → `agent_outcome` or `tool_result`, depending on context.

## Summary

The separation of concerns is understandable, the typed tool responses are a solid foundation, and the existing suite passes: **83 tests passed**. The largest risks are at integration boundaries the tests currently simplify away—MCP state, parallel tool calls, compliance-policy placement, and semantic output validation. Addressing those four areas would materially improve correctness before broader cleanup.

No source files were edited during the review.
