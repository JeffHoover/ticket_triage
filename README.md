# ticket-triage

Routes incoming support tickets to specialized subagents (billing, technical, refund) via a coordinator that classifies each ticket and applies deterministic escalation gates. Built as an exercise for the Anthropic Architect Fundamentals exam.

## Setup

Requires Python 3.14 (Homebrew).

```
python3 -m venv .venv
source .venv/bin/activate
pip install pytest pydantic anthropic
```

The `anthropic` SDK is required for the subagents. Set `ANTHROPIC_API_KEY` in your environment for real API calls; unit tests mock the client, so tests run without a key.

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

Current: 98% line coverage, 86% mutation kill rate (190/222). Remaining survivors are mostly error-message string mutations and a macOS case-insensitive-filesystem quirk on the default log path.

## Run

No entry point yet — the coordinator is invoked programmatically, and `classify()` plus each subagent are still stubs. Structured logs go to `./ticket_triage.log.jsonl` as JSON lines; override with `TICKET_TRIAGE_LOG_PATH=/path/to/log.jsonl`.

## Layout

```
ticket_triage/          # importable package
  coordinator.py        # orchestration, gates, retry/escalate, log
  schemas.py            # Pydantic models: Classification, SubagentResult, Reply
  tools.py              # mock external system calls (look_up_order, issue_refund)
tests/                  # pytest suite; shared fixtures in tests/conftest.py
conftest.py             # sentinel — puts project root on sys.path for tests
```

Planned: `ticket_triage/subagents.py` (billing/technical/refund).

## Status

Coordinator orchestration layer and both mock tools (`look_up_order`, `issue_refund`) complete. 37 tests, 98% line coverage, 86% mutation kill rate. Subagents, real Claude API integration, and prompt caching pending. See [CLAUDE.md](CLAUDE.md) for design reasoning and the pillar-by-pillar status table.
