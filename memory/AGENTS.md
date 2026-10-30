# Session memory index

Read the root `AGENTS.md` first, then all three files below at session startup.

| File | Purpose | Update when |
| --- | --- | --- |
| `plan.md` | Current scope, completed checklist, active work, next steps, blockers | Work starts, progresses, changes scope, or finishes |
| `session-history.md` | One append-only chronological record of sessions and decisions | Meaningful progress, decisions, checks, and handoff |
| `learned-facts.md` | Durable user preferences, verified project knowledge, lessons | A fact is verified, a correction arrives, or a lesson is learned |

Keep the plan current rather than accumulating competing plans. Carry unfinished
items forward. History entries use `YYYY-MM-DD HH:MM UTC` and a few sentences;
append corrections rather than rewriting past events. Do not claim knowledge of
unavailable sessions. Facts should include their source and distinguish user
instructions from project observations. Remove or explicitly supersede stale
facts. Store no secrets or private runtime data. These are development documents,
not runtime assets, and must not become application dependencies.
