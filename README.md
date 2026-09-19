# ticket-triage

Routes incoming support tickets to specialized subagents (billing, technical, refund) via a coordinator that classifies each ticket and applies deterministic escalation gates. Built as an exercise for the Anthropic Architect Fundamentals exam.

## Setup

Requires Python 3.14 (Homebrew).

```
python3 -m venv .venv
source .venv/bin/activate
pip install pytest pydantic
```

## Test

```
pytest tests/
```

Run a single file: `pytest tests/test_gates.py -v`. Run a single test: `pytest tests/test_gates.py::test_low_confidence_escalates_and_skips_dispatch -v`.

## Run

No entry point yet — the coordinator is invoked programmatically, and `classify()` plus each subagent are still stubs. Structured logs go to `./ticket_triage.log.jsonl` as JSON lines; override with `TICKET_TRIAGE_LOG_PATH=/path/to/log.jsonl`.

## Layout

```
ticket_triage/          # importable package
  coordinator.py        # orchestration, gates, retry/escalate, log
  schemas.py            # Pydantic models: Classification, SubagentResult, Reply
tests/                  # pytest suite; shared fixtures in tests/conftest.py
conftest.py             # sentinel — puts project root on sys.path for tests
```

Planned additions: `ticket_triage/subagents.py` (billing/technical/refund) and `ticket_triage/tools.py` (mock MCP tools).

## Status

Coordinator orchestration layer complete and covered by 29 tests (gates, dispatch, escalate, retry, observability, log serialization). Subagents, MCP tools, real Claude API integration, and prompt caching are pending. See [CLAUDE.md](CLAUDE.md) for design reasoning and the pillar-by-pillar status table.
