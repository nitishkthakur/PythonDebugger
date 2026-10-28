#!/usr/bin/env python3
"""debugger.py - a minimal browser-based Python debugger. Standard library only.

    python debugger.py [FOLDER] [--script FILE] [--port N] [--no-browser]

Opens a local web page (grayscale IDE-lite): file tree, code view with
clickable breakpoints, step over / into / out / continue, call stack,
variables (lists, dicts, sets, enums, objects, numpy arrays, pandas
DataFrames), watch expressions, and a Python terminal that evaluates in the
selected frame (so you can fix a variable on the fly).

Design: this process is the web server. The script runs in a child process
(`python debugger.py --worker ...`) under a bdb.Bdb subclass (the engine pdb
is built on) and talks to the server over a localhost socket (JSON lines).
The browser talks to the server via fetch() and Server-Sent Events.
Only the main thread of the debugged script is traced.
"""
from __future__ import annotations

import bdb
import builtins
import collections
import contextlib
import enum
import hmac
import http.server
import io
import itertools
import json
import os
import pprint
import queue
import reprlib
import secrets
import shlex
import socket
import subprocess
import sys
import sysconfig
import threading
import time
import traceback
import types
import urllib.parse
import webbrowser

HERE = os.path.realpath(os.path.abspath(__file__))
PAGE = 100          # children / rows fetched per expand
MAX_FILE = 5 * 1024 * 1024
MAX_OUTPUT = 1_000_000


# ============================================================================
# Worker side: runs inside the debuggee process
# ============================================================================

def _short(s, n=200):
    s = str(s)
    return s if len(s) <= n else s[:n] + "…"


_rep = reprlib.Repr()
_rep.maxlevel = 2
_rep.maxlist = _rep.maxtuple = _rep.maxset = _rep.maxfrozenset = 6
_rep.maxdeque = _rep.maxarray = 6
_rep.maxdict = 4
_rep.maxstring = 80
_rep.maxother = 120


def _pd():
    return sys.modules.get("pandas")


def _np():
    return sys.modules.get("numpy")


def _is_df(o):
    pd = _pd()
    return pd is not None and isinstance(o, pd.DataFrame)


def _is_series(o):
    pd = _pd()
    return pd is not None and isinstance(o, pd.Series)


def _is_nd(o):
    np = _np()
    return np is not None and isinstance(o, np.ndarray) and o.ndim >= 1


_SCALARS = (type(None), bool, int, float, complex, str, bytes, bytearray, range)
_OPAQUE = (type, types.ModuleType, types.FunctionType, types.BuiltinFunctionType,
           types.MethodType, types.GeneratorType)


def _kind(o):
    """How an object expands in the variable tree (None = leaf)."""
    if isinstance(o, _SCALARS) or isinstance(o, _OPAQUE):
        return None
    if _is_df(o):
        return "df"
    if _is_series(o):
        return "series"
    if _is_nd(o):
        return "nd" if o.shape and o.shape[0] > 0 else None
    if isinstance(o, dict):
        return "dict" if len(o) else None
    if isinstance(o, (list, tuple, collections.deque)):
        return "seq" if len(o) else None
    if isinstance(o, (set, frozenset)):
        return "set" if len(o) else None
    if isinstance(o, enum.Enum):
        return "enum"
    if _obj_attrs(o):
        return "obj"
    return None


def _obj_attrs(o):
    out = []
    try:
        d = vars(o)
    except TypeError:
        d = None
    if d:
        out.extend((k, v) for k, v in list(d.items()) if not str(k).startswith("__"))
    for cls in type(o).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for s in slots:
            if s.startswith("__") or s in ("__dict__", "__weakref__"):
                continue
            try:
                out.append((s, getattr(o, s)))
            except AttributeError:
                pass
    if not out and isinstance(o, BaseException) and o.args:
        out.append(("args", o.args))
    return out


def _sized(o):
    try:
        return len(o)
    except Exception:
        return None


def _type_label(o):
    t = type(o).__name__
    if _is_nd(o):
        return "ndarray"
    n = _sized(o) if isinstance(o, (dict, list, tuple, set, frozenset, collections.deque, str, bytes)) else None
    return "%s (%d)" % (t, n) if n is not None and not isinstance(o, (str, bytes)) else t


def _summary(o):
    try:
        np = _np()
        if _is_df(o):
            return "%d rows × %d columns" % o.shape
        if _is_series(o):
            return "len=%d dtype=%s" % (len(o), o.dtype)
        if _is_nd(o):
            return "shape=%s dtype=%s" % (tuple(o.shape), o.dtype)
        if np is not None and isinstance(o, np.generic):
            return str(o)
        if isinstance(o, str):
            r = repr(o if len(o) <= 200 else o[:200])
            return r + ("… (len %d)" % len(o) if len(o) > 200 else "")
        if isinstance(o, (bool, int, float, complex, type(None))):
            return repr(o)
        s = _rep.repr(o)
    except Exception as e:  # a broken __repr__ must never break the UI
        s = "<repr failed: %s>" % e
    return " ".join(s.split("\n"))


def _cell(v):
    try:
        return _short(str(v), 60)
    except Exception:
        return "?"


class Inspector:
    """Builds the variable tree lazily; keeps id -> object until execution resumes."""

    def __init__(self):
        self.refs = {}
        self.n = 0

    def clear(self):
        self.refs.clear()

    def node(self, name, o):
        n = {"name": str(name), "type": _type_label(o), "value": _summary(o)}
        k = _kind(o)
        if k:
            self.n += 1
            self.refs[self.n] = o
            n["ref"] = self.n
        if k in ("df", "series") or (k == "nd" and o.ndim in (1, 2)):
            n["table"] = True
        return n

    def page(self, items, ref, offset, total_known=None):
        """items: iterable of (name, obj), already positioned at `offset`."""
        items = list(itertools.islice(items, PAGE + 1))
        out = [self.node(k, v) for k, v in items[:PAGE]]
        if len(items) > PAGE:
            out.append({"more": True, "ref": ref, "offset": offset + PAGE})
        return out

    def children(self, ref, offset=0):
        o = self.refs.get(ref)
        if o is None:
            return None
        k = _kind(o)
        sl = lambda it: itertools.islice(it, offset, None)
        if k == "dict":
            return self.page(((_short(repr(a), 60), b) for a, b in sl(list(o.items()))), ref, offset)
        if k == "seq":
            fields = getattr(o, "_fields", None)
            names = (lambda i: fields[i] if fields and i < len(fields) else "[%d]" % i)
            return self.page(((names(i + offset), v) for i, v in enumerate(sl(o))), ref, offset)
        if k == "set":
            try:
                items = sorted(o) if len(o) <= 2000 else list(o)
            except Exception:
                items = list(o)
            return self.page((("{%d}" % (i + offset), v) for i, v in enumerate(sl(items))), ref, offset)
        if k == "enum":
            return [self.node("name", o.name), self.node("value", o.value)]
        if k == "obj":
            return self.page(sl(_obj_attrs(o)), ref, offset)
        if k == "nd":
            n = o.shape[0]
            return self.page((("[%d]" % i, o[i]) for i in range(offset, n)), ref, offset)
        if k == "series":
            return self._series_page(o, ref, offset)
        if k == "df":
            ncol = o.shape[1]
            return self.page(((str(o.columns[j]), o.iloc[:, j]) for j in range(offset, ncol)), ref, offset)
        return []

    def _series_page(self, o, ref, offset):
        sub = o.iloc[offset:offset + PAGE + 1]
        items = list(sub.items())
        out = [self.node(_short(repr(i), 60), v) for i, v in items[:PAGE]]
        if len(items) > PAGE:
            out.append({"more": True, "ref": ref, "offset": offset + PAGE})
        return out

    def table(self, ref, r0, c0, nrows=50, ncols=20):
        o = self.refs.get(ref)
        if o is None:
            return None
        if _is_df(o):
            sub = o.iloc[r0:r0 + nrows, c0:c0 + ncols]
            return {"shape": list(o.shape), "r0": r0, "c0": c0,
                    "cols": [str(c) for c in sub.columns], "idx": [str(i) for i in sub.index],
                    "rows": [[_cell(v) for v in row] for row in sub.values.tolist()],
                    "dtypes": [str(t) for t in sub.dtypes], "kind": "DataFrame"}
        if _is_series(o):
            sub = o.iloc[r0:r0 + nrows]
            return {"shape": [len(o), 1], "r0": r0, "c0": 0,
                    "cols": [str(o.name) if o.name is not None else "value"],
                    "idx": [str(i) for i in sub.index], "rows": [[_cell(v)] for v in sub.tolist()],
                    "dtypes": [str(o.dtype)], "kind": "Series"}
        if _is_nd(o) and o.ndim in (1, 2):
            if o.ndim == 1:
                sub = o[r0:r0 + nrows]
                rows = [[_cell(v)] for v in sub.tolist()]
                cols = ["value"]
                shape = [o.shape[0], 1]
            else:
                sub = o[r0:r0 + nrows, c0:c0 + ncols]
                rows = [[_cell(v) for v in row] for row in sub.tolist()]
                cols = [str(j) for j in range(c0, c0 + sub.shape[1])]
                shape = list(o.shape)
            return {"shape": shape, "r0": r0, "c0": c0, "cols": cols,
                    "idx": [str(i) for i in range(r0, r0 + len(rows))], "rows": rows,
                    "dtypes": [str(o.dtype)] * len(cols), "kind": "ndarray"}
        return None


def _locals_to_fast(frame):
    """Before 3.13 f_locals is a snapshot; push edits made from the console back."""
    if sys.version_info >= (3, 13):
        return
    try:
        import ctypes
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))
    except Exception:
        pass


def _lib_dirs():
    dirs = set()
    for k in ("stdlib", "platstdlib", "purelib", "platlib"):
        try:
            dirs.add(sysconfig.get_path(k))
        except Exception:
            pass
    try:
        import site
        dirs.update(site.getsitepackages())
        dirs.add(site.getusersitepackages())
    except Exception:
        pass
    return tuple(os.path.normcase(os.path.realpath(d)) + os.sep for d in dirs if d)


