"""Real stdio subprocess and protocol failure-path tests."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from coding_tools import ToolError, ToolRegistry, create_workspace_registry
from mcp_local import MCPClient, MCPError
from mcp_local.client import PROTOCOL
from mcp_local.server import serve

ROOT = str(Path(__file__).resolve().parent.parent)


class MCPTests(unittest.TestCase):
    def test_real_server_discovery_calls_registration_errors_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [sys.executable, "-m", "mcp_local.server", "--root", directory]
            with MCPClient(argv, cwd=ROOT) as client:
                names = [tool["name"] for tool in client.list_tools()]
                self.assertIn("read_file", names)
                self.assertNotIn("run_command", names)
                registry = ToolRegistry()
                self.assertIn("files__write_file", client.register_tools(registry, "files"))
                registry.call("files__write_file", {"path": "test.txt", "content": "hello"})
                result = registry.call("files__read_file", {"path": "test.txt"})
                self.assertEqual(json.loads(result["content"][0]["text"])["content"], "hello")
                with self.assertRaises(ToolError):
                    registry.call("files__read_file", {"path": "../secret"})
                count = len(registry.schemas())
                with self.assertRaises(ValueError):
                    client.register_tools(registry, "files")
                self.assertEqual(len(registry.schemas()), count)
                proc = client.proc
            self.assertIsNotNone(proc.poll())
            with self.assertRaises(ToolError):
                registry.call("files__list_files", {})
            client.close()
            with self.assertRaises(MCPError):
                client.list_tools()

    def test_protocol_errors_lifecycle_and_notifications(self):
        with tempfile.TemporaryDirectory() as directory:
            messages = [b"{bad\n", b"[]\n",
                        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                        {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {
                            "protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
                        {"jsonrpc": "2.0", "method": "notifications/initialized"},
                        {"jsonrpc": "2.0", "id": 3, "method": "ping"},
                        {"jsonrpc": "2.0", "id": 4, "method": "unsupported"},
                        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "missing"}}]
            source = io.BytesIO(b"".join(item if isinstance(item, bytes) else json.dumps(item).encode() + b"\n" for item in messages))
            sink = io.BytesIO()
            serve(create_workspace_registry(directory), source, sink)
            responses = [json.loads(line) for line in sink.getvalue().splitlines()]
            self.assertEqual([item["error"]["code"] for item in responses[:3]], [-32700, -32600, -32602])
            self.assertEqual(responses[3]["result"]["protocolVersion"], PROTOCOL)
            self.assertEqual(responses[4]["result"], {})
            self.assertEqual(responses[5]["error"]["code"], -32601)
            self.assertEqual(responses[6]["error"]["code"], -32602)

    def test_invalid_startup_version_malformed_output_eof_and_oversize(self):
        scripts = ["print('bad', flush=True)", "pass", "print('x'*1100000,flush=True)",
                   "import sys,json; m=json.loads(sys.stdin.readline()); print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':{'protocolVersion':'wrong','capabilities':{'tools':{}}}}),flush=True)"]
        for script in scripts:
            with self.subTest(script=script[:30]):
                client = MCPClient([sys.executable, "-u", "-c", script], timeout=1)
                with self.assertRaises(MCPError):
                    client.connect()
                self.assertIsNotNone(client.proc.poll())

    def test_timeout_kills_owned_child(self):
        client = MCPClient([sys.executable, "-u", "-c", "import time; time.sleep(30)"], timeout=0.1)
        with self.assertRaises(MCPError):
            client.connect()
        self.assertIsNotNone(client.proc.poll())

    @unittest.skipUnless(sys.platform != "win32", "POSIX process-group ownership")
    def test_close_reclaims_descendant_holding_stdio(self):
        script = "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])"
        client = MCPClient([sys.executable, "-u", "-c", script], timeout=0.2)
        started = time.monotonic()
        with self.assertRaises(MCPError):
            client.connect()
        self.assertLess(time.monotonic() - started, 4)
        self.assertFalse(any(thread.is_alive() for thread in client._threads))

    def test_pagination_and_server_stderr_cannot_block_discovery(self):
        script = """import sys,json
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 if m['method']=='initialize':
  sys.stderr.write('x'*100000); sys.stderr.flush()
  result={'protocolVersion':'2025-03-26','capabilities':{'tools':{}}}
 else:
  cursor=m.get('params',{}).get('cursor')
  result={'tools':[{'name':'second' if cursor else 'first','inputSchema':{'type':'object','properties':{}}}]}
  if not cursor: result['nextCursor']='page2'
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':result}),flush=True)
"""
        with MCPClient([sys.executable, "-u", "-c", script]) as client:
            self.assertEqual([tool["name"] for tool in client.list_tools()], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
