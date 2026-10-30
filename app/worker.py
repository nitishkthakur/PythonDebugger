"""Debuggee inspection, tracing, and loopback worker protocol."""
from __future__ import annotations

import bdb
import builtins
import collections
import contextlib
import enum
import functools
import inspect
import io
import itertools
import json
import os
import pprint
import queue
import reprlib
import re
import socket
import sys
import sysconfig
import threading
import traceback
import types

HERE = os.path.realpath(os.path.abspath(__file__))
PAGE = 100


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



def _def_loc(o):
    """(file, line) where a class/function/module is defined, or (None, None)."""
    try:
        o = inspect.unwrap(o)
    except Exception:
        pass
    try:
        if isinstance(o, (staticmethod, classmethod)):
            o = o.__func__
        elif isinstance(o, property):
            o = o.fget
        elif isinstance(o, functools.partial):
            o = o.func
        if inspect.ismethod(o):
            o = o.__func__
        if inspect.ismodule(o):
            f = getattr(o, "__file__", None)
            return (f, 1) if f else (None, None)
        if inspect.isclass(o):
            f = inspect.getsourcefile(o)
            return (f, inspect.findsource(o)[1] + 1) if f else (None, None)
        if inspect.isfunction(o):
            fn, line = o.__code__.co_filename, o.__code__.co_firstlineno   # line = first decorator, if any
            if fn.startswith("<frozen"):          # 3.11+ frozen stdlib: map back to the real source file
                real = getattr(sys.modules.get(getattr(o, "__module__", None) or ""), "__file__", None)
                if real:
                    fn = real
            try:
                import linecache
                src = linecache.getlines(fn)
                for i in range(line - 1, min(len(src), line + 30)):
                    if re.match(r"\s*(async\s+def|def)\b", src[i]):
                        line = i + 1
                        break
            except Exception:
                pass
            return fn, line
    except Exception:
        pass
    return None, None


def _loc_dict(o):
    f, ln = _def_loc(o)
    if not f:
        return None
    real = os.path.realpath(f)
    return {"file": real, "line": ln, "exists": os.path.isfile(real)}


def _mro_info(cls, mark=None):
    out = []
    for c in cls.__mro__:
        d = {"name": c.__qualname__, "module": c.__module__, "mark": c is mark}
        d["loc"] = _loc_dict(c)
        out.append(d)
    return out


def describe(expr, frame):
    """Hover info for a dotted name, resolved in `frame` WITHOUT running user code
    (attributes are looked up statically: no properties, no __getattr__)."""
    names = expr.split(".")
    if not all(n.isidentifier() for n in names):
        return None
    loc, glob = frame.f_locals, frame.f_globals
    if names[0] in loc:
        obj = loc[names[0]]
    elif names[0] in glob:
        obj = glob[names[0]]
    elif hasattr(builtins, names[0]):
        obj = getattr(builtins, names[0])
    else:
        return None
    owner = None
    for n in names[1:]:
        owner = obj
        try:
            raw = inspect.getattr_static(owner, n)
        except AttributeError:
            return None
        if isinstance(raw, (staticmethod, classmethod)):
            obj = raw.__func__
        elif type(raw).__name__ == "member_descriptor":  # __slots__ attribute: reading it is side-effect free
            try:
                obj = getattr(owner, n)
            except AttributeError:
                obj = raw
        else:
            obj = raw
    name = names[-1]
    info = {"expr": expr, "name": name}
    in_module = isinstance(owner, types.ModuleType)
    if inspect.isclass(obj):
        kind = "class"
    elif inspect.ismodule(obj):
        kind = "module"
    elif isinstance(obj, property):
        kind = "property"
    elif inspect.isfunction(obj) or inspect.isbuiltin(obj) or inspect.ismethoddescriptor(obj) or inspect.ismethod(obj):
        kind = "method" if (owner is not None and not in_module) else "function"
    else:
        kind = "variable"
    info["kind"] = kind
    if kind in ("class", "function", "method"):
        try:
            info["sig"] = str(inspect.signature(obj))
        except (TypeError, ValueError):
            info["sig"] = None
    if kind in ("class", "function", "method", "module", "property"):
        info["loc"] = _loc_dict(obj)
        try:
            doc = inspect.getdoc(obj)
        except Exception:
            doc = None
        if doc:
            lines = doc.strip().splitlines()
            info["doc"] = _short("\n".join(lines[:10]), 700)
    if kind == "variable":
        info["type"] = type(obj).__qualname__
        info["value"] = _summary(obj)
        info["loc"] = _loc_dict(type(obj))
    # inheritance: for a class its own MRO; for members the owner's MRO with the defining class marked
    if kind == "class":
        info["bases"] = [b.__qualname__ for b in obj.__bases__]
        info["mro"] = _mro_info(obj)
    elif owner is not None and not in_module:
        otype = owner if isinstance(owner, type) else type(owner)
        definer = next((c for c in otype.__mro__ if name in c.__dict__), None)
        info["owner"] = otype.__qualname__
        info["definer"] = definer.__qualname__ if definer else None
        info["mro"] = _mro_info(otype, definer)
    elif kind == "variable":
        info["mro"] = _mro_info(type(obj))
    return info


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
        elif c == "hover":
            try:
                info = describe(m["expr"], self.stack[m["frame"]][0])
            except BaseException:
                info = None
            self.send({"t": "hovered", "id": m["id"], "info": info})
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
                    code = compile(src, "<console>", "eval", dont_inherit=True)
                except SyntaxError:
                    code = None
                    s = src.strip()
                    # pdb-style `p x` / `pp x`
                    for pre, wrap in (("pp ", "__import__('pprint').pprint(%s)"), ("p ", "%s")):
                        if s.startswith(pre):
                            try:
                                code = compile(wrap % s[len(pre):], "<console>", "eval", dont_inherit=True)
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
                    exec(compile(src, "<console>", "exec", dont_inherit=True), g, l)
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
            code = compile(source, script, "exec", dont_inherit=True)   # don't leak this file's __future__ flags into the script
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
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))
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
