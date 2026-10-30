# Architecture and code map

The application has three cooperating parts, all implemented in `debugger.py`:

```text
Browser (PAGE_HTML)
    | fetch: /api/*          ^ EventSource: /events
    v                       |
ThreadingHTTPServer + Session
    | commands              ^ events
    +--- loopback socket, newline-delimited JSON ---+
                                                  |
                                     Worker subprocess (Dbg)
                                                  |
                                      bdb traces user script
```

The worker's stdout/stderr travel through separate subprocess pipes, and its stdin
is supplied through a pipe. They do not share the JSON control socket.
All debugger transports are loopback-only. Runtime resources are embedded in the
single Python file; no dependencies or assets are downloaded. The HTTP response
adds a Content Security Policy allowing nonce-bearing embedded scripts, inline
styles, and same-origin API/SSE connections; external resources are blocked.
`LocalHTTPServer` skips the standard HTTP server's hostname lookup, and the worker
connects directly to a numeric IPv4 loopback address, avoiding DNS resolution.

## Startup and a debugging run

1. `main` parses the CLI and loads `SettingsStore`. Explicit folder/script arguments
   take precedence over the saved session. `serve` binds to `127.0.0.1`, tries up to
   50 ports starting at the requested port, and prints a URL with a random token.
2. The browser loads `PAGE_HTML`, including bootstrapped preferences. It subscribes
   to `/events`, whose first event is a complete session snapshot. Later events
   update execution state, output, stack, variables, and inspection results.
3. Run or Restart calls `Session.start`. This stops the previous process, creates
   an ephemeral loopback listener, and launches the chosen interpreter as
   `debugger.py --worker PORT SCRIPT [ARGS...]`. The selected folder becomes its
   working directory; the script's directory becomes `sys.path[0]`.
4. The worker authenticates with a `hello` event using `DBG_TOKEN`. The server sends
   initial breakpoints and `go`. `DBG_OPTS` carries just-my-code and stop-on-entry
   settings. The environment combines inherited variables, optional project
   `.env`, explicit UI environment entries, and debugger transport settings.
5. `Dbg.run_script` executes the compiled script in a fresh `__main__` module under
   a `bdb.Bdb` tracer. A reader thread handles breakpoint/option changes immediately
   and queues other commands for the main tracing thread.
6. A stop sends a stack and selected-frame variables. `Session` records them,
   switches to `paused`, and broadcasts them. Inspection and console commands run
   in the worker while paused; resume commands clear inspection references and
   resume tracing. Uncaught exceptions enter post-mortem inspection before exit.
7. Pipe pump threads relay output. The server waits for process exit and allows
   output to drain before publishing `idle`. A `run_id` guards against events from
   previous runs arriving after a restart.

## Main components

| Component | Responsibility |
| --- | --- |
| `describe`, `_def_loc`, `_mro_info` | Static dotted-name lookup, signatures, docs, source locations, inheritance metadata |
| `Inspector` | Short value descriptions, object references, lazy children, paged NumPy/pandas tables |
| `Dbg` | Breakpoint management, stepping policy, frame selection, watches, console, post-mortem |
| `SettingsStore`, `clean_prefs`, `parse_env` | JSON persistence, preference validation, environment parsing |
| `Session` | Configuration, subprocess and socket lifecycle, state, output buffer, event subscribers |
| File helpers and `make_handler` | Folder browsing, source reading/saving, authenticated HTTP and SSE |
| `PAGE_HTML` | Editor, tree, controls, terminal, stack/variables/watches, table viewer, hover, settings, Help |

The editor uses a native textarea over syntax-highlighted rows. `editRange` routes
programmatic edits through `onEdInput`, with per-file text/selection snapshots for
undo/redo. Consecutive typing is grouped; histories are bounded and kept only in
memory. Native text input, line commands, replacements, and word completion share
that path. Read-only source stays protected. Saving captures a text snapshot so
edits made during the request remain dirty. The find bar searches only the current
buffer; highlighted ranges are merged with syntax spans without inserting raw
source as HTML. Suggestions use local words and built-in keyword lists.

## Protocol and state

HTTP GET endpoints are `/api/ls`, `/api/file`, and `/api/state`. `/` serves the UI;
`/events` streams SSE. POST `/api/config`, `/api/run`, `/api/restart`, `/api/stop`,
`/api/prefs`, and `/api/save` are handled directly. Other commands are dispatched
through `Session.command`: `step`, `next`, `out`, `continue`, `frame`, `eval`,
`expand`, `table`, `hover`, `watches`, `breaks`, and `stdin`.

Worker commands use a `c` field; events use `t`. Inspection requests carry an `id`
to match asynchronous responses (`evalres`, `expanded`, `tabled`, `hovered`). The
browser stores pending requests in `S.pending`. Execution states are `idle`,
`running`, and `paused`; stop reasons are `entry`, `breakpoint`, `step`, or
`exception`. SSE reconnects receive a fresh snapshot.

Settings persist preferences, run configuration, breakpoints, and watches through
an atomic JSON replacement. The default is `debugger_settings.json` beside the
script, with a home-directory fallback when that directory is not writable.
Appearance includes independent workspace/editor palettes and optional hex-color
overrides. Built-in palettes and the style import/export UI live in `PAGE_HTML`.
Imports accept versioned JSON appearance data and exclude arbitrary CSS, scripts,
URLs, and project configuration. The server also validates all persisted colors.

## Verification and limits

`tests/test_debugger.py` uses `unittest` and a `Harness` that starts a real HTTP
server on an ephemeral port and real worker subprocesses. It covers token checks,
stepping across files, dynamic breakpoints in caller frames, console mutation,
inspection, watches, post-mortem, stdin, environment handling, file saves,
settings, hover metadata, and optional pandas/NumPy tables. Some asynchronous
inspection assertions consume `Session` event queues directly. The suite does
not exercise browser rendering, keyboard shortcuts, or SSE through a browser.
`tests/editor.test.cjs` optionally runs the embedded JavaScript using Node's built-in
test runner and a minimal DOM double. It checks editor transactions, keyboard
handlers, history, search, replacement, suggestions, and concurrent saves. It does
not test real browser layout, native keyboard behavior, or rendering.

Only the debuggee's main thread is traced. Word completion does not perform type
analysis. Saved edits require a restart to affect already loaded code.
Explicit console input and watches can execute arbitrary Python. Static hover
attribute resolution avoids properties and `__getattr__`, while value formatting
can still use object representation methods; the debuggee is trusted local code.
