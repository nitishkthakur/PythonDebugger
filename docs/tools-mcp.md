# Coding tools and local MCP

The `coding_tools` package is shared by all model providers and harness versions.
It has no provider imports. Tools are plain Python callables with a stable name,
description, object input schema, and JSON-serializable result. `ToolRegistry`
validates inputs and publishes OpenAI-style function descriptors; a model adapter
can translate those descriptors to another provider's wire format.

## Tool inventory

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `list_files` | optional `path` | List at most 2,000 regular files; skips Git, environments, caches, protected files and escaping symlinks |
| `read_file` | `path` | Read a regular UTF-8 file, at most 1,000,000 bytes; preserves CRLF |
| `search_text` | `query`, optional `path` | Literal search, at most 200 hits; each displayed line at most 2,000 characters |
| `write_file` | `path`, `content` | Atomic UTF-8 replacement, bounded to 1,000,000 bytes; existing mode retained; parent must already exist |
| `edit_file` | `path`, `old_text`, `new_text` | Atomic replacement only when nonempty old text matches exactly once |
| `git_status` | none | Read status restricted to the workspace, with optional locks and fsmonitor disabled |
| `git_diff` | none | Read unstaged diff restricted to the workspace; external diff/text conversion disabled |
| `run_command` | `argv`, optional `timeout` | Explicit opt-in only; no shell, workspace cwd, at most 60 seconds and 64 KiB combined output |

File operations resolve paths beneath the configured root. `.git`, `.env`, and
`debugger_settings.json` are protected; Git inspection excludes the latter two.
All local operations raise `ToolError` on validation or execution failures.
Commands return their exit status, captured output, truncation, and timeout flags;
a failing subprocess exit is data rather than an exception. Commands exceeding
the output bound are terminated. POSIX child process groups are reclaimed.

Path validation and process cwd are **not an operating-system sandbox**. A trusted
local process racing filesystem changes can defeat ancestor-path checks, and
explicitly enabled commands can access anything allowed to the operating-system
user, including files outside the workspace. Disable execution for read/edit-only
deployments, or put the whole harness in an independently configured OS sandbox.
On Windows only the direct command/server process can be forcibly reclaimed;
POSIX process-group cleanup is the tested implementation.

## Python API

```python
from coding_tools import Tool, ToolRegistry, create_workspace_registry

tools = create_workspace_registry("/path/to/workspace", allow_execute=False)
descriptors = tools.schemas()
result = tools.call("read_file", {"path": "README.md"})

tools.register(Tool("project_info", "Describe this project",
                    {"type": "object", "properties": {}, "additionalProperties": False},
                    lambda arguments: {"language": "Python"}))
```

`clone()` copies membership and schemas so each harness can add planning or
delegation tools without mutating its caller's registry. Handlers still refer to
their original owned services. `register_many()` validates an entire plugin before
publishing it; duplicate or invalid names leave the registry unchanged.

Input validation covers `type`, `required`, `properties`, `additionalProperties`,
`enum`, numeric minimum/maximum, `maxLength`, `items`, and `maxItems`. This is an
explicit subset, not a full JSON Schema implementation; a third-party MCP server
must enforce its own full schemas. Tool output is untrusted context, never an
instruction that can change permissions or execute itself.

## MCP server inventory

Version one implements one reusable **workspace-coding-tools** MCP server,
which exposes the same file/Git tools. Add command execution only explicitly.
External local stdio MCP servers can be configured as additional instances and
registered under distinct namespaces. No external MCP package is installed, no
service is downloaded, and no network MCP endpoint is opened.

Start the bundled server from the repository root:

```sh
python3 -m mcp_local.server --root /path/to/workspace
```

Its stdout carries only protocol messages. The parent process owns its lifetime;
closing stdin ends the session. Add `--allow-execute` only to opt into exposing
`run_command` to the agent.

```python
import sys
from coding_tools import ToolRegistry
from mcp_local import MCPClient

tools = ToolRegistry()
with MCPClient([sys.executable, "-m", "mcp_local.server", "--root", "/path/to/workspace"],
               cwd="/path/to/repository", timeout=10) as server:
    server.register_tools(tools, namespace="workspace")
    result = tools.call("workspace__list_files", {})
```

The adapter returns normal MCP content blocks, so provider code never needs to
know MCP exists. MCP `isError` results become `ToolError`; invocation failures must
be visible to the harness rather than mistaken for success. Server executables
are explicit trusted argv, never commands assembled by a model. Registering an
MCP tool does not grant a subprocess additional operating-system permissions.

## Supported protocol and limits

The implementation pins MCP **2025-03-26**, using UTF-8 newline-delimited JSON-RPC
over stdio. It performs `initialize` negotiation and `notifications/initialized`,
supports `ping`, `tools/list`, and `tools/call`, and distinguishes protocol errors
from tool execution errors. It does not claim full MCP conformance: JSON-RPC
batches, HTTP/SSE transports, prompts, resources, sampling, elicitation, progress
UI, and runtime tool-list updates are not implemented. Server-initiated requests
receive method-not-supported errors rather than executing host actions.

Frames are limited to 1 MiB, pending frame queues to 128, and stderr retention to
8 KiB. Requests have a configurable fixed deadline (default ten seconds).
Timeout sends a best-effort cancellation notification and tears down the owned
connection; there is no implicit retry. Discovery supports up to 100 pages /
1,000 tools and rejects repeated cursors. Shutdown uses stdin EOF, then bounded
terminate/kill fallbacks, and POSIX group cleanup before closing inherited pipes.

The protocol design was checked against the official MCP
[stdio transport specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports),
[initialization/shutdown lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle),
and [tool discovery/call specification](https://modelcontextprotocol.io/specification/2025-03-26/server/tools).
These references inform protocol behavior; they are not runtime dependencies.

## Verification

```sh
python3 -m unittest discover -s tests -p 'test_coding_tools.py' -v
python3 -m unittest discover -s tests -p 'test_mcp.py' -v
```

Tests use temporary workspaces and real local stdio processes. They cover exact
edits/atomic writes, traversal and escaping links, nonregular files, UTF-8 and
byte limits, command opt-in/time/output bounds, scoped Git inspection, registry
cloning/validation, protocol lifecycle, actual discovery and calls, malformed and
oversized output, version mismatch, stderr backpressure, pagination, timeouts,
and a descendant retaining stdio. They need no model, GPU, package install, or
internet connection.
