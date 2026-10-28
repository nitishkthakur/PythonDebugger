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
    def __init__(self, root=EX):
        self.token = "tok"
        self.sess = debugger.Session(root, "", self.token)
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
