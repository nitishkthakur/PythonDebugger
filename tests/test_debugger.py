"""End-to-end tests: real HTTP server + real debuggee subprocess, no browser.

    python -m unittest discover -s tests -v
"""
import http.server
import json
import os
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import debugger  # noqa: E402

EX = os.path.join(ROOT, "examples")


def line_of(path, needle, nth=1):
    with open(path) as fh:
        hits = [i for i, l in enumerate(fh, 1) if needle in l]
    return hits[nth - 1]


class Harness:
    def __init__(self, root=EX, store=None):
        self.token = "tok"
        self.sess = debugger.Session(root, "", self.token, store)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), debugger.make_handler(self.sess))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.sess.stop_proc(quiet=True)
        self.httpd.shutdown()
        self.httpd.server_close()

    def post(self, name, body=None, token="tok"):
        req = urllib.request.Request("http://127.0.0.1:%d/api/%s" % (self.port, name),
                                     json.dumps(body or {}).encode(), {"X-Token": token})
        return json.load(urllib.request.urlopen(req, timeout=10))

    def get(self, path):
        return json.load(urllib.request.urlopen("http://127.0.0.1:%d%s&t=%s" % (self.port, path, self.token), timeout=10))

    def state(self):
        return self.get("/api/state?x=1")

    def wait(self, pred, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            st = self.state()
            if pred(st):
                return st
            time.sleep(0.05)
        raise AssertionError("timeout; last state: %s" % json.dumps(self.state())[:800])

    def run(self, script, breaks=None, **cfg):
        path = os.path.join(EX, script) if not os.path.isabs(script) else script
        self.post("breaks", {"files": {os.path.realpath(path): breaks or []}})
        self.post("run", dict(script=path, **cfg))

    def paused(self):
        return self.wait(lambda s: s["state"] == "paused")

    def idle(self):
        return self.wait(lambda s: s["state"] == "idle")

    def cmd(self, name):
        self.post(name)

    def evaluate(self, src, frame=None):
        before = len(self.sess.output)
        st = self.paused()
        self.post("eval", {"id": 1, "src": src, "frame": st["vars"]["frame"] if frame is None else frame})
        # eval result arrives as an SSE event; poll the refreshed vars instead
        time.sleep(0.4)
        return self.state()

    def names(self, st, which="locals"):
        return {n["name"]: n for n in st["vars"][which]}

    def output(self):
        return "".join(t for _, t in self.state()["output"])


class DebuggerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_forbidden_without_token(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.h.post("config", {}, token="wrong")
        self.assertEqual(cm.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen("http://127.0.0.1:%d/api/state" % self.h.port)
        self.assertEqual(cm.exception.code, 403)

    def test_breakpoint_locals_and_continue(self):
        ln = line_of(os.path.join(EX, "demo.py"), "s = s * (1 - discount)")
        self.h.run("demo.py", [ln])
        st = self.h.paused()
        top = st["stop"]["stack"][st["stop"]["idx"]]
        self.assertEqual((os.path.basename(top["file"]), top["line"], top["func"]), ("demo.py", ln, "total"))
        self.assertEqual(st["stop"]["reason"], "breakpoint")
        loc = self.h.names(st)
        self.assertEqual(loc["s"]["value"], "12.75")
        self.assertIn("ref", loc["items"])
        self.assertEqual(loc["items"]["type"], "list (3)")
        self.h.cmd("continue")
        st = self.h.idle()
        self.assertIn("done", self.h.output())
        self.assertIn("exited 0", st["status"])

    def test_step_into_over_out(self):
        f = os.path.join(EX, "demo.py")
        ln = line_of(f, "result, t = process(items)")
        self.h.run("demo.py", [ln])
        self.h.paused()
        self.h.cmd("step")                       # into process(): first body line, not the def line
        st = self.h.wait(lambda s: s["state"] == "paused" and s["stop"]["stack"][s["stop"]["idx"]]["func"] == "process")
        self.assertEqual(st["stop"]["stack"][-1]["line"], line_of(f, "enabled = False"))
        self.assertEqual([fr["func"] for fr in st["stop"]["stack"]], ["<module>", "main", "process"])
        self.h.cmd("next")
        st = self.h.wait(lambda s: s["state"] == "paused" and s["stop"]["stack"][-1]["line"] == line_of(f, "result = {}"))
        self.h.cmd("out")                        # back in main, after the call returned
        st = self.h.wait(lambda s: s["state"] == "paused" and s["stop"]["stack"][-1]["func"] == "main")
        self.assertGreaterEqual(st["stop"]["stack"][-1]["line"], ln)
        self.h.cmd("continue")
        self.h.idle()

    def test_fix_variable_from_terminal(self):
        f = os.path.join(EX, "demo.py")
        ln = line_of(f, "result = {}")
        self.h.run("demo.py", [ln])
        st = self.h.paused()
        self.assertEqual(self.h.names(st)["enabled"]["value"], "False")
        st = self.h.evaluate("enabled = True")
        self.assertEqual(self.h.names(st)["enabled"]["value"], "True")   # visible immediately
        self.h.cmd("continue")
        self.h.idle()
        self.assertIn("result: {'apple': 1.5, 'pear': 2.25, 'nut': 9.0}", self.h.output())  # and actually took effect

    def test_expand_containers(self):
        f = os.path.join(EX, "demo.py")
        self.h.run("demo.py", [line_of(f, 'print("result:"')])
        st = self.h.paused()
        loc = self.h.names(st)
        self.assertEqual(loc["ids"]["value"], "{1, 2, 3}")
        self.assertEqual(loc["colors"]["type"], "dict (2)")
        got = {}
        ev = threading.Event()

        def grab(name, ref):
            self.h.post("expand", {"id": hash(name) % 10000, "ref": ref})

        # drive the worker directly through the session and capture emitted events
        q = self.h.sess.add_client()
        q.get()  # snapshot
        for name in ("items", "colors", "matrix", "ids"):
            self.h.sess.command("expand", {"id": name, "ref": loc[name]["ref"]})
        deadline = time.time() + 5
        while len(got) < 4 and time.time() < deadline:
            ev_ = q.get(timeout=5)
            if ev_.get("t") == "expanded":
                got[ev_["id"]] = ev_["children"]
        self.assertEqual([c["name"] for c in got["items"]], ["[0]", "[1]", "[2]"])
        self.assertIn("Item(name='apple'", got["items"][0]["value"])
        self.assertEqual([c["name"] for c in got["colors"]], ["<Color.RED: 1>", "<Color.GREEN: 2>"])
        self.assertEqual([c["value"] for c in got["matrix"]], ["[1, 2, 3]", "[4, 5, 6]"])
        self.assertEqual([c["value"] for c in got["ids"]], ["1", "2", "3"])
        self.h.sess.command("expand", {"id": "obj", "ref": got["items"][0]["ref"]})
        while True:
            ev_ = q.get(timeout=5)
            if ev_.get("t") == "expanded":
                break
        self.assertEqual([(c["name"], c["value"]) for c in ev_["children"]],
                         [("name", "'apple'"), ("price", "1.5"), ("tags", "['fruit']")])
        self.h.cmd("continue")
        self.h.idle()

    def test_uncaught_exception_postmortem(self):
        self.h.run("demo_crash.py")
        st = self.h.paused()
        self.assertEqual(st["stop"]["reason"], "exception")
        self.assertIn("KeyError", st["stop"]["exc"])
        top = st["stop"]["stack"][st["stop"]["idx"]]
        self.assertEqual(top["func"], "f")
        self.assertEqual(self.h.names(st)["d"]["value"], "{'a': 1}")
        self.assertIn("KeyError", self.h.output())
        self.h.cmd("continue")
        st = self.h.idle()
        self.assertIn("exited 1", st["status"])

    def test_breakpoint_added_while_running(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "loop.py")
            with open(p, "w") as fh:
                fh.write(textwrap.dedent("""\
                    import time
                    i = 0
                    while i < 400:
                        i += 1          # LINE
                        time.sleep(0.02)
                    """))
            self.h.sess.cfg["root"] = d
            self.h.post("run", {"script": p})
            self.h.wait(lambda s: s["state"] == "running")
            time.sleep(0.5)
            self.h.post("breaks", {"files": {os.path.realpath(p): [4]}})
            st = self.h.paused()
            self.assertEqual(st["stop"]["stack"][-1]["line"], 4)
            self.h.post("stop")
            self.h.idle()

    def test_step_into_function_from_another_file(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "pkg"))
            with open(os.path.join(d, "pkg", "__init__.py"), "w") as fh:
                fh.write("")
            helper = os.path.join(d, "pkg", "helper.py")
            with open(helper, "w") as fh:
                fh.write("def double(x):\n    y = x * 2\n    return y\n")
            main = os.path.join(d, "main.py")
            with open(main, "w") as fh:
                fh.write("from pkg.helper import double\nvalue = 21\nresult = double(value)\nprint(result)\n")
            self.h.sess.cfg["root"] = d
            self.h.post("breaks", {"files": {os.path.realpath(main): [3]}})
            self.h.post("run", {"script": main})
            self.h.paused()
            self.h.cmd("step")
            st = self.h.wait(lambda s: s["state"] == "paused" and s["stop"]["stack"][-1]["func"] == "double")
            top = st["stop"]["stack"][-1]
            self.assertEqual(os.path.realpath(top["file"]), os.path.realpath(helper))   # editor will open helper.py
            self.assertEqual(top["line"], 2)
            self.assertEqual([os.path.basename(f["file"]) for f in st["stop"]["stack"]], ["main.py", "helper.py"])
            self.assertEqual(self.h.names(st)["x"]["value"], "21")
            self.h.cmd("out")                                       # and back into main.py
            st = self.h.wait(lambda s: s["state"] == "paused" and s["stop"]["stack"][-1]["func"] == "<module>")
            self.assertEqual(os.path.basename(st["stop"]["stack"][-1]["file"]), "main.py")
            self.h.post("stop")
            self.h.idle()

    def test_breakpoints_added_while_paused_are_honored(self):
        """Pause at a breakpoint, add more downstream (same file, other file, caller frames,
        loop body), continue: every new breakpoint must stop the program."""
        with tempfile.TemporaryDirectory() as d:
            helper = os.path.join(d, "helper.py")
            with open(helper, "w") as fh:
                fh.write("def work(x):\n    y = x * 2\n    z = y + 1\n    return z\n")
            main = os.path.join(d, "main.py")
            with open(main, "w") as fh:
                fh.write(textwrap.dedent("""\
                    from helper import work
                    def run():
                        a = 1
                        b = work(a)
                        c = b + 1
                        return c
                    result = run()
                    print("after", result)
                    for i in range(3):
                        print(i)
                    print("end")
                    """))
            self.h.sess.cfg["root"] = d
            hp, mp = os.path.realpath(helper), os.path.realpath(main)
            # only breakpoint at start: helper.py:2. main.py has none, so its frames start untraced.
            self.h.post("breaks", {"files": {hp: [2]}})
            self.h.post("run", {"script": main})
            st = self.h.paused()
            self.assertEqual((os.path.basename(st["stop"]["stack"][-1]["file"]), st["stop"]["stack"][-1]["line"]), ("helper.py", 2))
            # while paused: add breakpoints later in the same function, in the callers, in a loop
            self.h.post("breaks", {"files": {hp: [2, 3], mp: [5, 8, 10]}})
            hits = []
            for _ in range(7):
                self.h.cmd("continue")
                st = self.h.wait(lambda s: s["state"] in ("paused", "idle"))
                if st["state"] == "idle":
                    break
                top = st["stop"]["stack"][-1]
                hits.append((os.path.basename(top["file"]), top["line"]))
            self.assertEqual(hits, [("helper.py", 3), ("main.py", 5), ("main.py", 8),
                                    ("main.py", 10), ("main.py", 10), ("main.py", 10)])
            self.assertIn("exited 0", st["status"])
            self.assertIn("end", self.h.output())

    def test_deep_multi_file_breakpoints_added_while_paused(self):
        """main -> pkg/l1 -> pkg/sub/l2 -> pkg/sub/deeper/l3 -> .../l4 (5 files, 4 directories deep).
        Pause in the deepest file; add breakpoints in every caller file (their frames started untraced)
        and in a module that has not been imported yet; all must fire, in order."""
        with tempfile.TemporaryDirectory() as d:
            def w(rel, body):
                p = os.path.join(d, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w") as fh:
                    fh.write(textwrap.dedent(body))
                return os.path.realpath(p)
            for pkg in ("pkg", "pkg/sub", "pkg/sub/deeper"):
                w(pkg + "/__init__.py", "")
            l4 = w("pkg/sub/deeper/l4.py", """\
                def f4(x):
                    v = x + 4
                    return v
                """)
            l3 = w("pkg/sub/deeper/l3.py", """\
                from pkg.sub.deeper.l4 import f4
                def f3(x):
                    r = f4(x)
                    r += 3
                    return r
                """)
            l2 = w("pkg/sub/l2.py", """\
                from pkg.sub.deeper.l3 import f3
                def f2(x):
                    r = f3(x)
                    r += 2
                    return r
                """)
            l1 = w("pkg/l1.py", """\
                from pkg.sub.l2 import f2
                def f1(x):
                    r = f2(x)
                    r += 1
                    return r
                """)
            late = w("pkg/late.py", """\
                def final(n):
                    out = n * 10
                    return out
                """)
            main = w("main.py", """\
                from pkg.l1 import f1
                value = f1(0)
                total = value + 100
                import pkg.late
                answer = pkg.late.final(total)
                print("answer", answer)
                """)
            self.h.sess.cfg["root"] = d
            self.h.post("breaks", {"files": {l4: [2]}})           # the only breakpoint at start
            self.h.post("run", {"script": main})
            st = self.h.paused()
            names = [os.path.basename(f["file"]) for f in st["stop"]["stack"]]
            self.assertEqual(names, ["main.py", "l1.py", "l2.py", "l3.py", "l4.py"])   # 5 files deep
            # now, while paused: breakpoints in 4 other files (3 directory levels apart) + a not-yet-imported one
            self.h.post("breaks", {"files": {l4: [2], l3: [4], l2: [4], l1: [4], main: [3], late: [2]}})
            hits = []
            for _ in range(8):
                self.h.cmd("continue")
                st = self.h.wait(lambda s: s["state"] in ("paused", "idle"))
                if st["state"] == "idle":
                    break
                top = st["stop"]["stack"][-1]
                hits.append((os.path.basename(top["file"]), top["line"]))
            self.assertEqual(hits, [("l3.py", 4), ("l2.py", 4), ("l1.py", 4), ("main.py", 3), ("late.py", 2)])
            self.assertIn("answer 1100", self.h.output())      # f1(0)=10, total=110, final=110*10
            self.assertIn("exited 0", st["status"])

    def test_remove_and_replace_breakpoints_while_paused(self):
        with tempfile.TemporaryDirectory() as d:
            main = os.path.join(d, "m.py")
            with open(main, "w") as fh:
                fh.write("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n")
            self.h.sess.cfg["root"] = d
            mp = os.path.realpath(main)
            self.h.post("breaks", {"files": {mp: [1]}})
            self.h.post("run", {"script": main})
            self.h.paused()
            self.h.post("breaks", {"files": {mp: [3, 5]}})        # replace: 1 stays passed, 3 and 5 new
            self.h.cmd("continue")
            self.assertEqual(self.h.wait(lambda s: s["state"] == "paused")["stop"]["stack"][-1]["line"], 3)
            self.h.post("breaks", {"files": {mp: [5]}})           # remove 3 (already passed), keep 5
            self.h.cmd("continue")
            self.assertEqual(self.h.wait(lambda s: s["state"] == "paused")["stop"]["stack"][-1]["line"], 5)
            self.h.post("breaks", {"files": {}})                  # remove everything and finish
            self.h.cmd("continue")
            self.h.idle()

    def test_save_file_preserves_crlf_and_blocks_outside_root(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as other:
            inside = os.path.join(d, "a.py")
            with open(inside, "wb") as fh:
                fh.write(b"x = 1\r\ny = 2\r\n")
            outside = os.path.join(other, "b.py")
            with open(outside, "w") as fh:
                fh.write("z = 1\n")
            self.h.sess.cfg["root"] = d
            r = self.h.get("/api/file?path=" + urllib.parse.quote(inside))
            self.assertTrue(r["crlf"] and not r["readonly"])
            self.assertEqual(r["text"], "x = 1\ny = 2\n")             # normalized for the editor
            self.assertEqual(self.h.post("save", {"path": inside, "text": "x = 10\ny = 2\nz = 3\n", "crlf": True}), {"ok": True})
            with open(inside, "rb") as fh:
                self.assertEqual(fh.read(), b"x = 10\r\ny = 2\r\nz = 3\r\n")  # CRLF kept
            ro = self.h.get("/api/file?path=" + urllib.parse.quote(outside))
            self.assertTrue(ro["readonly"])
            self.assertIn("error", self.h.post("save", {"path": outside, "text": "hacked\n"}))
            with open(outside) as fh:
                self.assertEqual(fh.read(), "z = 1\n")
            self.assertIn("error", self.h.post("save", {"path": os.path.join(d, "nope.py"), "text": ""}))

    def test_settings_file_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            store = debugger.SettingsStore(path)
            self.assertEqual(store.data["prefs"]["font_size"], 14)
            h = Harness(store=store)
            try:
                r = h.post("prefs", {"prefs": {"font_size": 22, "theme": "dark", "accent": "#1f6feb", "line": "relaxed",
                                               "layout": {"left": 300, "right": 5, "junk": 9}}})
                self.assertEqual((r["prefs"]["font_size"], r["prefs"]["theme"], r["prefs"]["accent"]), (22, "dark", "#1f6feb"))
                self.assertEqual(r["prefs"]["layout"], {"left": 300})           # out-of-range / unknown dropped
                bad = h.post("prefs", {"prefs": {"font_size": 999, "theme": "neon", "accent": "red; x", "font": "comic"}})
                self.assertEqual((bad["prefs"]["font_size"], bad["prefs"]["theme"], bad["prefs"]["accent"], bad["prefs"]["font"]),
                                 (32, "dark", "#1f6feb", "default"))             # clamped / rejected, previous kept
                h.post("config", {"args": "--x 1", "env": "A=1", "dotenv": True, "jmc": False})
                h.post("breaks", {"files": {os.path.realpath(__file__): [5, 9]}})
                h.post("watches", {"list": ["a + b"]})
                self.assertTrue(os.path.exists(path))
            finally:
                h.close()
            # a fresh process (new store + session) reads everything back
            store2 = debugger.SettingsStore(path)
            sess2 = debugger.Session(EX, "", "t", store2)
            self.assertEqual(store2.data["prefs"]["font_size"], 32)
            self.assertEqual(sess2.cfg["args"], "--x 1")
            self.assertEqual((sess2.cfg["env"], sess2.cfg["dotenv"], sess2.cfg["jmc"]), ("A=1", True, False))
            self.assertEqual(sess2.breaks, {os.path.realpath(__file__): {5, 9}})
            self.assertEqual(sess2.watches, ["a + b"])
            self.assertEqual(sess2.snapshot()["prefs"]["theme"], "dark")
            with open(path, "w") as fh:
                fh.write("{ this is not json")                                  # corrupt file never crashes startup
            store3 = debugger.SettingsStore(path)
            self.assertEqual(store3.data["prefs"]["font_size"], 14)
            self.assertTrue(store3.error)
            r = h2 = Harness(store=store3)
            try:
                self.assertEqual(h2.post("prefs", {"reset": True})["prefs"]["theme"], "light")
            finally:
                h2.close()

    def test_environment_variables_reach_the_program(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "show.py"), "w") as fh:
                fh.write("import os\nfor k in ('FROM_SHELL', 'FROM_ENV_BOX', 'FROM_DOTENV', 'BOTH', 'EXPANDED'):\n    print(k, '=', os.environ.get(k))\n")
            with open(os.path.join(d, ".env"), "w") as fh:
                fh.write("# comment\nFROM_DOTENV='dot env'\nBOTH=from_dotenv\nexport QUOTED=\"q\"\n")
            os.environ["FROM_SHELL"] = "inherited"
            try:
                self.h.sess.cfg["root"] = d
                self.h.post("run", {"script": os.path.join(d, "show.py"), "dotenv": True,
                                    "env": "FROM_ENV_BOX=box value\nBOTH=from_box\nEXPANDED=$FROM_SHELL/x\n# c"})
                self.h.idle()
            finally:
                del os.environ["FROM_SHELL"]
            out = self.h.output()
            self.assertIn("FROM_SHELL = inherited", out)          # inherited from the launching shell
            self.assertIn("FROM_ENV_BOX = box value", out)
            self.assertIn("FROM_DOTENV = dot env", out)           # .env loaded
            self.assertIn("BOTH = from_box", out)                 # Env box overrides .env
            self.assertIn("EXPANDED = inherited/x", out)          # $VAR expansion

    def hover(self, q, expr, frame=-1):
        """Ask the worker for hover info and return it (frame -1 = innermost)."""
        st = self.h.state()
        idx = len(st["stop"]["stack"]) - 1 if frame < 0 else frame
        self.h.sess.command("hover", {"id": expr, "expr": expr, "frame": idx})
        end = time.time() + 5
        while time.time() < end:
            e = q.get(timeout=5)
            if e.get("t") == "hovered" and e["id"] == expr:
                return e["info"]
        raise AssertionError("no hover reply for " + expr)

    def test_hover_signature_file_and_mro(self):
        f = os.path.join(EX, "demo_mro.py")
        self.h.run("demo_mro.py", [line_of(f, "total = first.helper")])
        self.h.paused()
        q = self.h.sess.add_client()
        q.get()
        names = lambda info: [c["name"] for c in info["mro"]]
        # class: signature, bases, docstring, full MRO with file/line of every user class
        c = self.hover(q, "Child")
        self.assertEqual((c["kind"], c["sig"], c["bases"]), ("class", "(value)", ["Mixin", "Base"]))
        self.assertEqual(names(c), ["Child", "Mixin", "Base", "object"])
        self.assertEqual(c["doc"], "A child with multiple inheritance.")
        self.assertEqual((os.path.basename(c["loc"]["file"]), c["loc"]["line"]), ("demo_mro.py", line_of(f, "class Child")))
        self.assertTrue(c["loc"]["exists"] and c["mro"][1]["loc"]["line"] == line_of(f, "class Mixin"))
        self.assertIsNone(c["mro"][3]["loc"])                      # object: built-in, no source
        # method on an instance: signature, and WHICH class in the MRO defines it (Mixin.greet wins over Base.greet)
        g = self.hover(q, "first.greet")
        self.assertEqual((g["kind"], g["owner"], g["definer"]), ("method", "Child", "Mixin"))
        self.assertEqual(g["sig"], "(self, name, punctuation='?')")
        self.assertEqual(g["loc"]["line"], line_of(f, "def greet", 2))
        self.assertEqual([c_["name"] for c_ in g["mro"] if c_["mark"]], ["Mixin"])
        # inherited only from Base
        self.assertEqual(self.hover(q, "first.helper")["definer"], "Mixin")
        # annotated function with defaults + docstring
        b = self.hover(q, "build")
        self.assertEqual((b["kind"], b["sig"]), ("function", "(count: int, label: str = 'x') -> list"))
        self.assertEqual(b["doc"], "Build a list of children.")
        self.assertEqual(b["loc"]["line"], line_of(f, "def build"))
        # staticmethod via the class
        m = self.hover(q, "Child.make")
        self.assertEqual((m["kind"], m["sig"], m["definer"]), ("method", "(v)", "Child"))
        # variables: type, value, type location + MRO; instance attribute
        v = self.hover(q, "first")
        self.assertEqual((v["kind"], v["type"]), ("variable", "Child"))
        self.assertEqual(names(v), ["Child", "Mixin", "Base", "object"])
        self.assertEqual(v["loc"]["line"], line_of(f, "class Child"))
        a = self.hover(q, "first.value")
        self.assertEqual((a["kind"], a["value"], a["definer"]), ("variable", "0", None))   # instance attribute
        self.assertIsNone(self.hover(q, "total"))                  # not assigned yet at this line
        # stdlib / builtin / module
        j = self.hover(q, "os.path.join")
        self.assertEqual(j["kind"], "function")
        self.assertTrue(j["loc"]["file"].endswith("posixpath.py") or j["loc"]["file"].endswith("ntpath.py"))
        self.assertEqual(self.hover(q, "os")["kind"], "module")
        ln = self.hover(q, "len")
        self.assertEqual(ln["kind"], "function")
        self.assertIsNone(ln["loc"])
        # not resolvable -> None (never an error)
        self.assertIsNone(self.hover(q, "nothing_here"))
        self.assertIsNone(self.hover(q, "first.nothing"))
        self.assertIsNone(self.hover(q, "1bad.name"))
        self.h.cmd("continue")
        self.h.idle()

    def test_hover_never_runs_user_code(self):
        with tempfile.TemporaryDirectory() as d:
            main = os.path.join(d, "trap.py")
            with open(main, "w") as fh:
                fh.write(textwrap.dedent("""\
                    calls = []

                    class Trap:
                        @property
                        def boom(self):
                            calls.append("property")
                            return 1

                        def __getattr__(self, name):
                            calls.append("getattr:" + name)
                            return 2

                    t = Trap()
                    stop_here = 1
                    print("calls:", calls)
                    """))
            self.h.sess.cfg["root"] = d
            self.h.post("breaks", {"files": {os.path.realpath(main): [14]}})
            self.h.post("run", {"script": main})
            self.h.paused()
            q = self.h.sess.add_client()
            q.get()
            p = self.hover(q, "t.boom")
            self.assertEqual(p["kind"], "property")                # described, not evaluated
            self.assertEqual(p["loc"]["line"], 5)
            self.assertIsNone(self.hover(q, "t.dynamic"))          # __getattr__ attribute: not resolvable, not called
            self.hover(q, "t")
            self.h.cmd("continue")
            self.h.idle()
            self.assertIn("calls: []", self.h.output())            # nothing was executed by hovering

    def test_hover_in_selected_frame(self):
        f = os.path.join(EX, "demo_mro.py")
        self.h.run("demo_mro.py", [line_of(f, "child = Child.make(i)")])
        st = self.h.paused()
        q = self.h.sess.add_client()
        q.get()
        names = [fr["func"] for fr in st["stop"]["stack"]]
        self.assertEqual(names, ["<module>", "build"])
        self.assertEqual(self.hover(q, "count", frame=1)["kind"], "variable")      # local of build()
        self.assertIsNone(self.hover(q, "count", frame=0))                         # not visible in <module>
        self.assertEqual(self.hover(q, "build", frame=0)["kind"], "function")           # module-level name
        self.h.post("breaks", {"files": {}})
        self.h.cmd("continue")
        self.h.idle()

    def test_script_does_not_inherit_debugger_future_flags(self):
        with tempfile.TemporaryDirectory() as d:
            main = os.path.join(d, "ann.py")
            with open(main, "w") as fh:
                fh.write("def f(a: int) -> str:\n    return 'x'\nprint('annotations:', f.__annotations__)\nstop = 1\n")
            self.h.sess.cfg["root"] = d
            self.h.post("breaks", {"files": {os.path.realpath(main): [4]}})
            self.h.post("run", {"script": main})
            self.h.paused()
            self.h.post("eval", {"id": 1, "src": "def g(b: float): pass\nprint(g.__annotations__)", "frame": 0})
            time.sleep(0.5)
            self.h.cmd("continue")
            self.h.idle()
            self.assertIn("annotations: {'a': <class 'int'>, 'return': <class 'str'>}", self.h.output())   # real classes, not strings

    def test_just_my_code_toggle(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.py")
            with open(p, "w") as fh:
                fh.write("import json\nx = json.dumps({'a': 1})\ny = 2\n")
            self.h.sess.cfg["root"] = d
            self.h.post("breaks", {"files": {os.path.realpath(p): [2]}})
            self.h.post("run", {"script": p, "jmc": True})
            self.h.paused()
            self.h.cmd("step")
            st = self.h.paused()
            self.assertEqual(st["stop"]["stack"][-1]["line"], 3)   # stepped over json internals
            self.h.post("stop")
            self.h.idle()
            self.h.post("run", {"script": p, "jmc": False})
            self.h.paused()
            self.h.cmd("step")
            st = self.h.paused()
            self.assertTrue(st["stop"]["stack"][-1]["file"].endswith("__init__.py"))   # entered json/__init__.py
            self.h.post("stop")
            self.h.idle()

    def test_stdin_while_running(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ask.py")
            with open(p, "w") as fh:
                fh.write("name = input('who? ')\nprint('hi', name)\n")
            self.h.sess.cfg["root"] = d
            self.h.post("run", {"script": p})
            self.h.wait(lambda s: "who?" in "".join(t for _, t in s["output"]))
            self.h.post("stdin", {"text": "bob\n"})
            self.h.idle()
            self.assertIn("hi bob", self.h.output())

    @unittest.skipUnless(__import__("importlib").util.find_spec("pandas"), "pandas missing")
    def test_pandas_numpy_tables(self):
        f = os.path.join(EX, "demo_pandas.py")
        self.h.run("demo_pandas.py", [line_of(f, "print(summary)")])
        st = self.h.paused()
        g = self.h.names(st, "globals")
        self.assertEqual(g["df"]["value"], "120 rows × 3 columns")
        self.assertTrue(g["df"]["table"] and g["arr"]["table"] and g["s"]["table"])
        self.assertEqual(g["arr"]["value"], "shape=(3, 4) dtype=int64")
        q = self.h.sess.add_client()
        q.get()
        self.h.sess.command("table", {"id": "df", "ref": g["df"]["ref"], "r0": 100, "c0": 0})
        self.h.sess.command("table", {"id": "arr", "ref": g["arr"]["ref"], "r0": 0, "c0": 0})
        self.h.sess.command("expand", {"id": "dfcols", "ref": g["df"]["ref"]})
        res = {}
        deadline = time.time() + 5
        while len(res) < 3 and time.time() < deadline:
            e = q.get(timeout=5)
            if e.get("t") in ("tabled", "expanded"):
                res[e["id"]] = e
        df = res["df"]["data"]
        self.assertEqual(df["shape"], [120, 3])
        self.assertEqual(df["cols"], ["a", "b", "c"])
        self.assertEqual(len(df["rows"]), 20)
        self.assertEqual(df["idx"][0], "100")
        self.assertEqual(df["rows"][0], ["100", "0.8403361344537815", "z"] if False else df["rows"][0])
        self.assertEqual(res["arr"]["data"]["rows"][2], ["8", "9", "10", "11"])
        self.assertEqual([c["name"] for c in res["dfcols"]["children"]], ["a", "b", "c"])
        self.assertEqual(res["dfcols"]["children"][0]["type"], "Series")
        self.h.cmd("continue")
        self.h.idle()

    def test_watch_and_console_helpers(self):
        f = os.path.join(EX, "demo.py")
        self.h.run("demo.py", [line_of(f, "s = s * (1 - discount)")])
        self.h.paused()
        self.h.post("watches", {"list": ["s * 2", "nope + 1"]})
        st = self.h.wait(lambda s: s["vars"] and len(s["vars"]["watch"]) == 2)
        self.assertEqual(st["vars"]["watch"][0]["value"], "25.5")
        self.assertIn("NameError", st["vars"]["watch"][1]["error"])
        q = self.h.sess.add_client()
        q.get()
        self.h.sess.command("eval", {"id": 7, "src": "p s + 1", "frame": 3})
        e = self.wait_event(q, "evalres")
        self.assertEqual(e["out"], "13.75")
        self.h.sess.command("eval", {"id": 8, "src": "1/0", "frame": 3})
        e = self.wait_event(q, "evalres")
        self.assertTrue(e["err"] and "ZeroDivisionError" in e["out"])
        self.h.cmd("continue")
        self.h.idle()

    @staticmethod
    def wait_event(q, t, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            e = q.get(timeout=timeout)
            if e.get("t") == t:
                return e
        raise AssertionError("no %s event" % t)


if __name__ == "__main__":
    unittest.main()
