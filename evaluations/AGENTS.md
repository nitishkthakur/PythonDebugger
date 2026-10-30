# Evaluation index

Read root guidance before working here.

This folder reserves a place for repeatable assessment scenarios, evaluation
criteria, and concise reports.

| File | Contents |
| --- | --- |
| `local-llm-smoke.md` | Actual Qwen provider, coding-task, and MCP integration observations and limitations |

When an evaluation is requested, document its goal, setup, reproducible steps,
expected behavior, observed results, and limitations. Distinguish planned checks
from executed results. Reference automated regressions in `tests/` rather than
duplicating them here. Browser assessments must state which interactions were
actually exercised. Use temporary settings and sanitized output; never commit
token-bearing URLs, environment values, or private user paths.

Start with focused Markdown files. Add scenario/report subfolders only when
concrete work needs them, with an `AGENTS.md` in each new folder and an entry in
this index. All tooling remains offline and dependency-free, following the root
constraints. Record progress and decisions in `memory/`.
