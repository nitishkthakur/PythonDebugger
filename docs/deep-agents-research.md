# Deep Agents research and independent harness design

Reviewed official documentation and assembly source on 2026-10-30. Upstream
`master` and online docs evolve; this is an architectural reference, not a pinned
dependency or compatibility promise. This project does not import or copy the
Deep Agents runtime. Its implementation remains standard-library Python.

## What the baseline actually provides

Deep Agents layers planning, filesystem context, delegation, memory, and context
management around a model/tool loop. The important distinction is between the
model's inference API and the harness that decides which tools it can use and
how state evolves. Its overview presents planning as an optional capability, so
the local implementation should not assume every upstream version installs an
identical planner. [Official overview](https://docs.langchain.com/oss/python/deepagents/overview).

The reviewed `create_deep_agent` assembly wires filesystem middleware, optional
subagents, summarization, tool-call repair, and additional middleware into
LangChain's agent constructor. It accepts an explicit model, tools, backend,
custom middleware, optional memory/skills, permission/interrupt configuration,
and checkpoint storage. This supports an inference for this project: preserve
those boundaries as small interchangeable Python contracts instead of reproducing
its full LangGraph machinery. [Assembly source](https://github.com/langchain-ai/deepagents/blob/master/libs/deepagents/deepagents/graph.py).

Filesystem operations are routed through a backend abstraction. Local filesystem
restrictions do not make arbitrary shell execution safe: once a command can
execute on the host, it can access host resources outside the filesystem-tool
root. Therefore the local tools should resolve paths against an explicit root,
check symlinks, bound reads/results, and keep execution independently opt-in.
They must not describe command execution as sandboxed.
[Backend documentation](https://docs.langchain.com/oss/python/deepagents/backends).

Delegation can use an isolated context or a fork of parent history. Subagents may
have their own model, instructions, tools, and permissions. For this project's
first version, isolated read-only reviewers are easier to reason about than
unrestricted recursive forks. The parent should receive a concise result rather
than absorbing every child transcript. [Subagent documentation](https://docs.langchain.com/oss/python/deepagents/subagents).

Context management includes summarization and offloading large results. A local
v1 can honestly enforce bounded history/output with an explicit stop reason;
it should not silently discard tool-result pairs or claim token-accurate limits
from character counts. Model-backed summaries and artifact offloading can later
be separate context policies. [Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering).

Human review is configurable around selected operations. The reviewed workflow
integrates interrupts with persisted graph state; this is more than a prompt
telling a model to ask permission. Local policy should execute before tools and
fail closed when approval is absent, while preserving enough structured state to
explain the denial. Full interactive pause/edit/resume is a separate feature and
must not be implied by a simple callback. [Human-in-the-loop documentation](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop).

Memory files and progressively disclosed skills are distinct facilities: memory
adds selected durable instructions/context, whereas skills expose discoverable
specialized guidance. Neither requires automatic persistence of all user input.
For this repository, keep project `AGENTS.md` navigation separate from any
future agent-managed memory policy, and never let workspace text expand tool
permissions. [Memory](https://docs.langchain.com/oss/python/deepagents/memory),
[skills](https://docs.langchain.com/oss/python/deepagents/skills).

## Independent local contracts and acceptance criteria

The following are this project's design recommendations, inferred from those
boundaries rather than requirements of the upstream library:

- Providers expose normalized responses and tool calls; they do not own tools,
  filesystem policy, MCP sessions, or conversational state.
- A registry exposes provider-neutral callable tools and translates their JSON
  schemas at the provider boundary. MCP tools become namespaced registry entries.
- A version-selected harness owns the model/tool loop and accepts configurable
  instructions, iteration/context budgets, event hooks, approval policy, and
  optional checkpoint storage. Do not create a global mutable service singleton.
- Every assistant tool call receives a matching tool result, including malformed
  arguments, unknown tool names, policy denials, and tool exceptions. Tool-call IDs
  remain unique and history stays valid when multiple calls arrive together.
- Stop reasons distinguish final answer, budget exhaustion, cancellation, policy
  failure, and backend failure. A truncated or empty model response is not proof
  that a coding task succeeded.
- Checkpoints are explicit local artifacts, written atomically, and documented as
  potentially containing task/code context. Do not make import/startup write them.
- Test scripted fake models through normal, tool-error, approval, budget,
  subagent, and checkpoint paths. Then run the actual Qwen model through a small
  temporary-workspace tool task; simple chat alone does not prove tool use.

## MCP protocol research

MCP stdio uses newline-delimited UTF-8 JSON-RPC messages. It is not the older
Language Server Protocol Content-Length framing. Stdout is exclusively protocol
traffic; diagnostic output belongs on stderr. Clients own their launched server
subprocesses and need bounded reads and deterministic teardown.
[Transport specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

Initialization must precede operation: the client requests a supported protocol
version and capabilities, verifies the response, and then sends
`notifications/initialized`. Unsupported negotiated versions require disconnect;
do not advertise capabilities that are unimplemented. Explicitly pin the local
implementation's supported revision rather than asserting universal MCP support.
[Lifecycle specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle).

Tool discovery uses `tools/list` and can paginate; execution uses `tools/call`.
Protocol errors and execution failures differ: tool failures are structured
results marked `isError`, which callers must not present as successes. Validate
advertised schemas and results, bound total discovery/pages/output, and ensure
duplicate or invalid tool names cannot overwrite local tools.
[Tool specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

A stdio-only implementation is a useful explicit v1 scope. It does not imply
support for Streamable HTTP, resource subscriptions, prompts, sampling,
elicitation, long-running tasks, OAuth, or arbitrary external servers. The local
workspace server may expose the same registry using one well-tested transport;
separate process profiles can restrict read/write/execute capabilities without
duplicating implementations.
