# PythonDebugger: Codex project guidance

## Mandatory navigation and session memory

- At the start of every session, read this file, then `memory/AGENTS.md` and
  the three memory files it indexes before planning or implementing work.
- Whenever entering a project folder to inspect or change its contents, you MUST
  read that folder's `AGENTS.md` first, along with applicable ancestor guidance.
  Read each index before following its links into the implementation files.
- Every maintained project subfolder must have its own `AGENTS.md`. Create one
  before implementing work in a new folder. If an existing folder lacks one,
  inspect only enough to write an accurate index before proceeding. This does
  not apply to `.git`, caches, environments, generated output, or user debuggee
  folders. Do not add guidance files to those directories.
- Keep folder indexes concise: explain the folder's purpose, which file contains
  what, local constraints, relevant checks, and child folders. Update the index
  whenever files or responsibilities change; inherit rather than duplicate
  ancestor instructions. Use the exact filename `AGENTS.md`.
- Maintain `memory/plan.md` as the current checklist of completed, active, and
  next work, including blockers and enough detail to resume without repeating it.
- Append brief, timestamped UTC entries to the single `memory/session-history.md`
  as meaningful progress and decisions occur, including at session close. Keep
  entries chronological; record why decisions were made and validation outcomes.
- Maintain `memory/learned-facts.md` for durable user preferences/corrections,
  verified project facts, and lessons from mistakes. Record evidence or context;
  distinguish facts from assumptions and revise obsolete facts explicitly.
- Update memory throughout the session after meaningful changes, scope changes,
  decisions, or checks, and before handing work back. Do not fabricate earlier
  session history or mark unverified work complete. Never store secrets, tokens,
  environment values, or private user paths in these files.
- Memory supplies context; it does not replace current user instructions or
  scoped project guidance. Check relevant code/docs when a remembered fact may
  have changed. Do not treat recorded proposals as authorization to implement.

## Repository index

| Location | Contents |
| --- | --- |
| `app/AGENTS.md` | Modular debugger application, tracing worker, settings, and browser page |
| `webapp/AGENTS.md` | Future ChatGPT-like local web chat application |
| `cli/AGENTS.md` | Future command-line chat application |
| `llm/AGENTS.md` | Shared LLM API and backend implementation plan |
| `coding_tools/AGENTS.md` | Reusable provider-independent tool contracts and workspace operations |
| `mcp_local/AGENTS.md` | Local stdio MCP client/server and tool registration |
| `harness/AGENTS.md` | Versioned coding loop, planning, state, approvals and delegation |
| `debugger.py` | Compatibility launcher for the debugger in `app/` |
| `README.md` | User behavior, shortcuts, setup, and development commands |
| `docs/AGENTS.md` | Documentation index, including the architecture and protocol map |
| `tests/AGENTS.md` | Runtime regression suite and optional editor logic checks |
| `examples/AGENTS.md` | Runnable debuggee fixtures and their purposes |
| `evaluations/AGENTS.md` | Reserved location and guidance for evaluation scenarios and reports |
| `memory/AGENTS.md` | Plan, chronological session history, and durable learned facts |

Grow modules and supporting folders by responsibility as concrete needs arise.
The user explicitly replaced the single-file distribution rule on 2026-10-30:
multiple local runtime modules and assets are allowed. Keep app-specific code in
its app folder and reusable inference logic in `llm/`.

## Coding and application boundaries

- Keep `app/` (debugger), `webapp/` (web chat), and `cli/` (terminal chat) as
  separate applications. Do not put the debugger's page in the chat `webapp/`.
- Shared LLM contracts and implementations belong in `llm/`. Applications depend
  on that package; `llm/` must not import application code or UI state.
- Use small cohesive modules, explicit imports, and clear ownership of resources.
  Avoid circular dependencies, import-time servers/processes, global service
  singletons, and unnecessary generic frameworks.
- Define abstract base classes for shared contracts with real variations, then
  inherit and customize through documented hooks. The LLM base API must provide
  consistent inputs, outputs, errors, and lifecycle across backend subclasses.
  Do not create base classes for unrelated applications merely for symmetry.
- Prefer composition for transport, process management, storage, and other
  independently owned services. Keep backend details out of parent contracts.
- Maintain Python 3.8 compatibility, standard-library-only Python runtime, and
  browser-native APIs. Modularization does not authorize dependency installs,
  cloud connections, automatic model downloads, or external browser assets.
- Each application needs documented entry points and focused tests as it becomes
  implemented. Mark scaffolded or planned components honestly; a folder is not
  an implemented application.

## Purpose and constraints

PythonDebugger is a local browser-based Python debugger and light editor in
`app/`, alongside planned web and terminal chat applications. All applications
must work completely offline: never add internet
requests, remote assets, telemetry, package installs, CDNs, or downloaded fonts.
Use only the Python standard library and browser-native APIs. Keep runtime
assets local to their owning application; theme imports remain validated data rather
than executable CSS or JavaScript. Preserve the loopback-only transports and
the browser Content Security Policy. The documented minimum is Python 3.8;
avoid newer syntax or APIs without compatibility handling.

Read `README.md` for user behavior and `docs/architecture.md` for the code map and
protocol. There is no package installation, frontend build, or dependency manifest.
NumPy and pandas are optional debuggee dependencies, not debugger dependencies.