class Dbg(bdb.Bdb):
    def __init__(self, sock, jmc=True, stop_on_entry=False):
        super().__init__()
        self.sock = sock
        self.sendlock = threading.Lock()
        self.cmdq = queue.Queue()
        self.insp = Inspector()
        self.jmc = jmc
        self.stop_on_entry = stop_on_entry
        self.first_stop = True
        self.stack = []
        self.top = None
        self.idx = 0
        self.watches = []
        self.out_frame = None
        self.libs = _lib_dirs()
        self.user_cache = {}
        self.main_ident = threading.get_ident()
        self.reset()  # defines botframe etc. before the reader thread can touch them

    # -- plumbing ------------------------------------------------------------
    def send(self, obj):
        data = (json.dumps(obj, default=str) + "\n").encode("utf-8")
        with self.sendlock:
            self.sock.sendall(data)

    def reader(self):
        try:
            for line in self.sock.makefile("rb"):
                m = json.loads(line)
                c = m.get("c")
                if c == "breaks":
                    self.apply_breaks(m["files"])
                elif c == "opts":
                    self.jmc = bool(m.get("jmc", True))
                else:
                    self.cmdq.put(m)
        except Exception:
            traceback.print_exc()
        os._exit(1)  # server went away

    def canonic(self, filename):
        if filename.startswith("<") and filename.endswith(">"):
            return filename
        c = self.fncache.get(filename)
        if not c:
            c = os.path.normcase(os.path.realpath(filename))
            self.fncache[filename] = c
        return c

    def is_user(self, fn):
        r = self.user_cache.get(fn)
        if r is None:
            if fn.startswith("<"):
                r = False
            else:
                real = os.path.normcase(os.path.realpath(fn))
                r = not real.startswith(self.libs) and os.path.realpath(fn) != HERE
            self.user_cache[fn] = r
        return r

    # -- breakpoints ---------------------------------------------------------
    def apply_breaks(self, files):
        want = {self.canonic(f): set(ls) for f, ls in files.items() if ls}
        have = {f: set(ls) for f, ls in self.breaks.items()}
        for f in set(have) | set(want):
            for ln in have.get(f, set()) - want.get(f, set()):
                self.clear_break(f, ln)
            for ln in want.get(f, set()) - have.get(f, set()):
                self.set_break(f, ln)
        # frames that are already running were started without line tracing
        fr = sys._current_frames().get(self.main_ident)
        while fr is not None and fr is not self.botframe:
            fr.f_trace = self.trace_dispatch
            fr = fr.f_back

    # -- stepping policy -----------------------------------------------------
    def stop_here(self, frame):
        if self.jmc and not self.is_user(frame.f_code.co_filename):
            return False
        return super().stop_here(frame)

    def set_continue(self):
        # unlike Bdb.set_continue, keep the tracer installed so breakpoints
        # added while the script runs still fire
        self._set_stopinfo(self.botframe, None, -1)

    def user_call(self, frame, args):
        pass  # land on the first body line, not the `def` line

    def user_return(self, frame, rv):
        if frame is self.out_frame:
            self.out_frame = None
            self.set_step()  # step out: stop in the caller

    def user_exception(self, frame, exc_info):
        pass

    def user_line(self, frame):
        if self.first_stop and self.stop_on_entry:
            reason = "entry"
        elif self.get_break(self.canonic(frame.f_code.co_filename), frame.f_lineno):
            reason = "breakpoint"
        else:
            reason = "step"
        self.first_stop = False
        self.top = frame
        self.interact(frame, None, reason)

    # -- the stopped state ---------------------------------------------------
    def interact(self, frame, tb, reason, exc_text=None):
        stack, _ = self.get_stack(frame, tb)
        self.stack = [(f, ln) for f, ln in stack
                      if f is not self.botframe and os.path.realpath(f.f_code.co_filename) != HERE]
        if not self.stack:
            return
        idx = len(self.stack) - 1
        if reason == "exception":
            for i in range(idx, -1, -1):
                if self.is_user(self.stack[i][0].f_code.co_filename):
                    idx = i
                    break
        self.idx = idx
        msg = {"t": "stopped", "reason": reason, "idx": idx, "exc": exc_text,
               "stack": [{"file": os.path.abspath(f.f_code.co_filename), "line": ln,
                          "func": f.f_code.co_name, "user": self.is_user(f.f_code.co_filename)}
                         for f, ln in self.stack]}
        msg.update(self.frame_vars(idx))
        self.send(msg)
        self.loop(reason == "exception")

    def loop(self, postmortem):
        while True:
            m = self.cmdq.get()
            c = m.get("c")
            if c in ("step", "next", "out", "continue"):
                if postmortem:
                    return
                self.insp.clear()
                top = self.top
                if c == "step":
                    self.set_step()
                elif c == "next":
                    self.set_next(top)
                elif c == "out":
                    self.out_frame = top
                    self.set_return(top)
                else:
                    self.set_continue()
                while True:  # drop inspection requests that raced the resume
                    try:
                        self.cmdq.get_nowait()
                    except queue.Empty:
                        break
                return
            try:
                self.inspect(m)
            except Exception as e:
                self.send({"t": "evalres", "id": m.get("id"), "out": "debugger error: %r" % e, "err": True})

    def inspect(self, m):
        c = m["c"]
        if c == "frame":
            self.idx = m["idx"]
            self.send(dict(t="vars", **self.frame_vars(self.idx)))
        elif c == "watches":
            self.watches = m["list"]
            self.send(dict(t="vars", **self.frame_vars(self.idx)))
        elif c == "eval":
            self.idx = m["frame"]
            out, err = self.console(m["src"], self.stack[self.idx][0])
            self.send({"t": "evalres", "id": m["id"], "out": out, "err": err})
            self.send(dict(t="vars", **self.frame_vars(self.idx)))
        elif c == "expand":
            ch = self.insp.children(m["ref"], m.get("offset", 0))
            self.send({"t": "expanded", "id": m["id"], "children": ch, "error": None if ch is not None else "stale"})
        elif c == "table":
            self.send({"t": "tabled", "id": m["id"],
                       "data": self.insp.table(m["ref"], m.get("r0", 0), m.get("c0", 0))})

    def frame_vars(self, idx):
        frame = self.stack[idx][0]
        loc, glob = frame.f_locals, frame.f_globals
        skip = lambda k: str(k).startswith("__") or str(k).startswith(".")
        L = [] if loc is glob else [self.insp.node(k, v) for k, v in list(loc.items()) if not skip(k)][:500]
        G = [self.insp.node(k, v) for k, v in list(glob.items())
             if not skip(k) and not isinstance(v, _OPAQUE)][:500]
        W = []
        for expr in self.watches:
            try:
                W.append(self.insp.node(expr, eval(expr, glob, loc)))
            except BaseException as e:
                W.append({"name": expr, "error": "%s: %s" % (type(e).__name__, e)})
        return {"frame": idx, "locals": L, "globals": G, "watch": W,
                "scope": "module" if loc is glob else "function"}

    def console(self, src, frame):
        g, l = frame.f_globals, frame.f_locals
        src = src.rstrip()
        buf = io.StringIO()
        err = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                try:
                    code = compile(src, "<console>", "eval")
                except SyntaxError:
                    code = None
                    s = src.strip()
                    # pdb-style `p x` / `pp x`
                    for pre, wrap in (("pp ", "__import__('pprint').pprint(%s)"), ("p ", "%s")):
                        if s.startswith(pre):
                            try:
                                code = compile(wrap % s[len(pre):], "<console>", "eval")
                            except SyntaxError:
                                pass
                            break
                if code is not None:
                    v = eval(code, g, l)
                    if v is not None:
                        text = repr(v)
                        if len(text) > 100:
                            text = pprint.pformat(v, width=100, compact=True)
                        print(_short(text, 20000))
                else:
                    exec(compile(src, "<console>", "exec"), g, l)
            except BaseException as e:
                err = True
                tb = e.__traceback__.tb_next if e.__traceback__ else None
                if tb is not None:
                    traceback.print_exception(type(e), e, tb)
                else:
                    print("".join(traceback.format_exception_only(type(e), e)).rstrip())
        _locals_to_fast(frame)
        return buf.getvalue().rstrip("\n"), err

    # -- running the script --------------------------------------------------
    def run_script(self, script, args):
        script = os.path.abspath(script)
        with open(script, "rb") as fh:
            source = fh.read()
        sys.argv = [script] + args
        sys.path[0] = os.path.dirname(script)
        main = types.ModuleType("__main__")
        main.__dict__.update(__file__=script, __builtins__=builtins, __doc__=None)
        sys.modules["__main__"] = main
        try:
            code = compile(source, script, "exec")
        except SyntaxError:
            traceback.print_exc(limit=0)
            return 1
        code_ret = 0
        try:
            self.reset()
            self.botframe = sys._getframe()
            self.set_step() if self.stop_on_entry else self.set_continue()
            sys.settrace(self.trace_dispatch)
            try:
                exec(code, main.__dict__)
            finally:
                sys.settrace(None)
                self.quitting = True
        except bdb.BdbQuit:
            pass
        except SystemExit as e:
            if e.code is None:
                code_ret = 0
            elif isinstance(e.code, int):
                code_ret = e.code
            else:
                print(e.code, file=sys.stderr)
                code_ret = 1
        except BaseException as e:
            code_ret = 1
            tb = e.__traceback__.tb_next
            traceback.print_exception(type(e), e, tb)
            sys.stderr.flush()
            self.quitting = False
            self.top = None
            self.interact(None, tb, "exception", "".join(traceback.format_exception_only(type(e), e)).strip())
        return code_ret


