# Test index

Read root guidance before working here.

| File | Contents |
| --- | --- |
| `test_debugger.py` | Python unittest regression suite and Harness using real HTTP servers and worker subprocesses |
| `editor.test.cjs` | Optional Node built-in tests for embedded editor logic using a small DOM double |
| `test_layout.py` | Application layout, imports, launch commands, settings location, guidance indexes, and local documentation links |
| `test_llm.py` | Shared provider lifecycle/validation, fake HTTP and SSE, deadlines and llama.cpp parsing |
| `test_harness.py` | Fake-model loop, approvals, planning, budgets, checkpoints, subagents, and CLI |
| `test_coding_tools.py` | Workspace tools, traversal, atomic edits, command bounds and registry validation |
| `test_mcp.py` | Local MCP initialization, discovery, calls, protocol errors and process cleanup |

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
node --test tests/editor.test.cjs
```

Extend the existing Harness for changed debugger behavior. Prefer event queues
and state predicates over arbitrary sleeps. Tests need localhost sockets; use
environment approval if binding is denied. Do not install packages; optional
pandas coverage can skip. Node checks do not validate rendering or real browser
interactions. Keep reusable automated regressions here; evaluation protocols and
human assessment reports belong in `evaluations/`. Index any new files or child
folders as they are added.
