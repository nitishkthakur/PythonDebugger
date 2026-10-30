# Session history

Append timestamped entries in chronological order. Use UTC. Summarize meaningful
progress, rationale, validation, and remaining work; do not copy raw transcripts.

## 2026-10-30 17:05 UTC — Navigation and memory setup

The user asked whether the previous plan was saved; a workspace search found no
plan or session notes. No earlier session content is available to reconstruct.
The user then requested progressive folder guidance and persistent plan, history,
and learned-fact files so future sessions can resume without repeating work.

Read the existing project guidance, README, and architecture. Added root navigation
and memory rules, folder indexes for docs/tests/examples, and memory/evaluations
folders. Preserved the single-file runtime; evaluation implementation and the next
feature remain unspecified. Documentation verification is pending.

## 2026-10-30 17:07 UTC — Setup verified and ready for handoff

Verified all six folder indexes and three memory files exist, checked example
descriptions against their source, and passed `git diff --check`. Changes are
limited to guidance and memory documents; runtime tests were not run because
application code is unchanged. Setup is complete; awaiting the next user objective.

## 2026-10-30 17:15 UTC — Local LLM API and llama.cpp plan

The user requested a standardized parent LLM class and an inherited llama.cpp
backend for downloaded models. Saved the design in `docs/llm-design.md`: shared
types/errors, BaseLLM public wrappers and backend hooks, local HTTP adapter,
streaming, explicit server ownership, and staged tests. Kept runtime placement
in `debugger.py` to preserve the existing single-file constraint; no code added.

Reviewed official llama.cpp server docs. Proposed attachment to a user-started
server first, then streaming and opt-in real-model checks, with managed process
startup a separate follow-up. These are design assumptions, not user-confirmed
deployment choices. Updated the live checklist and learned facts. Design/index
checks and `git diff --check` passed; runtime tests were not run for this
documentation-only change. Next work is base-contract implementation when asked.

## 2026-10-30 17:28 UTC — Modular applications and mandatory testing

The user replaced the single-file constraint with `app/` (debugger), `webapp/`
(future chat website), and `cli/` (future terminal chat), allowing modular code
and inherited base contracts. Added `llm/` guidance for the shared inference
package; its classes remain planned. Added the explicit rule to test every
implemented component/behavior, including error, boundary, and cleanup paths.

Moved debugger runtime into `app/debugger.py`, `worker.py`, `settings.py`, and
`ui.py`, with `python -m app`, a direct script entry, and a small root compatibility
launcher. Preserved distribution-root settings. Updated docs, LLM placement,
folder indexes, test imports, editor extraction, and the isolated/offline copied-
application regression. The first run exposed missed DEFAULT_PREFS/SESSION_KEYS
imports; corrected them before rerunning.

Validation: full Python suite passed (35 tests, one pandas skip); all 11 Node
editor tests passed. Added one more invalid-folder test and passed all 11 layout
tests. Verified the entire browser page is unchanged from the original and
`git diff --check` passes. No real-browser check was run; UI behavior was not
edited. Runtime suite still emits unclosed subprocess-pipe ResourceWarnings;
recorded cleanup investigation as follow-up rather than claiming warning-free
validation. Actual Python 3.8 was not run; grammar compatibility was checked.

The user offered to download llama.cpp and an LLM for real inference tests.
Recommended a local llama-server executable and instruction-tuned GGUF, and asked
for executable/model paths when available (hardware details if model selection
is needed). Downloads and model readiness are unconfirmed. Next planned work is
the BaseLLM contract and fake-backed tests, then the llama.cpp adapter.

## 2026-10-30 17:40 UTC — Required real-model test target

The user is downloading `Qwen3.5-4B-UD-Q3_K_XL` and explicitly requires testing
that model. Updated the LLM design, checklist, and learned facts to preserve its
exact designation and require readiness, chat, streaming, and cleanup checks.
Download completion and local executable/model paths are still unconfirmed;
no inference or compatibility result is claimed.

## 2026-10-30 17:51 UTC — Installed model located and checked

The user confirmed installation and supplied the companion mmproj path. Found
the actual main GGUF beside it and the running loopback server on port 9931 with
the exact selected model alias. Raw HTTP health, chat and streaming passed; the
user then asked to pause and listen. Private asset paths are not persisted here.

## 2026-10-30 18:02 UTC — Coding harness implementation and review

The user explicitly requested implementation of LLM providers, reusable coding
tools, MCP servers/plugins, documentation and an independently built Deep Agents-
inspired harness, with subagents reviewing/improving the work. Launched provider,
tools/MCP, and research/review subagents. Read official Deep Agents assembly and
documentation plus MCP transport/lifecycle/tool specifications; saved the source
comparison in docs/deep-agents-research.md without adding upstream dependencies.

Implemented shared llm/coding_tools/mcp_local/harness packages and CLI. Included
planning, bounded loops/context, approval hooks, atomic checkpoints bound to CLI
workspace, observational events, read-only isolated child agents, and version
selection. Review-driven corrections covered registry cloning, tool-call pairing
and validation, deadlines, FIFO handling, command-output/process bounds, Git
scope, MCP initialization/atomic registration/descendant cleanup, and checkpoint
identity. No web chat UI or managed model server is claimed.

The actual Python provider passed Qwen health/discovery/chat/stream/cleanup.
Qwen then fixed a generated Python bug using read_file/edit_file/run_command;
independent unittest verification passed. MCP-backed read succeeded as well;
an initial exact-output assertion saw JSON-wrapped content, and a clarified
prompt produced the expected bare sentinel. See evaluations/local-llm-smoke.md.
Initial full suite: 82 tests passed with one pandas skip. Final expanded suite
and 11 editor tests are being checked; original debugger pipe warnings persist.

## 2026-10-30 18:04 UTC — Final v1 validation

Final expanded suite passed: 84 Python tests with one pandas skip, and all 11
Node editor tests. Python 3.8 grammar checks cover all new runtime packages;
actual Python 3.8 execution and Windows descendant cleanup were not exercised.
CLI help, indexes/local links and whitespace checks passed. Existing debugger
subprocess-pipe ResourceWarnings remain recorded as follow-up. No browser UI
changed. Implementation/review and direct/MCP real-Qwen checks are complete;
README and docs/coding-agent.md provide runnable usage and explicit v1 limits.

## 2026-10-30 18:58 UTC — Commit and push requested

The user authorized committing and pushing the completed implementation. Checked
the working tree on main and its origin remote, whitespace, and included file
inventory; caches and local settings are excluded. Prior full validation remains
84 Python tests with one pandas skip, 11 editor tests, and real Qwen coding/MCP
checks. Preparing one commit containing the application reorganization, reusable
inference/tools/MCP/harness implementation, tests, guidance and documentation.
