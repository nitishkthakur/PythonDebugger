"""Bounded synchronous MCP stdio client for explicitly configured local servers."""
import collections
import json
import os
import queue
import signal
import subprocess
import threading
import time

from coding_tools import Tool, ToolError

PROTOCOL = "2025-03-26"
MAX_FRAME = 1_048_576


class MCPError(Exception):
    pass


class MCPClient:
    def __init__(self, argv, cwd=None, timeout=10):
        if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError("argv must be a nonempty string sequence")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 300:
            raise ValueError("timeout must be in (0, 300]")
        self.argv, self.cwd, self.timeout = list(argv), cwd, timeout
        self.proc = None
        self._id = 0
        self._lock = threading.RLock()
        self._incoming = queue.Queue(maxsize=128)
        self._outgoing = queue.Queue(maxsize=128)
        self._threads = []
        self._failure = None
        self._stderr = collections.deque(maxlen=8)
        self.initialized = False

    def _reader(self):
        try:
            while True:
                data = self.proc.stdout.readline(MAX_FRAME + 1)
                if not data:
                    raise MCPError("server closed its output")
                if len(data) > MAX_FRAME or not data.endswith(b"\n"):
                    raise MCPError("server frame exceeds limit or lacks newline")
                message = json.loads(data.decode("utf-8"))
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise MCPError("invalid JSON-RPC envelope")
                self._incoming.put_nowait(message)
        except (OSError, ValueError, queue.Full, MCPError) as exc:
            self._failure = MCPError("MCP read failed: " + str(exc))

    def _writer(self):
        try:
            while True:
                data = self._outgoing.get()
                if data is None:
                    return
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
        except (OSError, ValueError) as exc:
            self._failure = MCPError("MCP write failed (%s)" % type(exc).__name__)

    def _drain_stderr(self):
        try:
            while True:
                data = self.proc.stderr.read(1024)
                if not data:
                    return
                self._stderr.append(data)
        except (OSError, ValueError):
            pass

    def _send(self, message):
        try:
            data = json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
            if len(data) > MAX_FRAME:
                raise MCPError("request exceeds frame limit")
            self._outgoing.put_nowait(data)
        except (ValueError, TypeError, queue.Full) as exc:
            raise MCPError("invalid or excessive outgoing request") from exc

    def _request(self, method, params=None):
        with self._lock:
            if self.proc is None or self.proc.poll() is not None:
                raise MCPError("MCP server is not connected")
            self._id += 1
            request_id = self._id
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                try:
                    response = self._incoming.get(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
                except queue.Empty:
                    if self._failure:
                        raise self._failure
                    continue
                if "method" in response:
                    if "id" in response:
                        self._send({"jsonrpc": "2.0", "id": response["id"],
                                    "error": {"code": -32601, "message": "client method unsupported"}})
                    continue
                if response.get("id") != request_id:
                    raise MCPError("response ID does not match request")
                if "error" in response:
                    raise MCPError("server returned JSON-RPC error")
                if "result" not in response or not isinstance(response["result"], dict):
                    raise MCPError("server returned an invalid result")
                return response["result"]
            try:
                self._send({"jsonrpc": "2.0", "method": "notifications/cancelled",
                            "params": {"requestId": request_id, "reason": "request timeout"}})
            except MCPError:
                pass
            self.close()
            raise MCPError("MCP request timed out")

    def connect(self):
        if self.proc is not None:
            if self.initialized:
                return self
            raise MCPError("client cannot reconnect")
        try:
            self.proc = subprocess.Popen(self.argv, cwd=self.cwd, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         start_new_session=(os.name == "posix"))
            for target in (self._reader, self._writer, self._drain_stderr):
                thread = threading.Thread(target=target, daemon=True)
                self._threads.append(thread)
                thread.start()
            result = self._request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                   "clientInfo": {"name": "local-coding-harness", "version": "1"}})
            if (result.get("protocolVersion") != PROTOCOL
                    or not isinstance(result.get("capabilities"), dict)
                    or not isinstance(result["capabilities"].get("tools"), dict)):
                raise MCPError("unsupported MCP version or missing tools capability")
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            self.initialized = True
            return self
        except Exception:
            self.close()
            raise

    def list_tools(self):
        if not self.initialized:
            raise MCPError("client is not initialized")
        tools, seen, cursor = [], set(), None
        for _ in range(100):
            result = self._request("tools/list", {"cursor": cursor} if cursor else {})
            page = result.get("tools")
            if not isinstance(page, list) or len(tools) + len(page) > 1000:
                raise MCPError("invalid or excessive tool list")
            tools.extend(page)
            cursor = result.get("nextCursor")
            if not cursor:
                return tools
            if not isinstance(cursor, str) or cursor in seen:
                raise MCPError("invalid or repeated pagination cursor")
            seen.add(cursor)
        raise MCPError("tool list exceeded pagination limit")

    def call_tool(self, name, arguments):
        if not self.initialized:
            raise MCPError("client is not initialized")
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise ToolError("MCP tool reported an execution error")
        if not isinstance(result.get("content"), list):
            raise MCPError("invalid MCP tool content")
        return result

    def register_tools(self, registry, namespace="mcp"):
        tools = self.list_tools()
        pending = []
        for item in tools:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("inputSchema"), dict):
                raise MCPError("invalid MCP tool descriptor")
            remote = item["name"]
            name = namespace + "__" + remote

            def invoke(arguments, remote=remote):
                try:
                    return self.call_tool(remote, arguments)
                except MCPError as exc:
                    raise ToolError("MCP transport failed") from exc

            pending.append(Tool(name, item.get("description", "Remote MCP tool"), item["inputSchema"],
                                invoke))
        registry.register_many(pending)
        return [tool.name for tool in pending]

    def close(self):
        self.initialized = False
        proc = self.proc
        if proc is None:
            return
        # Signal EOF through the writer before terminate/kill fallbacks.
        try:
            self._outgoing.put_nowait(None)
        except queue.Full:
            pass
        if proc.poll() is None:
            # Closing stdin from another blocked writer can deadlock; first give
            # the writer a short chance to finish, then terminate the owned child.
            if len(self._threads) > 1:
                self._threads[1].join(timeout=0.1)
            if len(self._threads) <= 1 or not self._threads[1].is_alive():
                proc.stdin.close()
            try:
                proc.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        # A descendant can retain the pipes even when the direct server exited.
        # POSIX sessions let us reclaim all processes we own before closing them.
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for thread in self._threads:
            thread.join(timeout=1)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream and not stream.closed:
                stream.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()
