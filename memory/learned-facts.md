# Learned facts

## User instructions and preferences

- **Required real-model target:** Test with `Qwen3.5-4B-UD-Q3_K_XL`, which the
  user has installed. Preserve this exact designation; do not substitute a
  different model or quantization for the required integration check. Download
  completion and main GGUF filename were verified locally. The server exposes
  `unsloth/Qwen3.5-4B-GGUF:UD-Q3_K_XL` at numeric loopback port 9931. Python
  provider, actual coding task and MCP integration checks passed. Exact build
  and hardware are not captured. Source: user instruction and checks, 2026-10-30.
- **Modular applications:** The user explicitly relaxed the single-file rule.
  `app/` owns the debugger, `webapp/` the future ChatGPT-like web interface,
  `cli/` the future terminal interface, and `llm/` shared inference contracts.
  Split cohesive modules and use base classes with customized subclasses for
  interchangeable behavior. Source: user request, 2026-10-30.
- **Test everything:** Tests are mandatory for every implemented component and
  behavior, including inherited contracts, error/boundary paths, configuration,
  lifecycle, and integrations. This supersedes treating tests as optional for
  small changes. Source: explicit user instruction, 2026-10-30; root Validation.
- **Real-model validation:** The user offered to download llama.cpp and a model
  to help test. Recommended a local llama-server executable and instruction-
  tuned GGUF. Superseded by subsequent verification of the installed selected
  model. Source: conversation and local smoke checks, 2026-10-30.
- **LLM inheritance:** Build toward a standardized parent LLM API whose methods,
  attributes, and contracts are inherited by backend subclasses; llama.cpp for
  models the user downloads is the first requested backend. User subsequently
  requested implementation of providers, tools, MCP and coding harness, with
  subagents reviewing the work. Source: user requests, 2026-10-30.
- **Progressive navigation:** Every maintained project folder should contain an
  `AGENTS.md` index describing its files. Read local guidance before working in
  that folder. Source: user's setup request, 2026-10-30.
- **Persistent context:** Keep one current plan/checklist, one chronological
  timestamped session history, and a separate file for learned facts. Update them
  during work so future sessions can recover decisions and progress. Source:
  user's setup request, 2026-10-30.
- **Staged work:** Create the folder and memory structure first, then return to
  the user before starting the next implementation objective. Source: user's
  setup request, 2026-10-30.

## Verified project knowledge

- **Superseded:** Runtime code and all browser assets formerly belonged in one
  `debugger.py`. The user replaced this constraint with modular application
  folders on 2026-10-30. Python 3.8+, standard-library-only operation, offline
  assets, and loopback transports remain in effect. Sources: original guidance
  and the user's subsequent architecture instruction.
- Debugger implementation now lives in `app/debugger.py`, `app/worker.py`,
  `app/settings.py`, and `app/ui.py`; root `debugger.py` is a compatibility
  launcher. Default settings remain in the distribution root to preserve saved
  sessions. Source: migration implementation and regression checks, 2026-10-30.
- `tests/test_debugger.py` covers runtime behavior with real servers and workers;
  `tests/editor.test.cjs` checks editor logic with a DOM double. Neither replaces
  browser interaction checks. Source: existing docs, read on 2026-10-30.
- `evaluations/local-llm-smoke.md` records actual local provider/coding/MCP smoke
  observations and limitations. Source: integration work, 2026-10-30.
- Official llama.cpp server docs describe loopback HTTP serving, health, model
  identity, and streaming/nonstreaming chat. A standard-library Python client
  can therefore avoid a Python binding dependency. Source: official server docs
  linked in `docs/llm-design.md`, reviewed 2026-10-30. This is a design basis;
  compatibility with the user's installed build has not been tested.

## Working lessons

- Do not assume a previous conversation or plan is available. Record confirmed
  decisions and unfinished work explicitly. The workspace search in this session
  found no saved prior plan. Source: workspace inspection, 2026-10-30.
- This session's command sandbox failed to start with a loopback permission
  error. Approved escalation allowed read-only inspection; this is environment
  behavior, not an application defect. Source: command results, 2026-10-30.
