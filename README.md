# PythonDebugger

A minimal, grayscale, browser-based Python debugger in one file (`debugger.py`).
Standard library only (Python 3.8+). Built on `bdb`, the engine behind `pdb`.

```
python debugger.py [FOLDER] [--script path/to/script.py] [--port 8765] [--no-browser]
```

It prints a URL containing a random token (localhost only); open it in Chrome.

## Using it

1. Pick a folder (Open / Browse…), click a `.py` file: it becomes the **Script** to run.
2. Click the gutter to set breakpoints (black dot), then **Run**.
3. **Continue F8 · Step Over F10 · Step Into F11 · Step Out Shift+F11**. The editor follows
   execution into other files. Click a call-stack row to inspect that frame.
4. **Variables**: expand lists, dicts, sets, enums, objects, numpy arrays, DataFrames/Series
   (`view` button opens a paged table). Values that changed since the last stop are outlined.
5. **Terminal** (bottom): while paused, type Python to run in the selected frame, e.g.
   `enabled = True` to fix a variable, or `p x` / `pp x`. While the script is running, the
   same box feeds the script's stdin.
6. **Watch** expressions re-evaluate at every stop.
7. Uncaught exceptions pause the program (post-mortem) so you can inspect the failing frames.
8. **Just my code** skips the standard library and site-packages when stepping.

The script runs with the selected folder as its working directory, `sys.path[0]` set to the
script's directory, and the **Python** field as interpreter (default: the one running the server).

Limits: main thread only (threads/multiprocessing are not traced); stepping is slower than
native because `bdb` is a pure-Python tracer (~0.7 µs per function call).

## Tests

```
python -m unittest discover -s tests -v
```

End-to-end: they start the real server and a real debuggee and drive it over HTTP.
