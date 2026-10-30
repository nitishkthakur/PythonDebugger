# Qwen local integration observations

Executed 2026-10-30 against the user-selected `Qwen3.5-4B-UD-Q3_K_XL`.
The installed local server exposes alias `unsloth/Qwen3.5-4B-GGUF:UD-Q3_K_XL`
on numeric loopback port 9931. The main GGUF filename was verified, alongside
the companion mmproj file. Private filesystem paths are not recorded here.

These are observed manual integration checks, not fabricated automated-suite
results. The exact server build and hardware were not captured, so they are not
a reproducible performance benchmark or a compatibility guarantee for all builds.

## Python provider

Using the implemented `LlamaCppLLM`, verified health ready, discovery of the exact
model alias, chat returning a synthetic sentinel with stop reason, streaming
returning its sentinel, zero active transport connections after completion, and
health remaining ready afterward. The attached server was not stopped.

## Coding harness with direct tools

Used an isolated temporary workspace containing a Python function returning 41
and a unittest expecting 42. The agent had read tools and explicit permission
for exact edits and argv execution. Observed sequence: `read_file`, `edit_file`,
`run_command`; final status completed in four model calls. Independently ran the
test afterward: passed. The agent changed the generated source fixture, not the
test. No project/user source files were used as the model task.

## MCP plugin

Launched the bundled stdio server as an owned subprocess, discovered/registered
its tools under a namespace, and asked the same model to read a generated text
file through `mcp_workspace__read_file`. Observed the namespaced call and returned
content, then deterministic client/server cleanup. A first prompt resulted in
the correct content wrapped in JSON instead of the exact bare sentinel requested
by the smoke assertion. A clarified extraction prompt produced the exact bare
sentinel and completed in two model calls. This demonstrates tool integration,
not guaranteed formatting compliance for arbitrary prompts.

## How to repeat

Use `LlamaCppLLM` with the alias/endpoint above, `create_workspace_registry` over
a fresh temporary directory, and `CodingHarness` with an event hook collecting
`before_tool`. For the MCP case, connect `MCPClient` to
`[sys.executable, '-m', 'mcp_local.server', '--root', temporary_root]`, register it
under `mcp_workspace`, and approve only the required namespaced read tool.
Assert actual tool events as well as output; a final answer alone does not prove
tools were used. Never use private user files as synthetic smoke fixtures.

Default automated checks remain model-independent. They test fake-provider tool
round trips and a real local MCP subprocess through the harness. A future
installed model/server version should rerun these manual checks explicitly.
