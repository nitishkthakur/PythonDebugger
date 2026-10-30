"""Validated preferences, settings persistence, and environment parsing."""
from __future__ import annotations

import json
import os
import re
import threading

# Preserve the settings location used before the application moved.
HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debugger.py")


DEFAULT_PREFS = {"font_size": 14, "font": "default", "line": "normal", "theme": "light",
                 "accent": "#d71e28", "layout": {}, "editor_theme": "match", "editor_colors": {}}
FONT_KEYS = ("default", "courier", "lucida", "system", "sans")
THEME_KEYS = ("light", "dark", "midnight", "sepia", "forest", "contrast")
EDITOR_COLOR_KEYS = ("background", "text", "keyword", "string", "comment", "number", "gutter")
SESSION_KEYS = ("root", "script", "args", "python", "stop_on_entry", "jmc", "env", "dotenv")


def clean_prefs(src, base=None):
    out = dict(base if base is not None else DEFAULT_PREFS)
    if not isinstance(src, dict):
        return out
    try:
        out["font_size"] = max(9, min(32, int(src.get("font_size", out["font_size"]))))
    except (TypeError, ValueError):
        pass
    if src.get("font") in FONT_KEYS:
        out["font"] = src["font"]
    if src.get("line") in ("compact", "normal", "relaxed"):
        out["line"] = src["line"]
    if src.get("theme") in THEME_KEYS:
        out["theme"] = src["theme"]
    if src.get("editor_theme") in ("match",) + THEME_KEYS:
        out["editor_theme"] = src["editor_theme"]
    if isinstance(src.get("editor_colors"), dict):
        out["editor_colors"] = {k: v for k, v in src["editor_colors"].items()
                                if k in EDITOR_COLOR_KEYS and isinstance(v, str)
                                and re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v)}
    if isinstance(src.get("accent"), str) and re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", src["accent"]):
        out["accent"] = src["accent"]
    if isinstance(src.get("layout"), dict):
        lay = {}
        for k in ("left", "right", "cons"):
            try:
                v = int(src["layout"].get(k))
                if 60 <= v <= 4000:
                    lay[k] = v
            except (TypeError, ValueError):
                pass
        out["layout"] = lay
    return out


class SettingsStore:
    """UI preferences + last session (folder, script, args, breakpoints, watches)."""

    def __init__(self, path=None):
        self.path = path or self.default_path()
        self.lock = threading.Lock()
        self.error = ""
        self.data = {"version": 1, "prefs": dict(DEFAULT_PREFS), "session": {}, "breakpoints": {}, "watches": []}
        self.load()

    @staticmethod
    def default_path():
        here = os.path.dirname(HERE)
        if os.access(here, os.W_OK):
            return os.path.join(here, "debugger_settings.json")
        return os.path.join(os.path.expanduser("~"), ".debugger_py_settings.json")

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            self.error = "ignored unreadable settings file (%s)" % e
            return
        if not isinstance(raw, dict):
            return
        self.data["prefs"] = clean_prefs(raw.get("prefs"))
        if isinstance(raw.get("session"), dict):
            self.data["session"] = {k: v for k, v in raw["session"].items() if k in SESSION_KEYS}
        if isinstance(raw.get("breakpoints"), dict):
            self.data["breakpoints"] = {f: [x for x in ls if isinstance(x, int)]
                                        for f, ls in raw["breakpoints"].items() if isinstance(ls, list)}
        if isinstance(raw.get("watches"), list):
            self.data["watches"] = [w for w in raw["watches"] if isinstance(w, str)]

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, indent=2, sort_keys=True)
                os.replace(tmp, self.path)
                self.error = ""
            except OSError as e:
                self.error = "cannot write settings: %s" % e


def parse_env(text, expand=False):
    """KEY=VALUE lines (also `export KEY=VALUE`, quotes, # comments)."""
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        elif " #" in v:
            v = v.split(" #", 1)[0].rstrip()
        if k:
            out[k] = os.path.expandvars(v) if expand else v
    return out
