# Review Response

Naming suggestions applied and committed. README updated. Responses to all other findings below.

---

## Findings

### 1. High — MCP refunds not duplicate-safe

**Agree — this is a bug against documented intent.**

`mcp_server.py` passes a fresh `set()` to every `issue_refund` call, bypassing the `_REFUNDED_ORDER_IDS` guard that CLAUDE.md documents as intentional. The MCP wrapper should share the module-level set, not create a throwaway one. ~~Fix is one-line; will address.~~ Fixed: removed `refunded_order_ids=set()` from the MCP wrapper so it falls through to the module-level set. Test added.

### 2. High — final response can bypass tool execution

**Agree.**

If the model emits `issue_refund` and `submit_response` in the same parallel-tool response, the current loop returns on `submit_response` without executing the refund. The fix is to drain all non-response tool calls first and only accept `submit_response` when it is the sole call in the block or after all other results are collected.

### 3. High — refund-threshold control does not protect the application runtime

**Partially agree.**

The hook's pedagogical purpose is explicit in CLAUDE.md: pillar 6 is specifically about demonstrating the hooks-vs-prompts tradeoff the exam tests. A Claude Code harness hook that does *not* protect the application runtime is the intended illustration of where that boundary sits and why policy must also live inside the tool.

That said, the bugs within the hook itself are real and worth fixing regardless of intent:
- **Fails open on absent `amount`**: `tool_input.get("amount", 0)` means a call with no `amount` field passes through silently. Should fail closed (block or raise).
- **Crashes on non-numeric `amount`**: no type guard before the comparison.

The policy placement argument (enforcement in the tool, hook as defense-in-depth) is architecturally correct for production. For this project it remains a hook-only demo. Will fix the two bugs within the hook.

### 4. High — output validation is syntactic, not semantic

**Agree.**

`AgentOutcome` (formerly `SubagentResult`) accepts `status="resolved"` with `reply_draft=None` and `status="escalate"` with `escalation_reason=None`. CLAUDE.md guarantees `TriageReply.text` on escalation is non-None, but that guarantee lives in runtime coordinator logic rather than in the type. A discriminated union — one Pydantic model per outcome, each with its required fields — would make invalid states unrepresentable. Will address.

### 5. Medium-high — malformed domain tool calls crash instead of structured failures

**Agree.**

An unknown tool name raises `KeyError`; malformed input raises `ValidationError`; tool implementation errors propagate uncaught. All of these terminate the request rather than routing through the retry/escalation path. The fix is to wrap the tool dispatch loop in a narrow exception boundary that converts failures into `is_error` tool results so the agent loop can apply the documented retry or escalation policy. Will address.

### 6. Medium-high — mixed invalid tool responses produce incomplete tool-result messages

**Agree.**

The Messages API requires a `tool_result` for every `tool_use` block in an assistant turn. The current validation-retry path supplies a result only for the failing `submit_response` block; any other tool-use blocks in the same turn are left without results, making the follow-up request malformed. Fix: when retrying on a bad `submit_response`, emit results for all tool-use blocks in that turn, not just the one being re-driven. Will address.

### 7. Medium — operational failures bypass the documented escalation strategy

**Agree.**

`classify()` will `StopIteration`-crash if the model returns no text block. `run_agent_loop()` raises `RuntimeError` when no tool call appears. SDK and network errors are uncaught. These all bypass the deterministic-gates path the design documents. A narrow exception boundary with categorized failure types (transient, model-output, permanent) and explicit retry/escalation routing is the right fix. Will address.

### 8. Medium — observability does not meet stated contract

**Agree.**

CLAUDE.md says every tool call is logged; the tool dispatch loop logs neither inputs nor results. The test suite asserts coordinator lifecycle events only. The gap is real. Will add structured log entries around tool dispatch in `run_agent_loop`. Will address.

### 9. Medium — money represented with binary floating-point

**Agree in principle; deferring.**

`float` is wrong for money — rounding error is real risk. For this mock (integer order totals, one threshold comparison, no arithmetic accumulation), the practical risk is near zero. `Decimal` or integer minor units would be the right teaching example. Deferring this; noting it as a production migration concern in CLAUDE.md rather than reworking the mock now.

### 10. Low-medium — setup and status documentation stale

**Agree.**

~~`README.md` omits `chromadb` and `mcp` from dependencies and describes subagents as stubs. `pyproject.toml` has no metadata or dependency list. Will update README and pyproject.toml.~~ README updated: dependencies, layout, run instructions, and status now reflect current state. `pyproject.toml` metadata and dependency list still absent; deferred.

---

## Refactoring opportunities

| Finding | Response |
|---|---|
| ~~Stop creating new refund-state set in MCP wrapper~~ | ~~Will fix (see finding 1).~~ Fixed. |
| Replace `AgentOutcome`'s optional-field bag with a discriminated outcome union | Will fix (see finding 4). |
| Make threshold validation fail closed and enforce in `issue_refund`, not only in hook | Fail-closed bug in hook: will fix. Enforcement inside `issue_refund`: deferred — keeping the hook-only demo intentional per pillar 6; noting production expectation. |
| Extract an `AgentLoop` responsible for tool dispatch, input validation, result pairing, logging, history trimming, and final-response acceptance | Will do. This is the right center-of-mass refactor and directly addresses findings 5, 6, 7, and 8 simultaneously. |
| Replace recursive `retry_or_escalate()` with a bounded loop | Will do. Recursion is safe at depth 3, but a loop removes the duplicated initial/retry handling. |
| Define an `AgentSpec` data-driven subagent | Deferred. Three explicitly defined subagents are more legible for a learning project than an abstraction over three instances. |
| `OrderRepository`/`RefundService` with persistent idempotency state | Out of scope for a mock-backed demo. Right direction for production. |
| Inject Anthropic clients and sinks through a service object rather than patching globals | Out of scope. Monkeypatching module globals is adequate for this test surface. |