def worker_main(port, script, args):
    sock = socket.create_connection(("127.0.0.1", port))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    opts = json.loads(os.environ.get("DBG_OPTS", "{}"))
    dbg = Dbg(sock, jmc=opts.get("jmc", True), stop_on_entry=opts.get("stop_on_entry", False))
    dbg.send({"t": "hello", "token": os.environ.get("DBG_TOKEN", "")})
    threading.Thread(target=dbg.reader, daemon=True).start()
    first = dbg.cmdq.get()  # server sends the initial breakpoints and then "go"
    assert first.get("c") == "go"
    code = dbg.run_script(script, args)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    dbg.send({"t": "exited", "code": code})
    sys.exit(code)


# ============================================================================
# Server side
# ============================================================================

class Session:
    """One debugging session: config, the child process, and event fan-out."""

    def __init__(self, root, script, token):
        self.token = token
        self.lock = threading.RLock()
        self.cfg = {"root": root, "script": script, "args": "", "python": sys.executable,
                    "stop_on_entry": False, "jmc": True}
        self.state = "idle"
        self.status = ""
        self.breaks = {}
        self.watches = []
        self.stop = None
        self.vars = None
        self.output = []
        self.out_len = 0
        self.clients = []
        self.proc = None
        self.conn = None
        self.run_id = 0
        self.send_lock = threading.Lock()

    # -- events ----------------------------------------------------------------
    def emit(self, ev):
        with self.lock:
            for q in list(self.clients):
                q.put(ev)

    def snapshot(self):
        return {"t": "snapshot", "cfg": self.cfg, "state": self.state, "status": self.status,
                "stop": self.stop, "vars": self.vars, "output": self.output,
                "breaks": {f: sorted(ls) for f, ls in self.breaks.items()}, "watches": self.watches}

    def add_client(self):
        q = queue.Queue()
        with self.lock:
            self.clients.append(q)
            q.put(self.snapshot())
        return q

    def drop_client(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def set_state(self, state, status=""):
        with self.lock:
            self.state, self.status = state, status
            if state != "paused":
                self.stop = self.vars = None
        self.emit({"t": "state", "state": state, "status": status})

    def out(self, stream, text):
        if not text:
            return
        with self.lock:
            self.output.append([stream, text])
            self.out_len += len(text)
            while self.out_len > MAX_OUTPUT and len(self.output) > 1:
                self.out_len -= len(self.output.pop(0)[1])
        self.emit({"t": "output", "stream": stream, "text": text})

    # -- config --------------------------------------------------------------
    def update_cfg(self, new):
        with self.lock:
            for k in self.cfg:
                if k in new:
                    self.cfg[k] = new[k]
        if self.state in ("paused", "running"):
            self.to_worker({"c": "opts", "jmc": bool(self.cfg["jmc"])})

    def resolve(self, p):
        return p if os.path.isabs(p) else os.path.join(self.cfg["root"], p)

    # -- process control -----------------------------------------------------
    def start(self):
        self.stop_proc(quiet=True)
        cfg = self.cfg
        if not cfg["script"]:
            self.out("sys", "[no script selected]\n")
            return
        script = self.resolve(cfg["script"])
        if not os.path.isfile(script):
            self.out("sys", "[script not found: %s]\n" % script)
            return
        self.run_id += 1
        rid = self.run_id
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(20)
        port = listener.getsockname()[1]
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
                   DBG_TOKEN=self.token,
                   DBG_OPTS=json.dumps({"jmc": bool(cfg["jmc"]), "stop_on_entry": bool(cfg["stop_on_entry"])}))
        try:
            args = shlex.split(cfg["args"], posix=(os.name != "nt"))
            args = [a[1:-1] if len(a) > 1 and a[0] == a[-1] and a[0] in "\"'" else a for a in args]
        except ValueError as e:
            self.out("sys", "[bad arguments: %s]\n" % e)
            return
        cmd = [cfg["python"] or sys.executable, "-u", HERE, "--worker", str(port), script] + args
        root = cfg["root"] if os.path.isdir(cfg["root"]) else os.path.dirname(script)
        try:
            proc = subprocess.Popen(cmd, cwd=root, env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as e:
            self.out("sys", "[cannot start %s: %s]\n" % (cmd[0], e))
            listener.close()
            return
        with self.lock:
            self.proc = proc
            self.conn = None
        self.out("sys", "[run] %s %s\n" % (os.path.basename(script), cfg["args"]))
        self.set_state("running", "starting")
        for stream, pipe in (("out", proc.stdout), ("err", proc.stderr)):
            threading.Thread(target=self._pump, args=(rid, stream, pipe), daemon=True).start()
        threading.Thread(target=self._serve_worker, args=(rid, proc, listener), daemon=True).start()

    def _pump(self, rid, stream, pipe):
        import codecs
        dec = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            chunk = pipe.read1(4096) if hasattr(pipe, "read1") else pipe.read(4096)
            if not chunk:
                break
            if rid == self.run_id:
                self.out(stream, dec.decode(chunk))

    def _serve_worker(self, rid, proc, listener):
        conn = None
        try:
            conn, _ = listener.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            listener.close()
            f = conn.makefile("rb")
            hello = json.loads(f.readline())
            if hello.get("t") != "hello" or not hmac.compare_digest(hello.get("token", ""), self.token):
                raise RuntimeError("bad worker handshake")
            with self.lock:
                if rid != self.run_id:
                    return
                self.conn = conn
            self.to_worker({"c": "breaks", "files": {f_: sorted(l_) for f_, l_ in self.breaks.items()}})
            self.to_worker({"c": "go"})
            self.set_state("running", "")
            for line in f:
                if rid != self.run_id:
                    return
                self.on_worker(json.loads(line))
        except Exception as e:
            if rid == self.run_id and proc.poll() is None:
                self.out("sys", "[debugger connection error: %s]\n" % e)
        finally:
            for sk in (listener, conn):
                try:
                    sk.close()
                except Exception:
                    pass
        if rid == self.run_id:
            proc.wait()
            time.sleep(0.15)  # let the pipe pumps drain
            with self.lock:
                if rid != self.run_id:
                    return
                done = self.state != "idle"
            if done:
                self.out("sys", "[process exited with code %s]\n" % proc.returncode)
                self.set_state("idle", "exited %s" % proc.returncode)

    def on_worker(self, m):
        t = m["t"]
        if t == "stopped":
            for fr in m["stack"]:
                fr["file"] = os.path.realpath(fr["file"]) if os.path.exists(fr["file"]) else fr["file"]
                fr["exists"] = os.path.exists(fr["file"])
            with self.lock:
                self.stop = {k: m[k] for k in ("reason", "idx", "exc", "stack")}
                self.vars = {k: m[k] for k in ("frame", "locals", "globals", "watch", "scope")}
            self.set_state("paused", m["reason"])
            self.emit({"t": "stopped", **self.stop, "vars": self.vars})
        elif t == "vars":
            with self.lock:
                self.vars = {k: m[k] for k in ("frame", "locals", "globals", "watch", "scope")}
            self.emit({"t": "vars", **self.vars})
        elif t in ("evalres", "expanded", "tabled"):
            self.emit(m)
        elif t == "exited":
            pass  # the process-exit path reports it

    def to_worker(self, msg):
        with self.lock:
            conn = self.conn
        if conn is None:
            return False
        data = (json.dumps(msg) + "\n").encode("utf-8")
        try:
            with self.send_lock:
                conn.sendall(data)
            return True
        except OSError:
            return False

    def command(self, name, body):
        """Resume / inspection commands forwarded to the worker."""
        if name in ("step", "next", "out", "continue"):
            if self.state != "paused":
                return
            self.set_state("running", "")
            self.to_worker({"c": name})
        elif name in ("frame", "eval", "expand", "table"):
            if self.state == "paused":
                self.to_worker(dict(body, c=name))
        elif name == "watches":
            self.watches = list(body.get("list", []))
            if self.state == "paused":
                self.to_worker({"c": "watches", "list": self.watches})
        elif name == "breaks":
            self.breaks = {f: set(ls) for f, ls in body.get("files", {}).items() if ls}
            self.to_worker({"c": "breaks", "files": {f: sorted(ls) for f, ls in self.breaks.items()}})
        elif name == "stdin":
            proc = self.proc
            if proc and proc.poll() is None and self.state == "running":
                try:
                    proc.stdin.write(body.get("text", "").encode("utf-8"))
                    proc.stdin.flush()
                    self.out("in", body.get("text", ""))
                except OSError:
                    pass

    def stop_proc(self, quiet=False):
        with self.lock:
            proc, conn, self.proc, self.conn = self.proc, self.conn, None, None
            self.run_id += 1
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        if proc and proc.poll() is None:
            proc.kill()
            for pipe in (proc.stdin,):
                try:
                    pipe.close()
                except Exception:
                    pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            if not quiet:
                self.out("sys", "[stopped]\n")
        if proc or self.state != "idle":
            self.set_state("idle", "stopped" if not quiet else "")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _list_dir(path, files):
    if not path:
        if os.name == "nt":
            roots = ["%s:\\" % c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists("%s:\\" % c)]
        else:
            roots = [os.sep]
        return {"path": "", "parent": None, "entries": [{"name": r, "dir": True, "path": r} for r in roots]}
    path = os.path.realpath(path)
    entries = []
    try:
        names = os.listdir(path)
    except OSError as e:
        return {"error": str(e), "path": path}
    for n in names:
        if n in ("__pycache__", ".git", ".DS_Store") or n.endswith(".pyc"):
            continue
        full = os.path.join(path, n)
        isdir = os.path.isdir(full)
        if isdir or files:
            entries.append({"name": n, "dir": isdir, "path": full})
    entries.sort(key=lambda e: (not e["dir"], e["name"].lower()))
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else "", "entries": entries}


