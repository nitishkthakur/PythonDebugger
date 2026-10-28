# PythonDebugger

A minimal browser-based Python debugger and light editor in one file (`debugger.py`).
Light/dark theme with a single configurable accent color.
Standard library only (Python 3.8+). Built on `bdb`, the engine behind `pdb`.

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

**Editing & settings.** The editor is editable (Ctrl+S saves, CRLF preserved, Tab/auto-indent, breakpoints
follow your edits). The ⚙ Settings menu sets font, theme, accent color and environment variables;
**A− / A+** or Ctrl+`+`/`-`/`0` zoom only the text (not the layout). Everything is saved to
`debugger_settings.json` next to `debugger.py` (git-ignored) and restored on the next start, together with your
last folder, script, args, breakpoints and watches. Don't put secrets in it.

The script runs with the selected folder as its working directory, `sys.path[0]` set to the
script's directory, and the **Python** field as interpreter (default: the one running the server).

Limits: no autocomplete/search-replace; main thread only (threads/multiprocessing are not traced); stepping is slower than
native because `bdb` is a pure-Python tracer (~0.7 µs per function call).

## Tests

```
python -m unittest discover -s tests -v
```

End-to-end: they start the real server and a real debuggee and drive it over HTTP.
