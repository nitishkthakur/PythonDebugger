# Coding tools index

Read root guidance first. `registry.py` defines provider-independent Tool and
ToolRegistry contracts and validates a documented JSON Schema subset.
`workspace.py` implements confined file operations, read-only Git inspection,
and explicitly enabled command execution. `__init__.py` exports the public API.
Tests: `tests/test_coding_tools.py`. Documentation: `docs/tools-mcp.md`.
Keep imports free of execution and never depend on model providers or harnesses.
Paths must resolve within the selected root; execution is not a sandbox and is
disabled unless the application explicitly opts in.
