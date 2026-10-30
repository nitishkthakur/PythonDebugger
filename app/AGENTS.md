# Debugger application index

Read root guidance before working here. This folder owns the existing local
Python debugger, including its browser UI; `webapp/` is a separate chat app.

| File | Responsibility |
| --- | --- |
| `__init__.py` | Package marker; no startup side effects |
| `__main__.py` | `python3 -m app` entry point |
| `debugger.py` | Session/process lifecycle, source access, authenticated HTTP/SSE, server and CLI startup |
| `worker.py` | Inspection, static hover, bdb tracing, stepping, console evaluation, worker socket entry |
| `settings.py` | Preference validation, atomic settings persistence, environment parsing |
| `ui.py` | Local PAGE_HTML, CSS, JavaScript, and MANUAL |

Entry points from the root: `python3 -m app`, `python3 app/debugger.py`, and the
compatibility launcher `python3 debugger.py`. Workers launch through the absolute
`app/debugger.py` path so changing the debuggee working directory cannot break
imports. Keep worker tracing exclusions aligned with the worker module location.

Settings default to `debugger_settings.json` in the repository/distribution root
to preserve existing saved sessions, with the existing home-directory fallback.
Use temporary settings in checks. Never move, overwrite, or commit user settings
as part of a code reorganization.

Preserve root security, tracing, frame mutation, and subprocess-generation rules.
Use existing base contracts (`bdb.Bdb` and HTTP server/handler classes); introduce
new abstract parents only for actual interchangeable implementations. Future LLM
integration imports `llm/` rather than duplicating backends here.

Run `python3 -m unittest discover -s tests -v` and
`node --test tests/editor.test.cjs` from the root for this migration. A copied
application folder must still work without site packages or external connections.
Keep local page behavior unchanged during module extraction. Update this index
and `docs/architecture.md` when responsibilities move again.
