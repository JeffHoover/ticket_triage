---
name: project-mutmut-cache
description: How mutmut 3.x caches results and how to force a full re-run in this project
metadata:
  type: project
---

Mutmut 3.x uses three cache layers in `mutants/`:
- `mutmut-stats.json` — stores function hashes (used to detect "unmodified" source) and test→function mapping
- `ticket_triage/*.meta` — stores mutation definitions + per-mutant exit codes (killed/survived)
- `.mutmut-cache` (SQLite, project root) — additional cache layer

**Why** Adding tests without changing source leaves all three caches stale — mutmut sees "8 unmodified" files and loads old results.

**How to apply:** To force a full re-run after adding tests (not changing source):
```
rm mutants/mutmut-stats.json && .venv/bin/mutmut run
```
Deleting just `.meta` files or `.mutmut-cache` is insufficient — mutmut skips regeneration when stats JSON hashes still match.
