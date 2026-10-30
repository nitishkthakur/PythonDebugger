# PythonDebugger

A minimal browser-based Python debugger and light editor in one file (`debugger.py`).
Completely offline, with all HTML, CSS, and JavaScript embedded in that file.
Standard library only (Python 3.8+): no pip installs, frontend build, CDNs, remote
fonts, telemetry, or internet requests. Built on `bdb`, the engine behind `pdb`.
The browser and debug worker communicate only over loopback on your computer;
the UI's Content Security Policy blocks external resources and connections.

```
python debugger.py [FOLDER] [--script path/to/script.py] [--port 8765] [--no-browser] [--settings FILE]
```

It prints a URL containing a random token (localhost only); open it in Chrome.

## Using it

1. Pick a folder (Open / Browse…). Click a `.py` file to open it; **double-click** it to make it the **Script** to run
   (the first file you open is chosen automatically).
2. Click the gutter to set breakpoints (accent-colored dot), then **Run**.
3. **Continue F8 · Step Over F10 · Step Into F11 · Step Out Shift+F11**. The editor follows
   execution into other files. Click a call-stack row to inspect that frame.
4. **Variables**: expand lists, dicts, sets, enums, objects, numpy arrays, DataFrames/Series
   (`view` button opens a paged table). Values that changed since the last stop are outlined.
5. **Terminal** (bottom): while paused, type Python to run in the selected frame, e.g.
   `enabled = True` to fix a variable, or `p x` / `pp x`. While the script is running, the
   same box feeds the script's stdin.
6. **Watch** expressions re-evaluate at every stop.
7. Uncaught exceptions pause the program (post-mortem) so you can inspect the failing frames.
8. Breakpoints can be added or removed at any time, also while paused; Continue honors them (other files too).
9. **Hover** (while paused) on a name: signature, docstring, `file:line` (click to open), and for classes/methods the
   full inheritance chain (**MRO**) with the defining class marked; Ctrl/Cmd+click jumps to the definition.
   Hover never runs your code (properties and `__getattr__` are not evaluated).
10. **Just my code** skips the standard library and site-packages when stepping.

**Editing & settings.** Click the code to edit it (Ctrl+S saves, CRLF preserved, Tab/auto-indent, breakpoints
follow your edits). The ⚙ Settings menu sets font, themes, custom colors and environment variables;
**A− / A+** or Ctrl+`+`/`-`/`0` zoom only the text (not the layout). Everything is saved to
`debugger_settings.json` next to `debugger.py` (git-ignored) and restored on the next start, together with your
last folder, script, args, breakpoints and watches. Don't put secrets in it.

The editor has its own toolbar, per-tab undo/redo history, cursor/selection status,
automatic bracket and quote pairing, and these shortcuts (use Cmd instead of Ctrl
on Mac, except Ctrl+Space):

| Action | Shortcut |
| --- | --- |
| Save / Save all modified tabs | Ctrl+S / Ctrl+Shift+S |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z or Ctrl+Y |
| Find / Replace in current file | Ctrl+F / Ctrl+H |
| Next / previous match | F3 / Shift+F3; Enter / Shift+Enter in the find field |
| Go to line or line:column | Ctrl+G |
| Toggle comments | Ctrl+/ |
| Indent / outdent selected lines | Tab / Shift+Tab |
| Move lines up / down | Alt+Up / Alt+Down |
| Duplicate lines | Alt+Shift+Down |
| Local word suggestions | Ctrl+Space, then arrows and Enter/Tab |

Find supports case-sensitive, whole-word, and JavaScript regex searches with match
highlighting. Regex replacements accept captures such as `$1`; literal mode keeps
dollar signs unchanged. Empty regex matches are skipped. At most 5,000 matches are
highlighted; Replace all processes every nonempty match in the current file and can
be undone in one step.

Word suggestions use names from the current file, Python keywords, and common
built-ins. They work entirely offline and do not perform type analysis. Cursor
positions and bounded undo histories survive tab switching and saving; they stay
in memory and are lost when a tab is closed or the page is reloaded. Save edits
before Run/Restart; editing a running program does not change its loaded code.

**Themes & styles.** Choose **Daylight**, **Graphite**, **Midnight**, **Parchment**,
**Forest**, or **High contrast** for the workspace. The **Viewer / editor** can
match the workspace or use a separate theme. Customize background, text, syntax
colors, and gutter with the color pickers and live preview. Choosing an editor
preset clears its custom color overrides; **Reset editor colors** restores just
that palette, and **Reset appearance to defaults** restores all appearance settings.

**Export style…** saves a local `pythondebugger-style.json`; **Import style…**
loads it without accessing the internet. Only appearance settings are exported,
excluding environment variables, file paths, and code. Imports accept validated
JSON settings rather than arbitrary CSS or JavaScript. Style files can also be
edited in a text editor; use hex colors such as `#243047`:

```json
{
  "format": "pythondebugger-style",
  "version": 1,
  "prefs": {
    "theme": "midnight",
    "editor_theme": "sepia",
    "editor_colors": {"keyword": "#8055a5"}
  }
}
```

Palette IDs are `light`, `dark`, `midnight`, `sepia`, `forest`, and `contrast`;
`editor_theme` also accepts `match`. Color keys are `background`, `text`, `keyword`,
`string`, `comment`, `number`, and `gutter`. Appearance settings persist across restarts.

The script runs with the selected folder as its working directory, `sys.path[0]` set to the
script's directory, and the **Python** field as interpreter (default: the one running the server).
The debugger does not restrict the script's own network access; it runs trusted
local code. Optional NumPy/pandas inspection uses packages already loaded by that
script and never installs or imports them on the debugger's behalf.

Limits: no semantic autocomplete, multi-cursor, or code folding; main thread only (threads/multiprocessing are not traced); stepping is slower than
native because `bdb` is a pure-Python tracer (~0.7 µs per function call).

## Tests

```
python -m unittest discover -s tests -v
```

End-to-end: they start the real server and a real debuggee and drive it over HTTP.
Coverage includes style persistence/validation, embedded assets and the browser
content policy, and a copy of the single-file app running with site packages
disabled and non-loopback server connections rejected by a test audit hook.

Optional editor logic checks use Node's built-in test runner (no npm packages):

```sh
node --test tests/editor.test.cjs
```

These execute the embedded application JavaScript against a small DOM test double,
covering editing commands, search/replacement, history, completion, and save races.
They do not verify browser rendering. Node is only a developer test tool; running
the debugger still requires just Python and a browser.

## Working with Codex

Open this repository in Codex. [AGENTS.md](AGENTS.md) supplies the project
instructions, commands, and behavior to preserve, using Codex's
[repository instruction convention](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
[Architecture and code map](docs/architecture.md) explains the server, worker,
browser, and their protocols. No dependency installation or frontend build is needed.

For a development session with separate settings:

```sh
python3 debugger.py examples --script demo.py --no-browser --settings /tmp/pythondebugger-settings.json
```

Open the printed URL, set a breakpoint, and press **Run**. The tests require
localhost sockets and subprocesses; the pandas table test skips if pandas is not
installed. Browser interactions need a separate manual check.
