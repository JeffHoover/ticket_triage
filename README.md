# ticket-triage

Routes incoming support tickets to specialized subagents (billing, technical, refund) via a coordinator that classifies each ticket and applies deterministic escalation gates. Built as an exercise for the Anthropic Architect Fundamentals exam.

## Setup

Requires Python 3.14 (Homebrew).

```
python3 -m venv .venv
source .venv/bin/activate
pip install pytest pydantic anthropic chromadb mcp
```

The `anthropic` SDK is required for real API calls. Set `ANTHROPIC_API_KEY` in your environment; unit tests mock the client, so tests run without a key.

Optional dev tools (coverage and mutation testing):

```
pip install pytest-cov mutmut
```

## Test

```
pytest tests/
```

Run a single file: `pytest tests/test_gates.py -v`. Run a single test: `pytest tests/test_gates.py::test_low_confidence_escalates_and_skips_dispatch -v`.

### Coverage and mutation testing

```
pytest --cov=ticket_triage --cov-report=term-missing tests/
mutmut run
```

Current: 98% line coverage, 74% mutation kill rate (284/384). `rag.py` is excluded from mutation testing — ChromaDB's module-level singleton is inherited by mutmut's forked workers, making mutations unreachable and causing suspicious exits from background threads (see `pyproject.toml`). Remaining survivors are mostly error-message string mutations in the coordinator.

## Run

Invoke the coordinator programmatically:

```python
from ticket_triage.coordinator import coordinator
reply = coordinator("I was charged twice for order ORD-001")
```

Structured logs go to `./ticket_triage.log.jsonl` as JSON lines; override with `TICKET_TRIAGE_LOG_PATH=/path/to/log.jsonl`.

The MCP server exposes `find_order_by_id` and `issue_refund` over stdio:

```
python -m ticket_triage.mcp_server
```

The `/triage` slash command (`.claude/agents/triage.md`) walks through the full pipeline interactively inside Claude Code.

## Layout

```
ticket_triage/
  coordinator.py    # classify, dispatch, retry/escalate, write_audit_event
  subagents.py      # billing_agent, technical_agent, refund_agent; run_agent_loop
  schemas.py        # Classification, AgentOutcome, TriageReply
  tools.py          # find_order_by_id, issue_refund (mock, Pydantic-typed)
  mcp_server.py     # MCP wrapper exposing tools over stdio
  rag.py            # ChromaDB in-memory collection + search_docs
  docs.py           # product-docs corpus, paragraph-level chunking
hooks/
  refund_threshold.py   # PreToolUse hook: blocks refunds above $100 threshold
tests/                  # pytest suite; shared fixtures in tests/conftest.py
.claude/
  agents/triage.md      # /triage slash command
  settings.json         # hook wiring
```

## Status

All 9 pillars complete. 84 tests, 98% line coverage, 74% mutation kill rate (284/384, `rag.py` excluded). See [CLAUDE.md](CLAUDE.md) for design reasoning and the pillar-by-pillar status table.
