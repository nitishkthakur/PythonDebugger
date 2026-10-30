# Current plan

## Scope

Implement the shared Python LLM API and local llama.cpp backend, provider-neutral
coding tools, local MCP server/client plugins, and a version-selected coding
harness. Research Deep Agents thoroughly without depending on it. User explicitly
authorized implementation/review subagents. Preserve offline stdlib operation.

## Completed

- [x] Read the existing root guidance, README, architecture, and repository file list.
- [x] Preserve existing application constraints and validation instructions.
- [x] Add mandatory folder-index navigation and memory maintenance to root guidance.
- [x] Add `AGENTS.md` indexes to `docs/`, `tests/`, and `examples/`.
- [x] Create `memory/` with a plan, chronological session history, and learned facts.
- [x] Create `evaluations/` with guidance for future scenarios and reports.
- [x] Verify all six folder indexes and three memory files exist, inspect example
  descriptions against their files, and run `git diff --check` successfully.
- [x] Review official llama.cpp server documentation for local serving, health,
  model IDs, chat/streaming, and offline operation.
- [x] Specify BaseLLM inheritance, shared data/error contracts, llama.cpp adapter,
  transport and process ownership boundaries, placement, and delivery phases.
- [x] Verify the saved design, index and memory links, Markdown fences, and
  `git diff --check`; prepare the design for user review.
- [x] Replace single-file rules with modular application boundaries, parent
  contracts/inheritance, composition, explicit ownership, and mandatory tests.
- [x] Create application/shared-library folders with local guidance indexes.
- [x] Extract the debugger into worker, settings, UI, and server/session modules;
  retain the root launcher and distribution-root settings location.
- [x] Update README, architecture, LLM design, and test paths for the new layout.
- [x] Pass runtime regression suite (35 tests, one pandas skip) and all 11 Node
  editor tests after correcting missed settings-constant imports.
- [x] Pass all 11 final layout tests, including an additional invalid-folder
  regression across every entry point; verify the UI page is byte-for-byte
  unchanged from before extraction, and pass `git diff --check`.
- [x] Implement BaseLLM/LlamaCppLLM, validated options, errors, tool calls, bounded
  HTTP deadlines, chat/streaming, health/model discovery and cleanup.
- [x] Implement eight reusable workspace/Git/command tools, registries and stdio
  MCP server/client with namespaced plugins and protocol/lifecycle checks.
- [x] Implement v1 bounded harness, todos, approvals, event hooks, checkpoints,
  cancellation boundaries, isolated read-only subagents and version factory.
- [x] Build CLI and document inventory, MCP configuration, research, API and limits.
- [x] Address subagent review findings on registry ownership, FIFO reads, output
  bounds, Git scope, HTTP deadlines, MCP cleanup and atomic plugin registration,
  checkpoint workspace identity and malformed tool calls.
- [x] Pass first full integration suite (82 tests, one pandas skip).
- [x] Verify selected Qwen with Python provider chat/streaming and a real coding
  task (read/edit/run tests), independent test verification, and MCP tool use.
- [x] Final full suite: 84 Python tests, one pandas skip; all 11 editor tests
  passed. Expanded syntax/index/import checks and `git diff --check` passed.

## In progress

None. Requested v1 implementation, research, review corrections, documentation,
and real-model validation are complete. Follow-up features remain separate scope.

## Next

Follow-up extensions, not required for the implemented v1:
- [ ] As a separate follow-up, add an owned server process manager with explicit
  launch configuration and lifecycle tests if managed startup is wanted.
- [ ] Update local indexes as implementation/test/evaluation files are added;
  run Python regression tests for runtime changes.
- [ ] Investigate subprocess pipe ResourceWarnings reported by the runtime suite;
  tests pass, but deterministic stream cleanup deserves focused coverage.
- [ ] Add web chat interface, additional providers, automatic summarization,
  parallel delegation or network MCP transports only against concrete next scope.

## Context and blockers

The exact selected model is installed and tested on the existing loopback server.
No model-server process is owned by the provider. The original typed ChatRequest
design is superseded by normalized dictionary messages and text-delta streaming;
structured calls use chat. Protocol subset is MCP 2025-03-26 tools over stdio.
Default tests do not need model availability. Local commands are not sandboxed;
POSIX descendant cleanup is tested, Windows cleanup has documented limits.
