# Terminal chat application index

Read root guidance before working here.

This folder now provides the terminal coding-agent application.

| File | Responsibility |
| --- | --- |
| `__init__.py` | Package marker without startup side effects |
| `__main__.py` | Explicit CLI configuration, providers, tools, MCP ownership, and exit codes |

Run `python3 -m cli --help` from the repository root. The debugger argument parser
remains in `app/debugger.py`. Test with tests/test_harness.py and the full suite.

Future CLI presentation and argument handling belong here and call shared `llm/`
contracts. Keep prompt handling, terminal output, and exit codes out of backend
classes. Use explicit startup, deterministic cleanup, and standard-library-only
code. Index implemented files, entry commands, and checks as they are added.
