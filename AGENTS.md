# PythonDebugger: Codex project guidance

## Purpose and constraints

PythonDebugger is a local browser-based Python debugger and light editor. The
application is deliberately distributed as one file, `debugger.py`, including its
HTML, CSS, and JavaScript. It must work completely offline: never add internet
requests, remote assets, telemetry, package installs, CDNs, or downloaded fonts.
Use only the Python standard library and browser-native APIs. Keep all runtime
assets in `debugger.py`; theme imports must remain local, validated data rather
than executable CSS or JavaScript. Preserve the loopback-only transports and
the browser Content Security Policy. The documented minimum is Python 3.8;
avoid newer syntax or APIs without compatibility handling.

Read `README.md` for user behavior and `docs/architecture.md` for the code map and
protocol. There is no package installation, frontend build, or dependency manifest.
NumPy and pandas are optional debuggee dependencies, not debugger dependencies.

## Commands

Run from the repository root (use `python` if that is the Python 3 interpreter):

```sh
python3 debugger.py examples --script demo.py --no-browser --settings /tmp/pythondebugger-settings.json
python3 debugger.py --help
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
  `Inspector` near the start of `debugger.py`.
- Tracing, breakpoints, stepping, console evaluation, and exceptions: `Dbg` and
  `worker_main`.
- Settings, environment, subprocess lifecycle, and event fan-out: `SettingsStore`,
  `parse_env`, and `Session`.
- File access, HTTP authentication, routes, and CLI: `_read_file`, `_save_file`,
  `make_handler`, `serve`, and `main`.
- All browser behavior and styling: the raw `PAGE_HTML` string. Its `MANUAL`
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

Run the existing unittest suite for runtime changes. Add focused regression
coverage for changed debugger behavior using the existing `Harness`; use event
queues and state predicates where possible. For UI changes, also check the
affected interaction in a browser because HTTP tests do not execute JavaScript.
Keep changes focused; do not reformat the embedded UI or split the application as
incidental cleanup. Report tests run, skips, and any unresolved failures.
