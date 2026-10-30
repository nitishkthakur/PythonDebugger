# Coding harness index

Read root guidance. This package owns provider-independent agent orchestration.

| File | Responsibility |
| --- | --- |
| `__init__.py` | Public harness API and version factory |
| `engine.py` | Bounded model/tool loop, approvals, hooks, planning, isolated subagents |
| `state.py` | Serializable run state and atomic local checkpoints |

Depend on llm and coding_tools contracts, never app/webapp/cli. Tools and MCP
adapters are plugins supplied by callers. Model instances are caller-owned;
factory-created subagent models are child-owned and always closed. No import-time
work. A coding harness is not an OS sandbox: command tools require explicit opt-in.
Keep every tool call paired with a result, including denied or malformed calls.
Run tests/test_harness.py plus the full regression suite. Changes to public
contracts must update docs/coding-agent.md and examples in that document.
