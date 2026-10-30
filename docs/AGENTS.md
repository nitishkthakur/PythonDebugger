# Documentation index

Read root guidance before working here.

| File | Contents |
| --- | --- |
| `architecture.md` | Components, startup, browser/server/worker protocols, editor design, verification limits |
| `llm-design.md` | Original LLM design rationale, with implemented v1 contract and superseded sketches identified |
| `coding-agent.md` | Implemented v1 harness, tool inventory, MCP configuration, Python API, CLI, and limits |
| `deep-agents-research.md` | Official Deep Agents and MCP research with independent-design rationale |
| `tools-mcp.md` | Reusable tool and MCP implementation reference |

Keep the architecture aligned with implementation. User-facing behavior belongs
in the root README and the embedded `MANUAL` in `app/ui.py` as well. Keep session
progress in `memory/`, rather than mixing it into architecture documentation.
Add a local index before implementing documentation in any new child folder.
For documentation-only work, verify referenced files and commands; runtime and
UI changes still require the checks specified in root guidance.
