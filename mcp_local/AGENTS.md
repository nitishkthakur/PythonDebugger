# Local MCP index

Read root guidance first. `client.py` owns an explicit local stdio subprocess,
negotiates protocol version, bounds JSON frames, and adapts tools into a registry.
`server.py` exposes workspace tools using MCP JSON-RPC over newline-delimited
stdio; stdout is protocol-only. `__init__.py` exports MCPClient and MCPError.
Tests: `tests/test_mcp.py`; documentation: `docs/tools-mcp.md`.
Supported subset: protocol 2025-03-26, initialize/initialized, ping, tools/list,
tools/call. No HTTP, sampling, resource, prompt, or server-initiated request support.
