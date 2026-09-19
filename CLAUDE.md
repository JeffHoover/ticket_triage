# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

As an exercise to learn the skills needed for the Anthropic Architect Fundamentals exam, build a "support-ticket triage agent" system.

The exam tests reasoning about architectural tradeoffs, so **document the "why" behind each architectural choice** (retry vs. escalate, which model per subagent, cache vs. no-cache) — that reasoning is what scenario questions probe.

## Design

### 1. Agentic loop + orchestration
Coordinator agent receives a raw ticket, classifies it, and dispatches to one of 2–3 subagents (e.g., billing, technical, refund-eligibility). Implement as coordinator/subagent pattern, **not** a single monolithic prompt.

### 2. MCP tool design
Each subagent gets real tools via MCP — a mock "look up order" tool, a mock "issue refund" tool. Focus on schema design: strict input/output types, clear tool descriptions, and explicit behavior when a tool call fails or returns malformed data.

### 3. Structured output + validation
Force every agent response into JSON matching a schema. Add a retry loop when validation fails instead of trusting the model.

### 4. Error propagation & human escalation
Define explicit rules: which error types get retried automatically vs. escalated to a human, and how escalation is logged/surfaced. This is the "deterministic gates" mindset the exam rewards.

### 5. Context management
Cap conversation history. Decide what gets summarized vs. dropped. When using the API, wire up prompt caching for parts of the system prompt / tool defs that don't change turn-to-turn.

### 6. Claude Code configuration
Build this using Claude Code with a proper CLAUDE.md, custom slash commands, and hooks — e.g., a hook that blocks a "refund" tool call above a dollar threshold without approval. Hooks-vs-prompts for compliance is explicitly an exam topic.

### 7. Observability / governance layer
Log every tool call, every escalation, every validation failure somewhere reviewable. A structured log file is sufficient to demonstrate the concept.

### 8. (Optional — Professional-tier) RAG component
Index a small product-docs knowledge base and have the technical subagent retrieve from it. Requires justifying a retrieval-strategy and chunking decision, not just calling an API.

## Scope

Local script with the Claude API + mock tools is enough — no production infra required.

## Status

Repository is empty — no code, config, or tooling yet. Update this file with build/test/run commands and architecture notes once the initial scaffolding lands.
