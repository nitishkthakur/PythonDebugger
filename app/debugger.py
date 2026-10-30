"""Debugger session lifecycle, authenticated HTTP/SSE, and startup."""
from __future__ import annotations

import hmac
import http.server
import json
import os
import queue
import secrets
import shlex
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

# Direct script and isolated run_path launches need the package parent.
if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "app"

from .settings import DEFAULT_PREFS, SESSION_KEYS, SettingsStore, clean_prefs, parse_env
from .ui import PAGE_HTML
from .worker import worker_main

HERE = os.path.realpath(os.path.abspath(__file__))
MAX_FILE = 5 * 1024 * 1024
MAX_OUTPUT = 1_000_000


def _under(path, root):
    r = os.path.normcase(os.path.realpath(root)).rstrip(os.sep)
    p = os.path.normcase(os.path.realpath(path))
    return p == r or p.startswith(r + os.sep)


class Session:
    """One debugging session: config, the child process, and event fan-out."""

    def __init__(self, root, script, token, store=None):
        self.token = token
        self.store = store
        self.lock = threading.RLock()
        self.cfg = {"root": root, "script": script, "args": "", "python": sys.executable,
                    "stop_on_entry": False, "jmc": True, "env": "", "dotenv": False}
        if store:
            for k, v in store.data["session"].items():
                if k not in ("root", "script") and k in self.cfg:
                    self.cfg[k] = v
        self.state = "idle"
        self.status = ""
        self.breaks = {}
        self.watches = []
        if store:
            self.breaks = {f: set(ls) for f, ls in store.data["breakpoints"].items() if os.path.exists(f) and ls}
            self.watches = list(store.data["watches"])
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

    def persist(self):
        if not self.store:
            return
        d = self.store.data
        d["session"] = {k: self.cfg[k] for k in SESSION_KEYS if k in self.cfg}
        d["breakpoints"] = {f: sorted(ls) for f, ls in self.breaks.items() if ls}
        d["watches"] = list(self.watches)
        self.store.save()

    def prefs(self):
        return self.store.data["prefs"] if self.store else dict(DEFAULT_PREFS)

    def set_prefs(self, body):
        if not self.store:
            return self.prefs()
        reset = bool(body.get("reset"))
        self.store.data["prefs"] = clean_prefs({} if reset else body.get("prefs"),
                                               DEFAULT_PREFS if reset else self.store.data["prefs"])
        self.store.save()
        return self.store.data["prefs"]

    def snapshot(self):
        return {"t": "snapshot", "prefs": self.prefs(),
                "settings_path": self.store.path if self.store else "",
                "settings_error": self.store.error if self.store else "",
                "cfg": self.cfg, "state": self.state, "status": self.status,
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
        self.persist()
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
        env = dict(os.environ)
        base_dir = cfg["root"] if os.path.isdir(cfg["root"]) else os.path.dirname(script)
        if cfg.get("dotenv"):
            try:
                with open(os.path.join(base_dir, ".env"), "r", encoding="utf-8") as fh:
                    env.update(parse_env(fh.read()))
            except OSError:
                pass
        env.update(parse_env(cfg.get("env", ""), expand=True))
        env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
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
        elif t in ("evalres", "expanded", "tabled", "hovered"):
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
        elif name in ("frame", "eval", "expand", "table", "hover"):
            if self.state == "paused":
                self.to_worker(dict(body, c=name))
        elif name == "watches":
            self.watches = list(body.get("list", []))
            self.persist()
            if self.state == "paused":
                self.to_worker({"c": "watches", "list": self.watches})
        elif name == "breaks":
            self.breaks = {f: set(ls) for f, ls in body.get("files", {}).items() if ls}
            self.persist()
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


def _read_file(path, root=""):
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
    try:
        text, utf8 = data.decode("utf-8"), True
    except UnicodeDecodeError:
        text, utf8 = data.decode("utf-8", "replace"), False
    crlf = "\r\n" in text
    readonly = (not utf8) or (not _under(real, root)) or not os.access(real, os.W_OK)
    return {"path": real, "text": text.replace("\r\n", "\n"), "crlf": crlf, "readonly": readonly}


def _save_file(root, body):
    path = os.path.realpath(body.get("path", ""))
    if not os.path.isfile(path):
        return {"error": "file does not exist"}
    if not _under(path, root):
        return {"error": "file is outside the project folder (read-only)"}
    text = body.get("text", "")
    if body.get("crlf"):
        text = text.replace("\n", "\r\n")
    tmp = path + ".dbgtmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(text.encode("utf-8"))
        try:
            shutil.copymode(path, tmp)
        except OSError:
            pass
        os.replace(tmp, path)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return {"error": str(e)}
    return {"ok": True}


class LocalHTTPServer(http.server.ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer.server_bind calls getfqdn(), which may consult DNS even
        # for a loopback address. The debugger never needs a resolved name.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


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
                boot = json.dumps({"prefs": sess.prefs()}).replace("</", "<\\/")
                nonce = secrets.token_urlsafe(18)
                data = PAGE_HTML.replace("__BOOT__", boot).replace("__NONCE__", nonce).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                # The complete UI is embedded. Only same-origin API/SSE connections
                # are allowed; themes cannot load remote fonts, CSS, or images.
                self.send_header("Content-Security-Policy", "default-src 'none'; "
                                 "script-src 'nonce-%s'; style-src 'unsafe-inline'; "
                                 "connect-src 'self'; base-uri 'none'; form-action 'none'; "
                                 "frame-ancestors 'none'; object-src 'none'" % nonce)
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
            elif u.path == "/events":
                self._events()
            elif u.path == "/api/ls":
                self._json(_list_dir(q.get("path", ""), q.get("files") == "1"))
            elif u.path == "/api/file":
                self._json(_read_file(q.get("path", ""), sess.cfg["root"]))
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
            elif name == "prefs":
                return self._json({"prefs": sess.set_prefs(body)})
            elif name == "save":
                return self._json(_save_file(sess.cfg["root"], body))
            else:
                sess.command(name, body)
            self._json({"ok": True})

    return Handler


def serve(root, script, port, open_browser, store=None):
    token = secrets.token_urlsafe(16)
    sess = Session(root, script, token, store)
    handler = make_handler(sess)
    httpd = None
    for p in range(port, port + 50):
        try:
            httpd = LocalHTTPServer(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit("no free port near %d" % port)
    httpd.daemon_threads = True
    url = "http://127.0.0.1:%d/?t=%s" % (httpd.server_address[1], token)
    print("debugger.py serving %s\nSettings file: %s\nOpen: %s\n(Ctrl+C to quit)"
          % (root, store.path if store else "(none)", url), flush=True)
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
    ap.add_argument("folder", nargs="?", default=None, help="project folder (default: last used, else current directory)")
    ap.add_argument("--script", default="", help="script to run (relative to folder)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--settings", default=None, help="settings file (default: distribution root, next to the compatibility launcher)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv[1:])
    store = SettingsStore(a.settings)
    saved = store.data["session"]
    folder = a.folder or (saved.get("root") if os.path.isdir(saved.get("root", "")) else None) or os.getcwd()
    root = os.path.realpath(folder)
    if not os.path.isdir(root):
        sys.exit("not a folder: %s" % folder)
    script = a.script or (saved.get("script", "") if root == os.path.realpath(saved.get("root", "") or "-") else "")
    serve(root, script, a.port, not a.no_browser, store)


if __name__ == "__main__":
    main(sys.argv)
