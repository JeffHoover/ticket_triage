# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

As an exercise to learn the skills needed for the Anthropic Architect Fundamentals exam, build a "support-ticket triage agent" system.

The exam tests reasoning about architectural tradeoffs, so **document the "why" behind each architectural choice** (retry vs. escalate, which model per subagent, cache vs. no-cache, hooks vs. prompts) — that reasoning is what scenario questions probe.

See [README.md](README.md) for setup, test, and run commands.

## Design pillars

### 1. Agentic loop + orchestration
Coordinator agent receives a raw ticket, classifies it, and dispatches to one of 2–3 subagents (billing, technical, refund-eligibility). Coordinator/subagent pattern — **not** a single monolithic prompt.

### 2. MCP tool design
Each subagent gets real tools via MCP — a mock `look_up_order`, a mock `issue_refund`. Focus on schema design: strict input/output types, clear tool descriptions, and explicit behavior when a tool call fails or returns malformed data.

### 3. Structured output + validation
Force every agent response into JSON matching a schema. Retry loop when validation fails instead of trusting the model.

### 4. Error propagation & human escalation
Explicit rules for which error types get retried automatically vs. escalated to a human, and how escalation is logged/surfaced. The "deterministic gates" mindset the exam rewards.

### 5. Context management
Cap conversation history. Decide what gets summarized vs. dropped. Prompt caching for parts of the system prompt / tool defs that don't change turn-to-turn.

### 6. Claude Code configuration
CLAUDE.md, custom slash commands, and hooks — e.g., a hook that blocks a `issue_refund` tool call above a dollar threshold without approval. Hooks-vs-prompts for compliance is an exam topic.

### 7. Observability / governance layer
Log every tool call, every escalation, every validation failure somewhere reviewable.

### 8. (Optional — Professional tier) RAG component
Small product-docs knowledge base; technical subagent retrieves from it. Justify retrieval-strategy and chunking decisions, not just call an API.

## Scope

Local script with the Claude API + mock tools. No production infra.

## Tools layer

Tools are mock external system calls the subagents use to fetch grounded facts about a customer's situation — order details, refund status, etc. Without them, a subagent LLM would guess or hallucinate. In production each tool would hit a real service (order-management DB, refund-processing API); here they're Python functions with strict Pydantic schemas backed by in-memory mock data.

**Why tools sit in their own layer:**
- Tool schema is what the model sees when deciding whether/how to call — clean schemas → better tool-use accuracy.
- Failure signals must be explicit and distinguishable (`order_not_found` vs. `system_down` vs. `malformed_input`) so the subagent can decide whether to retry, ask the customer, or escalate.
- Tools swap easily: implementation changes (mock → Postgres → REST API) without touching subagent code.

**Current tools** (in `ticket_triage/tools.py`):
- `look_up_order(order_id)` — read-only. Returns `LookUpOrderSuccess | LookUpOrderFailure`. Failure code: `order_not_found`.
- `issue_refund(order_id, amount, reason)` — state-changing. Returns `IssueRefundSuccess | IssueRefundFailure`. Failure codes: `order_not_found`, `already_refunded`, `refund_exceeds_order_total`.

## Committed conventions (load-bearing — changing means rewriting tests)

- **Retry state parameter is `retry_count`, starting at 1.** Not `attempt` (off-by-one ambiguity).
- **`MAX_RETRIES = 2`** — 2 retries after the coordinator's initial failed call = 3 total attempts. Guard clause escalates *without* calling the subagent when `retry_count > MAX_RETRIES`.
- **Escalation is coordinator-owned, not subagent-owned.** Subagents *request* escalation via `SubagentResult(status="escalate", escalation_reason=...)`; the coordinator (or `retry_or_escalate`) executes `escalate()`. Single audit point, single place to enforce top-level policy.
- **`Reply.text` on escalation is non-None** (customer-facing placeholder). Escalation isn't invisible to the customer.
- **Log events are structured JSON lines** with `event`, ISO-8601 UTC `timestamp`, and arbitrary fields. Pydantic models serialize via `.model_dump()`; unknown types raise `TypeError` (fail-loud, no silent `str()` fallback).
- **Log path via `TICKET_TRIAGE_LOG_PATH` env var**, default `./ticket_triage.log.jsonl`.
- **Test isolation via `monkeypatch`** — the coordinator's `classify`, `escalate`, `log`, and `SUBAGENTS` are all module-level and patched per-test. Fixtures in `tests/conftest.py`.
- **Tool responses are tagged unions** (`ToolSuccess | ToolFailure` with `status: Literal[...]` discriminator), not exceptions. Structured returns match MCP's over-the-wire shape — every call yields a response object regardless of outcome, and what the tool writes is what the model eventually sees.
- **`issue_refund` uses dedup-by-state for duplicate protection** — a repeat call on an already-refunded order returns `already_refunded`. **In production this would be idempotency keys** (caller-supplied unique key → server stores original response for that key, replays on repeat). Idempotency keys handle network retries cleanly and support partial refunds; the mock uses simpler by-state dedup because our LLM caller doesn't yet have retry semantics and one-refund-per-order is enough for the demo.

## Status

| # | Pillar | Status | Notes |
|---|---|---|---|
| 1 | Coordinator/subagent orchestration | Done | All three subagents (billing, technical, refund) implemented + tested. Coordinator dispatches to all three. E2E tests cover each domain. |
| 2 | MCP tool design | Done | Both mock tools implemented + tested. MCP server with `look_up_order` and `issue_refund` wrappers. Stateless wrapper pattern via injectable `_refunded_orders`. |
| 3 | Structured output + validation | Done | `submit_response` tool pattern forces structured output. Validation-retry loop (up to `MAX_VALIDATION_RETRIES`) + `failed` fallback. Tested with mock client. |
| 4 | Escalation gates | Done | Gates + `escalate` + `retry_or_escalate` tested. |
| 5 | Context management + prompt caching | Partial | Prompt caching on system prompt + tool defs (`cache_control: ephemeral`) in all subagents. Conversation history cap not yet implemented. |
| 6 | Claude Code config (this file + hooks + slash commands) | Done | This file. `issue_refund` dollar-threshold hook in `hooks/refund_threshold.py` + wired in `.claude/settings.json`. `/triage` slash command in `.claude/agents/triage.md`. |
| 7 | Observability / governance | Done | JSON-lines `log()` + Pydantic serialization + contract tests. |
| — | Optional RAG (Professional tier) | Not started | — |

53 tests across gates, dispatch, escalate, retry, observability, log, look_up_order, issue_refund, MCP server, billing/technical/refund agents, refund threshold hook, and e2e dispatch. Coverage and mutation kill rate not yet re-measured (see README for how to run).