def _read_file(path):
    real = os.path.realpath(path)
    try:
        if os.path.getsize(real) > MAX_FILE:
            return {"error": "file too large", "path": real}
        with open(real, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return {"error": str(e), "path": real}
    if b"\0" in data[:4096]:
        return {"error": "binary file", "path": real}
    return {"path": real, "text": data.decode("utf-8", "replace").replace("\r\n", "\n")}


def make_handler(sess):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *a):
            pass

        def _ok(self):
            host = self.headers.get("Host", "").rsplit(":", 1)[0]
            if host not in ("127.0.0.1", "localhost", "[::1]"):
                return False
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            tok = self.headers.get("X-Token") or (q.get("t") or [""])[0]
            return hmac.compare_digest(tok, sess.token)

        def _json(self, obj, code=200):
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            if u.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if not self._ok():
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"forbidden: open the URL printed by debugger.py (it contains the token)")
                return
            if u.path == "/":
                data = PAGE_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif u.path == "/events":
                self._events()
            elif u.path == "/api/ls":
                self._json(_list_dir(q.get("path", ""), q.get("files") == "1"))
            elif u.path == "/api/file":
                self._json(_read_file(q.get("path", "")))
            elif u.path == "/api/state":
                with sess.lock:
                    self._json(sess.snapshot())
            else:
                self.send_response(404)
                self.end_headers()

        def _events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            q = sess.add_client()
            try:
                while True:
                    try:
                        ev = q.get(timeout=15)
                        self.wfile.write(b"data: " + json.dumps(ev).encode("utf-8") + b"\n\n")
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (OSError, ValueError):
                pass
            finally:
                sess.drop_client(q)

        def do_POST(self):
            if not self._ok():
                return self._json({"error": "forbidden"}, 403)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json({"error": "bad json"}, 400)
            name = self.path[len("/api/"):] if self.path.startswith("/api/") else ""
            if name == "config":
                sess.update_cfg(body)
            elif name in ("run", "restart"):
                sess.update_cfg(body)
                sess.start()
            elif name == "stop":
                sess.stop_proc()
            else:
                sess.command(name, body)
            self._json({"ok": True})

    return Handler


def serve(root, script, port, open_browser):
    token = secrets.token_urlsafe(16)
    sess = Session(root, script, token)
    handler = make_handler(sess)
    httpd = None
    for p in range(port, port + 50):
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit("no free port near %d" % port)
    httpd.daemon_threads = True
    url = "http://127.0.0.1:%d/?t=%s" % (httpd.server_address[1], token)
    print("debugger.py serving %s\nOpen: %s\n(Ctrl+C to quit)" % (root, url), flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sess.stop_proc(quiet=True)
    return httpd, sess


def main(argv):
    if len(argv) > 1 and argv[1] == "--worker":
        return worker_main(int(argv[2]), argv[3], argv[4:])
    import argparse
    ap = argparse.ArgumentParser(description="Minimal browser-based Python debugger")
    ap.add_argument("folder", nargs="?", default=os.getcwd())
    ap.add_argument("--script", default="", help="script to run (relative to folder)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv[1:])
    root = os.path.realpath(a.folder)
    if not os.path.isdir(root):
        sys.exit("not a folder: %s" % root)
    serve(root, a.script, a.port, not a.no_browser)


# ============================================================================
# Browser UI (single page, grayscale)
# ============================================================================

PAGE_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>debugger.py</title>
<style>
:root{--left:230px;--right:340px;--cons:220px;--bg:#ececec;--pn:#fff;--bd:#b4b4b4;--tx:#1c1c1c;--dim:#777;--sel:#d4d4d4;--red:#d71e28;--red-d:#a3141c;--red-m:#f0b3b6;--red-l:#fbe4e5;--red-xl:#fdf3f3;
 --mono:Consolas,Menlo,"DejaVu Sans Mono",monospace}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--tx);font:12px/1.4 var(--mono)}
