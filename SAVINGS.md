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
