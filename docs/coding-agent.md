# Local coding agent v1

The independent `v1` harness uses shared `llm/`, `coding_tools/`, and `mcp_local/`
packages. It neither imports nor depends on LangChain, LangGraph, or Deep Agents.
Read [the research and design rationale](deep-agents-research.md) and
[tool/MCP reference](tools-mcp.md) for the source comparisons and tool inventory.

## Run

Start with an existing loopback llama.cpp server and a downloaded model:

```sh
python3 -m cli --root . "Inspect the project and summarize its architecture"
python3 -m cli --root . --allow-write --allow-execute "Fix the specified bug and run tests"
python3 -m cli --harness v1 --subagents --root . "Review the code using a read-only subagent"
```

The default model is `unsloth/Qwen3.5-4B-GGUF:UD-Q3_K_XL` at
`http://127.0.0.1:9931`. Set `--model` and `--endpoint` for another local instance.
The Python process does not start, stop, install, or download the model server.
The debugger remains independently launchable with `python3 -m app`.

The CLI automatically loads root workspace AGENTS.md (bounded to 16,000 bytes).
The system prompt requires the model to read scoped instructions before edits.
This is a model instruction, not a formal enforcement of every AGENTS.md rule.

## Tool inventory and permissions

| Capability | Tools | Default |
| --- | --- | --- |
| Inspect workspace | `list_files`, `read_file`, `search_text` | Enabled within the selected root |
| Inspect Git | `git_status`, `git_diff` | Enabled; no commit/push tools |
| Edit workspace | `write_file`, `edit_file` | Harness approval required; CLI `--allow-write` |
| Execute/test | `run_command` with argv and timeout | Not registered without `--allow-execute` |
| Plan | `write_todos` | Enabled; state scoped to a harness run |
| Delegate | `task` | Only with an explicit factory / CLI `--subagents` |
| External local tools | Namespaced MCP tools | Explicit server config; CLI `--allow-mcp` to approve calls |

Arbitrary host commands are **not sandboxed** and can access resources beyond
the workspace. File tools constrain ordinary path resolution but cannot provide
OS isolation against a malicious concurrent filesystem actor. Tool output and
workspace files are untrusted model context. Commands and MCP server launches
are explicit trust decisions, not authorization inferred from model text.

Every tool call has a result even when arguments are invalid or approval fails.
Errors are structured for the model to recover. MCP execution failures stay
failures. Long results are replaced by a bounded preview and an explicit error;
the agent must not treat a preview as complete output.

## MCP servers and plugins

The first server implementation exposes the workspace tool registry over local
stdio. Different instances/profiles provide workspace and optional execution
services; no external account, package installation, network MCP endpoint, or
downloaded server is needed. See [MCP server details](tools-mcp.md).

```sh
python3 -m mcp_local.server --root .
python3 -m mcp_local.server --root . --allow-execute
```

The first command is a protocol process, not an interactive prompt. The client
launches servers and manages initialization/discovery/calls/cleanup. To attach
them to the CLI, create a local JSON configuration (use your interpreter's path
if `python3` differs):

```json
[
  {"name":"workspace", "argv":["python3","-m","mcp_local.server","--root","."]}
]
```

```sh
python3 -m cli --mcp-config /tmp/agent-mcp.json --allow-mcp "Use the workspace MCP tools to list files"
```

Set each server's optional `cwd` when launching outside the repository. Server
argv is executed directly without a shell. Configured servers are trusted local
programs; the MCP client is not a sandbox. All discovered tools go through the
same provider-neutral registry. Future providers need only translate standard
function schemas and normalized tool calls; they never import MCP internals.

## Python API and version selection

```python
from coding_tools import create_workspace_registry
from harness import create_harness, HarnessConfig
from llm import LlamaCppLLM

tools = create_workspace_registry(".")
with LlamaCppLLM("unsloth/Qwen3.5-4B-GGUF:UD-Q3_K_XL") as model:
    agent = create_harness("v1", model=model, tools=tools,
                           config=HarnessConfig(max_steps=8))
    result = agent.run("Read AGENTS.md and summarize the project")
    print(result.status, result.output)
```

`register_harness(version, factory)` adds a named harness implementation without
changing providers, tools, or MCP adapters. Duplicate versions are rejected.
Each harness owns a clone of its registry so planning tools cannot collide when
the caller reuses a registry. The caller owns the parent provider and MCP client;
use context managers. A subagent factory creates independently owned providers
that are closed on completion or error. Children receive a separate task/context,
their own todo state, and only built-in read tools. Delegation is sequential in
v1; it does not imply parallel execution or unrestricted nested delegation.

Customize the system prompt, approval callback `(name, arguments) -> bool`,
event hooks, resource budgets, tool registry, model, and child-provider factory.
Hooks are observational and receive snapshots; exceptions are retained in
`agent.hook_errors` and do not corrupt tool-result pairing. Use approval callbacks
for gating actions. There is no durable human interrupt/edit/resume protocol yet.

## State and limits

`RunState` holds messages, todos, aggregate model steps, output, version, and
explicit status. Stop reasons are `completed`, `incomplete`, `step_limit`,
`context_limit`, `cancelled`, or `failed`. Completed means the model emitted a
nonempty final answer; it does not independently certify code correctness.

`max_steps` is the model-call budget per `run()` invocation; resuming grants a new
budget. `max_tool_calls` bounds each assistant batch. Context limits count JSON
characters including tool schemas, not tokens. v1 stops before exceeding its request budget rather than
silently deleting history or pretending to provide model-based summarization.
Tool-result budgets bound context size, while transport/tools also have byte
limits. The model provider has a request timeout. A cancellation event is checked
between model/tool calls; it does not interrupt an in-flight model request.

Checkpoints are explicit trusted-local JSON files written by atomic replacement.
They may contain task prompts and source code; choose a private, untracked path.
They do not contain provider connection objects or resume arbitrary Python code.
Resume validates complete call/result turns rather than replaying pending tools.
The CLI binds checkpoints to the selected workspace root and rejects a changed
root. Python callers should supply `workspace_root` to get the same protection.
Resuming a completed state without a new task returns the existing result.

```sh
python3 -m cli --checkpoint /tmp/coding-agent-state.json "Inspect the project"
python3 -m cli --checkpoint /tmp/coding-agent-state.json --resume "Continue the review"
```

## Validation and scope

Run `python3 -m unittest discover -s tests -v` and
`node --test tests/editor.test.cjs`. Fake models/HTTP servers and real local MCP
subprocesses cover contracts, paths, writes, timeouts, protocol failures, budgets,
approvals, call pairing, checkpoint resume, and child cleanup. Real Qwen inference
is an additional explicit smoke check, not a requirement of the default suite.

The web chat UI, managed model-server startup, async runs, parallel subagents,
semantic skills retrieval, automatic summarization, OS sandboxes, cloud providers,
and network MCP transports are not part of v1. These are extension boundaries,
not features claimed by the independent Deep Agents baseline comparison.
