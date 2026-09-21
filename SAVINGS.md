# Token-saving notes

## Where to check current usage

Claude doesn't have access to token usage data — that lives in Anthropic's billing/telemetry. **Check in Claude Code with `/cost`** for session-level cost and tokens.

## Observations from working on this project

- **Long "wall of text" responses cost real money.** Early answers in this session were 40–60 lines when 8–12 would have sufficed. Prefer shorter, and offer "want more detail?" instead of preemptive depth.
- **Full-file rewrites are expensive.** Prefer targeted `Edit` calls over `Write` when only part of a file changes. Rewriting a 60-line file to change 3 lines is ~20× the tokens of the equivalent edit.
- **Re-reading files that are already in context.** The harness tracks file state and tells the model "no need to Read it back." Trust that; don't re-Read.
- **Verbose test output.** Pipe pytest through `tail -N` when there are many tests. Full output of a green 30-test run is mostly noise.
- **Delegate to `Explore` agent for pure lookups.** For "where is X defined?" or "which files reference Y?", spawning an `Explore` subagent isolates the search context so it doesn't bloat the main conversation. Only worth it once the codebase is large enough that searches take multiple tries.
- **Side conversations are not cheaper.** Same context window, same per-turn cost as main-thread work.

## Structural savers going forward

- For pure teaching questions ("what is X for", "tradeoffs on Y"), Claude's answers tend to run 3–8 lines longer than needed. The prompt *"terser"* is enough of a signal to correct in-flight.
- Batching related questions into one turn is cheaper than one-question-per-turn (each turn pays the full context cost).
- Small TDD cycles keep context focused — one failing test → one green implementation → move on — rather than accumulating uncommitted work in the chat.

## Actual-cost observations (mid-project spot check)

Roughly $70 through ~2 days of hands-on TDD work on this project. In-the-ballpark-but-high for the scope. Root causes, in order of weight:

1. **Model tier.** Running on Opus 4.7. Opus is ~5× more expensive per token than Sonnet 4.6, ~25× more than Haiku 4.5. For most of this work (TDD cycles, doc edits, wiring code, teaching questions), Sonnet would produce equivalent quality at ~20% of the cost. Switch with `/model claude-sonnet-4-6`.
2. **Long-lived session.** ~200+ turns in one thread. Every turn pays the full accumulated-context cost. Starting a new session at chunk boundaries (e.g., "finished MCP work → start subagent work") resets that.
3. **Verbose command output landing in context.** Mutmut's spinner alone dumped thousands of progress lines. Route long-running command output through `tail`/`grep` so only summaries hit the context.
4. **Multi-option design menus.** "Here are 4 options with tradeoffs and my recommendation" is expensive when a unilateral recommendation would've been fine. Ask for terse choices when you don't need the depth.
5. **Full-file rewrites when Edits would work.** A rewrite pays for the whole file; Edit pays for the diff.

## Chunk boundaries → start a new context

Signals it's time for a fresh session:
- Finished a design pillar (e.g., MCP done, moving to next subagent).
- Switching from tests-and-implementation cycle to a distinct type of work (research, exam-prep review, docs-only work).
- Long teaching thread that's mostly answered — the reasoning is captured in CLAUDE.md; further Q&A doesn't need the whole history.

Load-bearing state that survives across sessions: CLAUDE.md, README.md, code, tests, memory (`~/.claude/projects/.../memory/`). Ephemeral state that a new session won't have: what test you were about to write next, unresolved design questions from the current thread. Note those in CLAUDE.md before switching if they matter.