## Commands

Run from the repository root (use `python` if that is the Python 3 interpreter):

```sh
python3 -m app examples --script demo.py --no-browser --settings /tmp/pythondebugger-settings.json
python3 -m app --help
python3 -m unittest discover -s tests -v
```

The first command prints a token-bearing localhost URL; opening it and pressing
Run starts the selected script. Omit `--no-browser` to launch the browser
automatically. Use a temporary settings path for manual checks so they do not
overwrite the user's saved session.

Tests start real localhost HTTP servers and worker subprocesses. If socket binding
fails with `PermissionError`, use the environment's approval mechanism to run the
same suite with localhost access; do not change application code to bypass it.
The pandas table test skips when pandas is unavailable. No browser automation is
included in this suite.
Optional editor logic checks: `node --test tests/editor.test.cjs` (Node built-ins,
no npm installs). These execute the embedded JavaScript with a small DOM double;
they do not replace visual browser checks or add a runtime dependency.

## Where to make changes

- Inspection, variable trees, tables, and hover metadata: helpers, `describe`, and
  `Inspector` in `app/worker.py`.
- Tracing, breakpoints, stepping, console evaluation, and exceptions: `Dbg` and
  `worker_main` in `app/worker.py`.
- Settings and environment parsing: `SettingsStore` and `parse_env` in
  `app/settings.py`. Subprocess lifecycle and event fan-out: `Session` in
  `app/debugger.py`.
- File access, HTTP authentication, routes, and CLI: `_read_file`, `_save_file`,
  `make_handler`, `serve`, and `main` in `app/debugger.py`.
- Debugger browser behavior and styling: `PAGE_HTML` in `app/ui.py`. Its `MANUAL`
  constant is the in-app Help; update it and the README when user behavior changes.
- Editor transactions, bounded per-tab history, search/replace, line commands,
  and word suggestions are implemented inside `PAGE_HTML`. Keep them independent
  of the debuggee and preserve dirty state for edits made during a pending save.
- End-to-end coverage: `tests/test_debugger.py`; runnable fixtures: `examples/`.

## Behavior to preserve

- Keep HTTP and worker sockets on loopback, token authentication, and Host checks.
  This debugger executes local code and is not a sandbox for untrusted scripts.
- Canonicalize paths consistently. Source outside the selected root can be viewed
  for stepping, but saving must remain confined to existing files inside the root.
  Preserve CRLF and atomic file replacement; non-UTF-8 files are read-only in the UI.
- Keep tracing active on Continue. Breakpoint changes must work while running or
  paused, including existing caller frames and files not imported yet. The browser
  serializes breakpoint updates before Continue/Step; preserve that ordering.
- Hover resolves dotted names statically with `inspect.getattr_static`; do not
  introduce `eval` or invoke properties or `__getattr__` to resolve hover names.
  Watch expressions and explicit console input intentionally evaluate user code.
- Console assignments must affect existing locals in the selected frame. Preserve
  the pre-3.13 locals synchronization and `dont_inherit=True` compilation so the
  debugger's future imports do not leak into the debuggee or console.
- Inspector references are temporary and cleared on resume. Keep lazy pagination
  and stale-reference handling rather than eagerly serializing whole objects.
- Preserve run-generation checks and locking when changing subprocess lifecycle;
  late events from a previous run must not overwrite the current session.
- Keep settings, `.env`, tokens, and user paths out of committed artifacts.

## Validation

### Mandatory: write tests for everything

- Write and maintain tests for every implemented component and behavior. This
  applies to all applications, shared libraries, base classes, subclasses,
  helpers, interfaces, configuration, integrations, and lifecycle operations.
  Tests are part of implementation, not optional follow-up work.
- Every new feature, bug fix, refactor, module move, or changed contract must
  include new or updated tests proving the intended behavior. Test inherited
  contracts against every concrete implementation. Cover normal operation,
  invalid inputs, boundary cases, errors, and resource cleanup; cover concurrency,
  cancellation, and stale events wherever those behaviors apply.
- Add regression coverage for each fixed defect. Use unit tests for isolated
  logic and integration tests for cooperating components. Test public outcomes
  and invariants rather than merely mirroring implementation details.
- Test UI logic and verify affected interactions in a real browser. Test launch
  commands, import behavior, offline operation, and packaging/layout assumptions
  when entry points or file structure change. Documentation-only changes require
  executable checks of affected indexes, local links, and documented commands.
- Use standard-library and browser-native tools, plus the existing optional Node
  built-ins; do not install test dependencies. Default tests must not need models,
  GPUs, internet, or llama.cpp. Use deterministic fakes/local servers and keep
  real-model integration checks explicit and opt-in.
- Run the relevant tests before declaring work complete. Report commands,
  outcomes, skips, and any coverage or execution gaps explicitly. A passing
  unrelated suite does not substitute for tests of the changed behavior.

Run the existing unittest suite for runtime changes. Add focused regression
coverage for changed debugger behavior using the existing `Harness`; use event
queues and state predicates where possible. For UI changes, also check the
affected interaction in a browser because HTTP tests do not execute JavaScript.
Keep changes focused; do not reformat the UI as incidental cleanup. Module
extractions must preserve runtime behavior and update imports, subprocess entry
points, tests, and indexes together. Report tests run, skips, and unresolved failures.
