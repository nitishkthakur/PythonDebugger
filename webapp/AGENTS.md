# Web chat application index

Read root guidance before working here.

This is the reserved folder for the user's ChatGPT-like local web chat interface.
Only this guidance is implemented so far; no server, UI, or entry point exists.
The existing debugger browser page belongs to `app/`.

When implementing this app, keep browser assets and HTTP entry points here. Use
the shared `llm/` API from Python; do not duplicate inference adapters or expose
model-server credentials to the browser. Keep transport loopback-only, validate
requests, and preserve an appropriate CSP with local assets. Application startup
must be explicit, never a side effect of importing a module. Record actual files,
entry commands, and focused checks in this index as they are added.