body{display:grid;grid-template-rows:auto auto minmax(0,1fr)}
input,button,textarea{font:inherit;color:inherit}
input[type=text]{border:1px solid var(--bd);background:#fff;padding:2px 4px;min-width:0}
button{border:1px solid #888;background:#e2e2e2;padding:2px 8px;cursor:pointer}
button:hover:not(:disabled){background:#d0d0d0}
button:disabled{color:#aaa;border-color:#ccc;cursor:default}
#brun:not(:disabled){background:var(--red);border-color:var(--red-d);color:#fff}
#brun:not(:disabled):hover{background:var(--red-d)}
#bcont:not(:disabled){border-color:var(--red);color:var(--red-d)}
button.mini{padding:0 4px;font-size:11px;margin-left:6px}
#cfg{border-top:3px solid #bdbdbd}
body[data-state=running] #cfg{border-top-color:#555}
body[data-state=paused] #cfg{border-top-color:var(--red)}
body[data-state=paused] #status{color:var(--red)}
#cfg,#ctl{display:flex;gap:8px;align-items:center;padding:4px 6px;border-bottom:1px solid var(--bd);flex-wrap:wrap}
#cfg label{display:flex;gap:4px;align-items:center;white-space:nowrap}
#status{margin-left:auto;font-weight:bold}
#main{display:grid;grid-template-columns:var(--left) 4px minmax(0,1fr) 4px var(--right);min-height:0}
.panel{background:var(--pn);min-height:0;min-width:0;display:flex;flex-direction:column;overflow:hidden}
.ph{background:#dcdcdc;border-bottom:1px solid var(--bd);padding:2px 6px;font-weight:bold;text-transform:uppercase;font-size:10px;letter-spacing:.06em;flex:none}
.pb{overflow:auto;flex:1;min-height:0}
.split{background:#c4c4c4;cursor:col-resize}.split.h{cursor:row-resize}
.split:hover{background:var(--red-m)}
#center{display:grid;grid-template-rows:auto minmax(0,1fr) 4px var(--cons);min-height:0;min-width:0}
/* tree */
.ti{white-space:nowrap;cursor:pointer;padding:0 4px}.ti:hover{background:#eee}
.ti.dir{font-weight:bold}.ti .tg{display:inline-block;width:12px;color:var(--dim)}
.ti.run{background:var(--sel)}
/* tabs */
#tabs{display:flex;overflow-x:auto;background:#dcdcdc;border-bottom:1px solid var(--bd)}
.tab{padding:2px 8px;border-right:1px solid var(--bd);cursor:pointer;white-space:nowrap;color:#444}
.tab.on{background:#fff;color:#000;font-weight:bold;box-shadow:inset 0 2px var(--red)}
.tab .x{margin-left:6px;color:var(--dim)}.tab .x:hover{color:#000}
/* code */
#code{overflow:auto;background:#fff;min-height:0;position:relative}
.line{display:flex;width:max-content;min-width:100%;white-space:pre;height:17px;line-height:17px}
.gut{flex:none;width:58px;display:flex;align-items:center;justify-content:flex-end;gap:4px;padding-right:6px;color:#999;background:#f4f4f4;border-right:1px solid #ddd;cursor:pointer;user-select:none;position:sticky;left:0;z-index:1}
.gut i{width:10px;height:10px;border-radius:50%;display:inline-block}
.gut:hover i{background:var(--red-m)}
.line.bp .gut i{background:var(--red)}
.src{padding-left:8px}
.line.caller{background:var(--red-xl)}
.line.trail{background:var(--red-xl);box-shadow:inset 3px 0 var(--red-m)}
.line.trail .gut::before{content:'·';color:var(--red);font-weight:bold}
.line.cur{background:var(--red-l);box-shadow:inset 3px 0 var(--red)}
.line.cur.flash{animation:flash .9s ease-out}
@keyframes flash{0%{background:#f6a6aa}100%{background:var(--red-l)}}
.line.cur .gut{color:var(--red-d);font-weight:bold;background:var(--red-l)}
.line.cur .gut b::before{content:'▶ ';color:var(--red);font-size:9px}
.line.exc{background:repeating-linear-gradient(45deg,var(--red-m),var(--red-m) 4px,var(--red-l) 4px,var(--red-l) 8px);box-shadow:inset 4px 0 var(--red-d)}
.line.exc .gut{color:var(--red-d);font-weight:bold}
.k{font-weight:bold;color:#000}.s{color:#666}.c{color:#999;font-style:italic}.n{color:#333;text-decoration:underline dotted #999}
.msg{padding:12px;color:var(--dim)}
/* console */
#cons{display:flex;flex-direction:column;background:#fff;border-top:1px solid var(--bd);min-height:0}
#out{flex:1;overflow:auto;margin:0;padding:4px 6px;white-space:pre-wrap;word-break:break-all;min-height:0}
#out .err{color:var(--red-d);font-style:italic}#out .sys{color:var(--dim)}#out .in{color:#000;font-weight:bold}#out .bad{color:var(--red-d);background:var(--red-l)}
#prompt{display:flex;gap:4px;border-top:1px solid var(--bd);padding:2px 6px;align-items:flex-start;background:#f7f7f7;flex:none}
#in{flex:1;border:0;outline:0;resize:none;background:transparent;font-family:inherit;min-height:17px;max-height:110px;padding:0;overflow:auto}
/* variables */
.vrow{white-space:nowrap;cursor:default;padding:0 4px;display:flex;gap:6px;align-items:baseline}
.vrow.ex{cursor:pointer}.vrow:hover{background:#f0f0f0}
.vrow .tg{width:10px;flex:none;color:var(--dim)}
.vrow .nm{font-weight:bold}.vrow .ty{color:var(--dim);font-size:10px}
.vrow .vl{overflow:hidden;text-overflow:ellipsis;min-width:0}
.vrow.chg .vl{background:var(--red-l);outline:1px solid var(--red-m);color:var(--red-d)}
.vrow.er .vl{color:#666;font-style:italic}.vrow.more{color:var(--dim);cursor:pointer}
.vrow.er .vl{color:var(--red-d)}
.sub{font-weight:bold;color:#555;padding:2px 4px;background:#f3f3f3;border-top:1px solid #e2e2e2;border-bottom:1px solid #e2e2e2;font-size:10px;text-transform:uppercase}
.frm{padding:0 6px;white-space:nowrap;cursor:pointer}.frm:hover{background:#eee}.frm.on{background:var(--red-l);font-weight:bold;box-shadow:inset 3px 0 var(--red)}.frm.lib{color:#999}
.frm .fl{color:var(--dim)}
#rt{display:flex;flex-direction:column;min-height:0}
#rt .panel{flex:none}
#stackp{max-height:150px}#watchp{max-height:140px}#varp{flex:1 !important}
#wadd{display:flex;border-top:1px solid #ddd;flex:none}#wadd input{flex:1;border:0;padding:2px 6px;outline:0}
.wx{color:var(--dim);cursor:pointer;margin-left:auto;padding-left:8px}
/* manual */
.man{padding:6px 22px 18px;line-height:1.55;max-width:860px}
.man h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;border-bottom:2px solid var(--red);padding-bottom:2px;margin:18px 0 6px}
.man h3{font-size:12px;margin:10px 0 2px}
.man p{margin:3px 0}.man ul{margin:3px 0;padding-left:20px}
.man kbd{border:1px solid #999;border-bottom-width:2px;background:#f4f4f4;padding:0 4px;font:inherit;white-space:nowrap}
.man table{border-collapse:collapse;margin:4px 0}.man td,.man th{border:1px solid #ccc;padding:2px 8px;text-align:left;vertical-align:top}
.man th{background:#eee}.man code{background:#f0f0f0;padding:0 3px}
.man .sw{display:inline-block;width:11px;height:11px;border-radius:50%;background:var(--red);vertical-align:-1px}
.man .nt{background:var(--red-xl);border-left:3px solid var(--red);padding:3px 8px;margin:6px 0}
/* modal */
#modal{position:fixed;inset:0;background:rgba(0,0,0,.35);display:none;align-items:center;justify-content:center;z-index:10}
#modal.on{display:flex}
#mbox{background:#fff;border:2px solid #333;border-top:3px solid var(--red);width:min(92vw,1100px);max-height:86vh;display:flex;flex-direction:column}
#mbox .ph{display:flex;gap:8px;align-items:center;text-transform:none;font-size:12px}
#mbox .ph .sp{flex:1}
#mbody{overflow:auto;padding:0;min-height:80px}
table.t{border-collapse:collapse;font-size:12px}
table.t th,table.t td{border:1px solid #d0d0d0;padding:1px 6px;white-space:nowrap;text-align:right}
table.t thead th{position:sticky;top:0;background:#e4e4e4;z-index:1}
table.t th.i{position:sticky;left:0;background:#eee;text-align:left}
table.t .dt{font-weight:normal;color:var(--dim);font-size:10px;display:block}
</style></head><body>
<div id="cfg">
  <label>Folder <input type="text" id="root" size="34"></label><button id="bopen">Open</button><button id="bbrowse">Browse…</button>
  <label>Script <input type="text" id="script" size="26"></label>
  <label>Args <input type="text" id="args" size="16"></label>
  <label>Python <input type="text" id="python" size="22"></label>
  <label><input type="checkbox" id="soe">stop on entry</label>
  <label><input type="checkbox" id="jmc" checked>just my code</label>
</div>
<div id="ctl">
  <button id="brun">Run</button><button id="bcont" title="F8">Continue</button><button id="bnext" title="F10">Step Over</button>
  <button id="bstep" title="F11">Step Into</button><button id="bout" title="Shift+F11">Step Out</button>
  <button id="bstop">Stop</button><button id="brestart">Restart</button>
  <span id="status">idle</span><button id="bhelp" title="F1">? Help</button>
</div>
<div id="main">
  <div class="panel"><div class="ph">Files</div><div class="pb" id="tree"></div></div>
  <div class="split" data-v="--left" data-d="1"></div>
  <div id="center">
    <div id="tabs"></div>
    <div id="code"><div class="msg">Open a folder, click a .py file, set breakpoints in the gutter, press Run.</div></div>
    <div class="split h" data-v="--cons" data-d="-1"></div>
    <div id="cons"><div class="ph">Console / terminal <span style="font-weight:normal;text-transform:none"> — when paused, type Python to run in the selected frame (e.g. <b>flag = True</b>); while running, input goes to the script's stdin</span></div>
      <pre id="out"></pre>
      <div id="prompt"><span>&gt;&gt;&gt;</span><textarea id="in" rows="1" spellcheck="false" autocomplete="off" placeholder="expression or statement (Enter = run, Shift+Enter = newline)"></textarea></div>
    </div>
  </div>
  <div class="split" data-v="--right" data-d="-1"></div>
  <div id="rt">
    <div class="panel" id="stackp"><div class="ph">Call stack</div><div class="pb" id="stack"></div></div>
    <div class="panel" id="varp"><div class="ph">Variables</div><div class="pb" id="vars"></div></div>
    <div class="panel" id="watchp"><div class="ph">Watch</div><div class="pb" id="watch"></div>
      <div id="wadd"><input type="text" id="winp" placeholder="add expression, Enter"></div></div>
  </div>
</div>
<div id="modal"><div id="mbox"><div class="ph"><span id="mtitle"></span><span class="sp"></span><span id="mctl"></span><button id="mclose">Close</button></div><div id="mbody"></div></div></div>
<script>
'use strict';
const TOKEN = new URLSearchParams(location.search).get('t') || '';
const $ = (s, r) => (r || document).querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
async function post(name, body) {
  const r = await fetch('/api/' + name, {method: 'POST', headers: {'X-Token': TOKEN, 'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
  return r.json();
}
async function get(name, params) {
  const u = new URLSearchParams(params || {}); u.set('t', TOKEN);
  return (await fetch('/api/' + name + '?' + u)).json();
}
const S = {cfg: {}, state: 'idle', status: '', files: new Map(), alias: new Map(), tabs: [], active: null, breaks: new Map(),
  stop: null, sel: 0, expanded: new Set(), prevVals: new Map(), curVals: new Map(), pending: new Map(), rid: 1,
  hist: [], hpos: 0, watches: [], lastVars: null, tbl: null};

/* ---------------- syntax highlighting (grayscale classes) ---------------- */
const KW = new Set('False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield self'.split(' '));
const RX = /(#[^\n]*)|("{3}[\s\S]*?"{3}|'{3}[\s\S]*?'{3}|(?:[rRbBuUfF]{0,2})"(?:\\.|[^"\\\n])*"|(?:[rRbBuUfF]{0,2})'(?:\\.|[^'\\\n])*')|(\b\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?\b)|(\b[A-Za-z_]\w*\b)/g;
function highlight(text) {
  const lines = []; let cur = '';
  const emit = (t, cls) => {
    const parts = t.split('\n');
    parts.forEach((p, i) => { if (i) { lines.push(cur); cur = ''; } if (p) cur += cls ? '<span class="' + cls + '">' + esc(p) + '</span>' : esc(p); });
  };
  let last = 0, m; RX.lastIndex = 0;
  while ((m = RX.exec(text))) {
    if (m.index > last) emit(text.slice(last, m.index), '');
    if (m[1]) emit(m[0], 'c'); else if (m[2]) emit(m[0], 's'); else if (m[3]) emit(m[0], 'n');
    else emit(m[0], KW.has(m[0]) ? 'k' : '');
    last = RX.lastIndex;
  }
  if (last < text.length) emit(text.slice(last), '');
  lines.push(cur);
  return lines;
}
const codeLike = l => { const t = l.trim(); return t && !t.startsWith('#'); };

/* ---------------- files & tabs ---------------- */
async function loadFile(path) {
  path = S.alias.get(path) || path;
  if (S.files.has(path)) return S.files.get(path);
  const r = await get('file', {path});
  const key = r.path || path;
  S.alias.set(path, key);
  let f = S.files.get(key);
  if (!f) {
    f = r.error ? {path: key, error: r.error} : {path: key, html: highlight(r.text), raw: r.text.split('\n')};
    S.files.set(key, f);
  }
  return f;
}
async function openFile(path, line) {
  const f = await loadFile(path);
  if (!S.tabs.includes(f.path)) S.tabs.push(f.path);
  S.active = f.path;
  renderTabs(); renderCode(); if (line) scrollTo(line);
  return f;
}
function closeTab(p) {
  const i = S.tabs.indexOf(p); if (i < 0) return;
  S.tabs.splice(i, 1); S.files.delete(p);  // reopening re-reads the file from disk
  if (S.active === p) S.active = S.tabs[Math.min(i, S.tabs.length - 1)] || null;
  renderTabs(); renderCode();
}
const base = p => p.split(/[\\/]/).pop();
function renderTabs() {
  const t = $('#tabs'); t.textContent = '';
  for (const p of S.tabs) {
    const d = el('div', 'tab' + (p === S.active ? ' on' : ''), base(p)); d.title = p;
    d.onclick = () => { S.active = p; renderTabs(); renderCode(); };
    const x = el('span', 'x', '×'); x.onclick = e => { e.stopPropagation(); closeTab(p); }; d.appendChild(x);
    t.appendChild(d);
  }
}
function renderCode() {
  const c = $('#code'); c.textContent = '';
  const f = S.files.get(S.active);
  if (!f) { c.appendChild(el('div', 'msg', 'Open a folder, click a .py file, set breakpoints in the gutter, press Run.')); return; }
  if (f.error) { c.appendChild(el('div', 'msg', f.path + ': ' + f.error)); return; }
  const frag = document.createDocumentFragment();
  f.html.forEach((h, i) => {
    const n = i + 1, row = el('div', 'line'); row.id = 'L' + n; row.dataset.n = n;
    const g = el('span', 'gut'); g.appendChild(el('i')); g.appendChild(el('b', null, String(n)));
    g.onclick = () => toggleBp(f.path, n, f);
    const s = el('span', 'src'); s.innerHTML = h || ' ';
    row.appendChild(g); row.appendChild(s); frag.appendChild(row);
  });
  c.appendChild(frag);
  marks();
}
function marks(flash) {
  const c = $('#code');
  c.querySelectorAll('.cur,.caller,.exc,.bp,.trail,.flash').forEach(e => e.classList.remove('cur', 'caller', 'exc', 'bp', 'trail', 'flash'));
  if (S.stop && S.trail && S.trail.file === S.active) { const t = document.getElementById('L' + S.trail.line); if (t) t.classList.add('trail'); }
  const bs = S.breaks.get(S.active);
  if (bs) bs.forEach(n => { const e = document.getElementById('L' + n); if (e) e.classList.add('bp'); });
  if (S.stop) S.stop.stack.forEach((fr, i) => {
    if (fr.file !== S.active) return;
    const e = document.getElementById('L' + fr.line); if (!e) return;
    if (i === S.sel) { e.classList.remove('trail'); e.classList.add(S.stop.reason === 'exception' && i === S.stop.idx ? 'exc' : 'cur'); if (flash) e.classList.add('flash'); } else e.classList.add('caller');
  });
}
function scrollTo(line) {
  const e = document.getElementById('L' + line), c = $('#code'); if (!e) return;
  const er = e.getBoundingClientRect(), cr = c.getBoundingClientRect();
  if (er.top < cr.top + 20 || er.bottom > cr.bottom - 20) c.scrollTop += (er.top - cr.top) - cr.height / 2;
  c.scrollLeft = 0;
}
function toggleBp(path, n, f) {
  if (!codeLike(f.raw[n - 1] || '')) return;
  let s = S.breaks.get(path); if (!s) S.breaks.set(path, s = new Set());
  s.has(n) ? s.delete(n) : s.add(n);
  marks(); syncBreaks();
}
function syncBreaks() {
  const files = {}; S.breaks.forEach((s, p) => { if (s.size) files[p] = [...s].sort((a, b) => a - b); });
  post('breaks', {files});
}

/* ---------------- file tree & folder browser ---------------- */
function treeNode(entry, depth, onFile, container) {
  const wrap = el('div'), row = el('div', 'ti' + (entry.dir ? ' dir' : ''));
  row.style.paddingLeft = (depth * 12 + 4) + 'px';
  const tg = el('span', 'tg', entry.dir ? '▸' : ''); row.appendChild(tg); row.appendChild(document.createTextNode(entry.name));
  row.title = entry.path; wrap.appendChild(row);
  const kids = el('div'); wrap.appendChild(kids);
  let open = false;
  row.onclick = async () => {
    if (!entry.dir) { onFile(entry, row); return; }
    open = !open; tg.textContent = open ? '▾' : '▸'; kids.textContent = '';
    if (open) { const r = await get('ls', {path: entry.path, files: 1}); (r.entries || []).forEach(e => kids.appendChild(treeNode(e, depth + 1, onFile))); }
  };
  container && container.appendChild(wrap);
  return wrap;
}
async function loadTree() {
  const t = $('#tree'); t.textContent = '';
  const r = await get('ls', {path: S.cfg.root, files: 1});
  if (r.error) { t.appendChild(el('div', 'msg', r.error)); return; }
  (r.entries || []).forEach(e => t.appendChild(treeNode(e, 0, async (en, row) => {
    await openFile(en.path);
    if (/\.py$/i.test(en.path)) { setScript(en.path); }
  })));
}
const rel = p => { const r = S.cfg.root || ''; return r && p.startsWith(r) ? p.slice(r.length).replace(/^[\\/]/, '') : p; };
function setScript(p) { S.cfg.script = rel(p); $('#script').value = S.cfg.script; pushCfg(); }
function showModal(title) { $('#mtitle').textContent = title; $('#mctl').textContent = ''; $('#modal').classList.add('on'); }
$('#mclose').onclick = () => { $('#modal').classList.remove('on'); S.tbl = null; };
function showHelp() { showModal('Help — manual'); const b = $('#mbody'); b.innerHTML = MANUAL; b.scrollTop = 0; }
$('#bhelp').onclick = showHelp;
async function browse(path) {
  showModal('Select folder');
  const body = $('#mbody'); body.textContent = '';
  const r = await get('ls', {path: path || S.cfg.root || ''});
  const top = el('div', 'msg', r.path || '(computer)'); body.appendChild(top);
  const pick = el('button', null, 'Use this folder'); pick.style.margin = '0 12px 8px'; pick.disabled = !r.path;
  pick.onclick = () => { $('#modal').classList.remove('on'); $('#root').value = r.path; applyRoot(); };
  body.appendChild(pick);
  if (r.parent !== null && r.path) { const up = el('div', 'ti dir', '↑ ..'); up.onclick = () => browse(r.parent); body.appendChild(up); }
  (r.entries || []).forEach(e => { const d = el('div', 'ti dir', e.name); d.onclick = () => browse(e.path); body.appendChild(d); });
}
function applyRoot() { S.cfg.root = $('#root').value.trim(); pushCfg(); loadTree(); }


const MANUAL = `<div class="man">
<h2>Quick start</h2>
<ol>
<li>Type a folder path in <b>Folder</b> and press Enter (or <b>Browse…</b>). The file tree appears on the left.</li>
<li>Click a <code>.py</code> file. It opens in the editor and becomes the <b>Script</b> to run.</li>
<li>Click in the gutter (left of a line number) to set a breakpoint <span class="sw"></span>. Click again to remove it.</li>
<li>Press <b>Run</b>. Execution stops at your first breakpoint and the top line turns red: <b>PAUSED</b>.</li>
<li>Step with the toolbar or the keyboard, inspect variables on the right, type Python in the terminal at the bottom.</li>
</ol>

<h2>Toolbar &amp; keyboard</h2>
<table>
<tr><th>Control</th><th>Key</th><th>What it does</th></tr>
<tr><td><b>Run</b></td><td></td><td>Start the script under the debugger. Runs until a breakpoint, an uncaught exception, or the end.</td></tr>
<tr><td><b>Continue</b></td><td><kbd>F8</kbd></td><td>Run until the next breakpoint (or the end).</td></tr>
<tr><td><b>Step Over</b></td><td><kbd>F10</kbd></td><td>Run the current line completely, including any function it calls, and stop at the next line in this function.</td></tr>
<tr><td><b>Step Into</b></td><td><kbd>F11</kbd></td><td>If the current line calls a function, stop on its first line, <i>even if it is defined in another file</i> (that file opens in a new tab). Otherwise acts like Step Over.</td></tr>
<tr><td><b>Step Out</b></td><td><kbd>Shift</kbd>+<kbd>F11</kbd></td><td>Run until the current function returns, then stop in the caller.</td></tr>
<tr><td><b>Stop</b></td><td></td><td>Kill the program. Always works, paused or running.</td></tr>
<tr><td><b>Restart</b></td><td></td><td>Stop and run again with the current settings. Breakpoints and watches are kept.</td></tr>
<tr><td><b>Help</b></td><td><kbd>F1</kbd></td><td>This manual. <kbd>Esc</kbd> closes any pop-up.</td></tr>
</table>
<p>On a Mac laptop the F-keys may need <kbd>fn</kbd>; the buttons always work. Step buttons are only enabled while paused.</p>

<h2>Settings row</h2>
<table>
<tr><td><b>Folder</b></td><td>The project root. It is also the working directory of your script, so relative paths such as <code>data/x.csv</code> resolve from here.</td></tr>
<tr><td><b>Script</b></td><td>File to run (relative to Folder). Set automatically when you click a .py file; you can edit it.</td></tr>
<tr><td><b>Args</b></td><td>Command-line arguments, as you would type them after <code>python script.py</code>. Quotes work.</td></tr>
<tr><td><b>Python</b></td><td>Interpreter used to run the script (e.g. a venv's <code>python.exe</code>). Defaults to the one that started this tool.</td></tr>
<tr><td><b>stop on entry</b></td><td>Pause on the very first line instead of running to a breakpoint.</td></tr>
<tr><td><b>just my code</b></td><td>On: stepping never enters the standard library or installed packages (it steps over them). Off: you can step into any code, e.g. <code>json/__init__.py</code>. Can be toggled while running.</td></tr>
</table>

<h2>Breakpoints</h2>
<ul>
<li>Click the gutter. Blank lines and comment-only lines cannot hold breakpoints.</li>
<li>You can add or remove breakpoints <i>while the program is running</i>; they take effect immediately.</li>
<li>Breakpoints work in any file you open, including files you stepped into. They survive a page reload but are not saved when you stop the tool.</li>
</ul>

<h2>Reading the editor</h2>
<ul>
<li><span class="sw"></span> red dot: a breakpoint.</li>
<li><b>Red-tinted line with ▶ and a red bar</b>: where execution is now (the selected stack frame). It flashes briefly each time you step so you can find it.</li>
<li><b>Small dot + faint red line</b>: the line you just stepped <i>from</i>, so you can see which way you moved.</li>
<li><b>Faint red tint</b>: the line in each caller (other stack frames) that is waiting for the call to return.</li>
<li><b>Red hatched line</b>: where an uncaught exception was raised.</li>
<li>Tabs: every file you open or step into gets a tab; <b>×</b> closes it.</li>
</ul>

<h2>Call stack (top right)</h2>
<p>Innermost call on top. <b>Click any frame</b> to jump the editor to that call site and to show that frame's variables; the terminal and watches then run in that frame too. With <i>just my code</i> on, library frames are hidden.</p>

<h2>Variables</h2>
<ul>
<li><b>Locals</b> (inside a function) and <b>Globals</b> (module level; modules, functions and classes are hidden to reduce noise).</li>
<li>Click a row with ▸ to expand: lists, tuples, dicts, sets, enums, objects (their attributes), numpy arrays, DataFrame columns, Series. Long containers load 100 items at a time ("… more").</li>
<li>Rows stay expanded while you keep stepping.</li>
<li>A value with a <span style="background:var(--red-l);outline:1px solid var(--red-m);color:var(--red-d);padding:0 3px">red tint</span> changed since the previous stop.</li>
<li><b>view</b> button (DataFrame, Series, 1-D/2-D numpy array) opens a paged table with dtypes; use the row/column arrows for big data.</li>
<li>Long values are shortened in the row; print them in the terminal (<code>p name</code>) to see everything.</li>
</ul>

<h2>Watch</h2>
<p>Type any expression (e.g. <code>len(items)</code>, <code>df.shape</code>, <code>total &gt; 100</code>) and press Enter. It is re-evaluated at every stop in the selected frame. Errors are shown in red instead of a value. <b>×</b> removes a watch. Watches must not have side effects.</p>

<h2>Console &amp; terminal (bottom)</h2>
<p>The area shows your program's output (stderr in red italics). The prompt <code>&gt;&gt;&gt;</code> works in two modes:</p>
<ul>
<li><b>Paused:</b> a Python prompt that runs <i>inside the selected frame</i>, with that frame's variables.
<ul>
<li>Inspect: <code>x</code>, <code>df.head()</code>, <code>len(items)</code>. Pdb style also works: <code>p x</code>, <code>pp mydict</code>.</li>
<li><b>Change state:</b> <code>enabled = True</code>, <code>count += 1</code>, <code>items.append(3)</code>. The change is real and the program continues with it; the variables panel updates immediately.</li>
<li>Statements, imports and one-liners such as <code>for i in range(3): print(i)</code> work. <kbd>Shift</kbd>+<kbd>Enter</kbd> adds a new line, <kbd>Enter</kbd> runs, <kbd>↑</kbd>/<kbd>↓</kbd> browse history.</li>
<li>Errors print as a normal Python traceback and never break the debugging session.</li>
<li>Terminal code runs untraced: breakpoints are not hit inside it.</li>
</ul></li>
<li><b>Running:</b> what you type is sent to the program's standard input (for <code>input()</code>).</li>
<li><b>Not running:</b> nothing to talk to; press Run.</li>
</ul>
<div class="nt">Assigning to a <i>new</i> name inside a function frame (not an existing variable) creates it in the terminal's scope only; the running function will not see it. Existing variables, globals, and mutations of lists/dicts/objects always take effect.</div>

<h2>Exceptions</h2>
<p>If the script ends with an uncaught exception, the program pauses at the failing line (red hatching) with the full stack intact, as in a post-mortem debugger. Inspect variables, walk the call stack, evaluate in the terminal. <b>Continue</b> (or Stop) then ends the program with exit code 1. Exceptions that your code catches do not pause.</p>

<h2>The status line</h2>
<p>The thin line at the very top: <b>gray</b> = idle, <b>dark</b> = running, <b>red</b> = paused. The text on the right says why you are paused (<i>breakpoint</i>, <i>step</i>, <i>entry</i>, <i>exception</i>) and where.</p>

<h2>Layout</h2>
<p>Drag the thin bars between panels to resize the file tree, the right-hand column and the console.</p>

<h2>Limits &amp; good to know</h2>
<ul>
<li>Only the <b>main thread</b> is debugged; code in other threads or processes is not stopped by breakpoints.</li>
<li>Debugging is slower than normal execution (about 0.7 µs per Python function call). Code with no breakpoints in a file runs nearly full speed.</li>
<li>The viewer is read-only: edit files in your editor, then press Restart. Closing a tab and clicking the file again re-reads it from disk.</li>
<li>Big objects: only short previews are computed; expand rows to see more, so the tool stays fast on large DataFrames.</li>
<li>The page works only through the URL printed in the terminal (it contains a private token, localhost only). If you see "forbidden", open the exact URL again. Close the tool with <kbd>Ctrl</kbd>+<kbd>C</kbd> in the terminal that started it.</li>
</ul>

<h2>Troubleshooting</h2>
<table>
<tr><td>Nothing happens on Run</td><td>Check the Script field and the console for <code>[script not found]</code>.</td></tr>
<tr><td>Breakpoint never hits</td><td>The line may not execute (e.g. inside an unused branch), or the file differs from the one that actually runs (a copy elsewhere, or an installed package). Step into the call to see which file is used.</td></tr>
<tr><td>Wrong packages / import errors</td><td>Point <b>Python</b> at your project's interpreter.</td></tr>
<tr><td>Step Into doesn't enter a library call</td><td>That is <i>just my code</i>. Untick it to step into library code.</td></tr>
<tr><td>Program waits forever</td><td>It may be waiting for <code>input()</code>: type the answer in the terminal prompt.</td></tr>
</table>
</div>`;

/* ---------------- config / controls ---------------- */
function readCfg() {
  S.cfg.root = $('#root').value.trim(); S.cfg.script = $('#script').value.trim(); S.cfg.args = $('#args').value;
  S.cfg.python = $('#python').value.trim(); S.cfg.stop_on_entry = $('#soe').checked; S.cfg.jmc = $('#jmc').checked;
  return S.cfg;
}
function pushCfg() { post('config', readCfg()); }
function writeCfg() {
  $('#root').value = S.cfg.root || ''; $('#script').value = S.cfg.script || ''; $('#args').value = S.cfg.args || '';
  $('#python').value = S.cfg.python || ''; $('#soe').checked = !!S.cfg.stop_on_entry; $('#jmc').checked = S.cfg.jmc !== false;
}
['script', 'args', 'python'].forEach(id => $('#' + id).addEventListener('change', pushCfg));
['soe', 'jmc'].forEach(id => $('#' + id).addEventListener('change', pushCfg));
$('#root').addEventListener('keydown', e => { if (e.key === 'Enter') applyRoot(); });
$('#bopen').onclick = applyRoot; $('#bbrowse').onclick = () => browse(S.cfg.root);
const run = () => { out('sys', ''); post('run', readCfg()); };
$('#brun').onclick = run; $('#brestart').onclick = run;
$('#bstop').onclick = () => post('stop');
const cmd = n => () => { if (S.state === 'paused') post(n); };
$('#bcont').onclick = cmd('continue'); $('#bnext').onclick = cmd('next'); $('#bstep').onclick = cmd('step'); $('#bout').onclick = cmd('out');
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { $('#mclose').click(); }
  else if (e.key === 'F1') { e.preventDefault(); showHelp(); }
  else if (e.key === 'F8') { e.preventDefault(); cmd('continue')(); }
  else if (e.key === 'F10') { e.preventDefault(); cmd('next')(); }
  else if (e.key === 'F11') { e.preventDefault(); e.shiftKey ? cmd('out')() : cmd('step')(); }
});
function setState(state, status) {
  S.state = state; S.status = status; document.body.dataset.state = state;
  const paused = state === 'paused', running = state === 'running';
  ['bcont', 'bnext', 'bstep', 'bout'].forEach(i => $('#' + i).disabled = !paused);
  $('#bstop').disabled = !(paused || running); $('#brun').disabled = paused || running; $('#brestart').disabled = state === 'idle' && !S.cfg.script;
  let t = state;
  if (paused) { const f = S.stop && S.stop.stack[S.stop.idx]; t = 'PAUSED (' + status + ')' + (f ? ' ' + base(f.file) + ':' + f.line : ''); }
  else if (running) t = 'RUNNING'; else if (status) t = 'idle — ' + status;
  $('#status').textContent = t;
}

/* ---------------- console ---------------- */
const OUT = $('#out');
function out(kind, text) {
  if (!text) return;
  const atEnd = OUT.scrollTop + OUT.clientHeight >= OUT.scrollHeight - 8;
  const s = el('span', kind, text); OUT.appendChild(s);
  while (OUT.childNodes.length > 3000) OUT.removeChild(OUT.firstChild);
  if (atEnd) OUT.scrollTop = OUT.scrollHeight;
}
const INP = $('#in');
function fit() { INP.style.height = 'auto'; INP.style.height = Math.min(110, INP.scrollHeight) + 'px'; }
INP.addEventListener('input', fit);
INP.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  else if (e.key === 'ArrowUp' && !INP.value.includes('\n') && S.hist.length) { e.preventDefault(); S.hpos = Math.max(0, S.hpos - 1); INP.value = S.hist[S.hpos]; }
  else if (e.key === 'ArrowDown' && !INP.value.includes('\n')) { e.preventDefault(); S.hpos = Math.min(S.hist.length, S.hpos + 1); INP.value = S.hist[S.hpos] || ''; }
});
function submit() {
  const src = INP.value; if (!src.trim()) return;
  S.hist.push(src); S.hpos = S.hist.length; INP.value = ''; fit();
  if (S.state === 'paused') {
    out('in', '>>> ' + src.split('\n').join('\n... ') + '\n');
    const id = S.rid++; S.pending.set(id, {type: 'eval'});
    post('eval', {id, src, frame: S.sel});
  } else if (S.state === 'running') post('stdin', {text: src + '\n'});
  else out('sys', '(no active process — press Run, or pause at a breakpoint to evaluate code)\n');
}

/* ---------------- call stack / variables / watch ---------------- */
function renderStack() {
  const c = $('#stack'); c.textContent = '';
  if (!S.stop) return;
  const st = S.stop.stack;
  for (let i = st.length - 1; i >= 0; i--) {
    const fr = st[i]; if (!fr.user && S.cfg.jmc !== false && i !== S.stop.idx) continue;
    const d = el('div', 'frm' + (i === S.sel ? ' on' : '') + (fr.user ? '' : ' lib'), fr.func);
    const l = el('span', 'fl', '  ' + base(fr.file) + ':' + fr.line); d.appendChild(l); d.title = fr.file + ':' + fr.line;
    d.onclick = () => selectFrame(i); c.appendChild(d);
  }
}
async function selectFrame(i) {
  S.sel = i; renderStack(); post('frame', {idx: i});
  const fr = S.stop.stack[i];
  if (fr.exists !== false) { await openFile(fr.file, fr.line); } else { out('sys', '[source not available for ' + fr.file + ']\n'); }
  marks(); scrollTo(fr.line);
}
function valKey(p) { return (S.stop ? S.stop.stack[S.sel].func : '') + '|' + p; }
function nodeRow(n, ppath, depth, host) {
  if (n.more) {
    const r = el('div', 'vrow more', '… more'); r.style.paddingLeft = (depth * 14 + 4) + 'px';
    r.onclick = () => { requestExpand(n.ref, n.offset, host, ppath, depth, r); }; return r;
  }
  const path = ppath + '/' + n.name, wrap = el('div');
  const row = el('div', 'vrow' + (n.ref ? ' ex' : '') + (n.error ? ' er' : '')); row.style.paddingLeft = (depth * 14 + 4) + 'px';
  const tg = el('span', 'tg', n.ref ? '▸' : ''); row.appendChild(tg);
  row.appendChild(el('span', 'nm', n.name));
  if (n.error) row.appendChild(el('span', 'vl', n.error));
  else {
    row.appendChild(el('span', 'ty', n.type));
    const v = el('span', 'vl', n.value); v.title = n.value; row.appendChild(v);
    const k = valKey(path); S.curVals.set(k, n.value);
    if (S.prevVals.has(k) && S.prevVals.get(k) !== n.value) row.classList.add('chg');
  }
  if (n.table) { const b = el('button', 'mini', 'view'); b.onclick = e => { e.stopPropagation(); openTable(n); }; row.appendChild(b); }
  wrap.appendChild(row);
  const kids = el('div'); wrap.appendChild(kids);
  if (n.ref) {
    let open = false;
    const toggle = () => { open = !open; tg.textContent = open ? '▾' : '▸'; kids.textContent = '';
      if (open) { S.expanded.add(path); requestExpand(n.ref, 0, kids, path, depth + 1); } else S.expanded.delete(path); };
    row.onclick = toggle;
    if (S.expanded.has(path)) { open = true; tg.textContent = '▾'; requestExpand(n.ref, 0, kids, path, depth + 1); }
  }
  return wrap;
}
function requestExpand(ref, offset, host, path, depth, moreRow) {
  const id = S.rid++; S.pending.set(id, {type: 'expand', host, path, depth, moreRow});
  post('expand', {id, ref, offset});
}
function section(host, title, nodes, empty) {
  host.appendChild(el('div', 'sub', title));
  if (!nodes.length) { const e = el('div', 'msg', empty); e.style.padding = '2px 8px'; host.appendChild(e); }
  nodes.forEach(n => host.appendChild(nodeRow(n, title, 0, host)));
}
function renderVars(v) {
  S.lastVars = v;
  S.curVals = new Map();
  const host = $('#vars'), top = host.scrollTop; host.textContent = '';
  if (!v) return;
  if (v.scope === 'function') section(host, 'Locals', v.locals, '(none)');
  section(host, 'Globals', v.globals, '(none)');
  host.scrollTop = top;
  const w = $('#watch'); w.textContent = '';
  v.watch.forEach((n, i) => {
    const r = nodeRow(n, 'watch', 0, w); w.appendChild(r);
    const x = el('span', 'wx', '×'); x.onclick = () => { S.watches.splice(i, 1); post('watches', {list: S.watches}); if (!S.stop) renderWatchOnly(); };
    r.firstChild.appendChild(x);
  });
}
function renderWatchOnly() {
  const w = $('#watch'); w.textContent = '';
  S.watches.forEach((e, i) => { const r = el('div', 'vrow', e); const x = el('span', 'wx', '×'); x.onclick = () => { S.watches.splice(i, 1); post('watches', {list: S.watches}); renderWatchOnly(); }; r.appendChild(x); w.appendChild(r); });
}
$('#winp').addEventListener('keydown', e => {
  if (e.key !== 'Enter' || !e.target.value.trim()) return;
  S.watches.push(e.target.value.trim()); e.target.value = ''; post('watches', {list: S.watches}); if (S.state !== 'paused') renderWatchOnly();
});

/* ---------------- table viewer (DataFrame / Series / ndarray) ---------------- */
function openTable(n) {
  S.tbl = {ref: n.ref, name: n.name, r0: 0, c0: 0};
  showModal(n.name + ' — ' + n.type + ' ' + n.value); $('#mbody').textContent = 'loading…'; reqTable();
}
function reqTable() { const id = S.rid++; S.pending.set(id, {type: 'table'}); post('table', {id, ref: S.tbl.ref, r0: S.tbl.r0, c0: S.tbl.c0}); }
function renderTable(d) {
  const body = $('#mbody'), ctl = $('#mctl'); body.textContent = ''; ctl.textContent = '';
  if (!d) { body.appendChild(el('div', 'msg', 'Value is no longer available (the program has moved on).')); return; }
  const [R, C] = d.shape;
  const mk = (txt, fn, dis) => { const b = el('button', 'mini', txt); b.disabled = dis; b.onclick = fn; ctl.appendChild(b); };
  const info = el('span', null, 'rows ' + d.r0 + '–' + (d.r0 + d.rows.length) + ' of ' + R + (C > 1 ? ', cols ' + d.c0 + '–' + (d.c0 + d.cols.length) + ' of ' + C : '') + ' ');
  ctl.appendChild(info);
  mk('◀ rows', () => { S.tbl.r0 = Math.max(0, S.tbl.r0 - 50); reqTable(); }, d.r0 === 0);
  mk('rows ▶', () => { S.tbl.r0 += 50; reqTable(); }, d.r0 + 50 >= R);
  if (C > d.cols.length || d.c0 > 0) {
    mk('◀ cols', () => { S.tbl.c0 = Math.max(0, S.tbl.c0 - 20); reqTable(); }, d.c0 === 0);
    mk('cols ▶', () => { S.tbl.c0 += 20; reqTable(); }, d.c0 + 20 >= C);
  }
  const t = el('table', 't'), thead = el('thead'), hr = el('tr');
  hr.appendChild(el('th', 'i', ''));
  d.cols.forEach((c, j) => { const th = el('th', null, c); th.appendChild(el('span', 'dt', d.dtypes[j] || '')); hr.appendChild(th); });
  thead.appendChild(hr); t.appendChild(thead);
  const tb = el('tbody');
  d.rows.forEach((row, i) => { const tr = el('tr'); tr.appendChild(el('th', 'i', d.idx[i])); row.forEach(v => tr.appendChild(el('td', null, v))); tb.appendChild(tr); });
  t.appendChild(tb); body.appendChild(t);
}

/* ---------------- events from server ---------------- */
async function onStopped(m) {
  S.stop = {reason: m.reason, idx: m.idx, exc: m.exc, stack: m.stack};
  S.trail = m.reason === 'step' ? S.lastPos : null;
  S.sel = m.idx;
  S.prevVals = S.curVals;
  renderStack(); renderVars(m.vars);
  setState('paused', m.reason);
  const fr = m.stack[m.idx];
  if (m.reason === 'exception') out('bad', '[uncaught exception] ' + m.exc + '\n');
  if (fr.exists !== false) await openFile(fr.file, fr.line); else out('sys', '[source not available: ' + fr.file + ']\n');
  marks(true); scrollTo(fr.line); setState('paused', m.reason);
}
function onEvent(m) {
  switch (m.t) {
    case 'snapshot':
      S.cfg = m.cfg; writeCfg(); S.watches = m.watches || [];
      S.breaks = new Map(Object.entries(m.breaks).map(([p, l]) => [p, new Set(l)]));
      OUT.textContent = ''; m.output.forEach(([k, t]) => out(k, t));
      if (!$('#tree').firstChild) loadTree();
      if (m.stop) { S.stop = m.stop; onStopped(Object.assign({vars: m.vars}, m.stop)); } else { S.stop = null; renderStack(); renderVars(null); renderWatchOnly(); marks(); }
      setState(m.state, m.status); break;
    case 'state': if (S.stop && m.state === 'running') { const t = S.stop.stack[S.stop.idx]; S.lastPos = {file: t.file, line: t.line}; } if (m.state === 'idle') S.lastPos = S.trail = null;
      if (m.state !== 'paused') { S.stop = null; renderStack(); marks(); if (m.state === 'idle') { renderVars(null); renderWatchOnly(); } } setState(m.state, m.status); break;
    case 'output': out(m.stream, m.text); break;
    case 'stopped': onStopped(m); break;
    case 'vars': renderVars(m); break;
    case 'evalres': S.pending.delete(m.id); out(m.err ? 'bad' : 'sys', m.out ? m.out + '\n' : ''); break;
    case 'expanded': {
      const p = S.pending.get(m.id); S.pending.delete(m.id); if (!p) break;
      if (p.moreRow) p.moreRow.remove();
      if (m.error) { p.host.appendChild(el('div', 'msg', '(value no longer available)')); break; }
      m.children.forEach(c => p.host.appendChild(nodeRow(c, p.path, p.depth, p.host)));
      break;
    }
    case 'tabled': S.pending.delete(m.id); if (S.tbl) renderTable(m.data); break;
  }
}
new EventSource('/events?t=' + encodeURIComponent(TOKEN)).onmessage = e => onEvent(JSON.parse(e.data));
setState('idle', '');

/* ---------------- splitters ---------------- */
document.querySelectorAll('.split').forEach(s => s.addEventListener('mousedown', e => {
  e.preventDefault();
  const v = s.dataset.v, d = +s.dataset.d, st = s.classList.contains('h') ? e.clientY : e.clientX;
  const root = document.documentElement, start = parseFloat(getComputedStyle(root).getPropertyValue(v));
  const mv = ev => { const cur = s.classList.contains('h') ? ev.clientY : ev.clientX; root.style.setProperty(v, Math.max(80, start + d * (cur - st)) + 'px'); };
  const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); };
  document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
}));
</script></body></html>
"""

if __name__ == "__main__":
    main(sys.argv)
