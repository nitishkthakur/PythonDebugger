"""Explicit numeric-loopback HTTP, bounded bodies/SSE, and owned connections."""
import contextlib
import http.client
import ipaddress
import json
import math
import socket
import threading
import time
from urllib.parse import urlsplit

from .errors import (LLMClosedError, LLMConnectionError, LLMHTTPError, LLMProtocolError,
                     LLMTimeoutError, LLMValidationError)


class LocalHTTPTransport:
    def __init__(self, endpoint, timeout=60, max_bytes=4 * 1024 * 1024):
        try:
            url = urlsplit(endpoint)
            address = ipaddress.ip_address(url.hostname)
            if url.scheme != "http" or not address.is_loopback or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
                raise ValueError()
            self.host, self.port = str(address), url.port or 80
        except (ValueError, TypeError, AttributeError):
            raise LLMValidationError("Endpoint must be numeric loopback HTTP with no path or credentials") from None
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise LLMValidationError("timeout must be positive and finite")
        if type(max_bytes) is not int or max_bytes <= 0:
            raise LLMValidationError("max_bytes must be positive")
        self.timeout, self.max_bytes = timeout, max_bytes
        self._connections = set()
        self._sockets = {}
        self._lock = threading.Lock()
        self._closed = False

    @contextlib.contextmanager
    def response(self, method, path, body=None, accept="application/json"):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        deadline = time.monotonic() + self.timeout
        active_socket = []
        response = None
        def expire():
            # HTTP/1.0 responses can detach the socket from HTTPConnection.
            # Keep the actual socket so the total deadline also interrupts
            # slow-drip status lines, headers, and bodies.
            sock = active_socket[0] if active_socket else connection.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()
        timer = threading.Timer(self.timeout, expire)
        timer.daemon = True
        with self._lock:
            if self._closed:
                raise LLMClosedError("Transport is closed")
            self._connections.add(connection)
        try:
            data = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
            if data is not None and len(data) > self.max_bytes:
                raise LLMValidationError("Inference request exceeds limit")
            timer.start()
            connection.connect()
            if connection.sock is None:
                raise LLMTimeoutError("Inference request deadline exceeded")
            active_socket.append(connection.sock)
            with self._lock:
                if self._closed:
                    raise LLMClosedError("Transport is closed")
                self._sockets[connection] = connection.sock
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LLMTimeoutError("Inference request deadline exceeded")
            connection.sock.settimeout(remaining)
            connection.request(method, path, data, {"Content-Type": "application/json", "Accept": accept})
            response = connection.getresponse()
            if time.monotonic() >= deadline:
                raise LLMTimeoutError("Inference request deadline exceeded")
            if response.status != 200:
                raise LLMHTTPError(response.status)
            yield connection, response, deadline
        except socket.timeout:
            raise LLMTimeoutError("Inference request timed out") from None
        except (OSError, http.client.HTTPException):
            if time.monotonic() >= deadline:
                raise LLMTimeoutError("Inference request deadline exceeded") from None
            raise LLMConnectionError("Inference server connection failed") from None
        finally:
            timer.cancel()
            if response is not None:
                response.close()
            connection.close()
            with self._lock:
                self._connections.discard(connection)
                self._sockets.pop(connection, None)

    def chunks(self, connection, response, deadline):
        size = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LLMTimeoutError("Inference request deadline exceeded")
            if connection.sock:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(65536, self.max_bytes + 1 - size))
            if time.monotonic() >= deadline:
                raise LLMTimeoutError("Inference request deadline exceeded")
            if not chunk:
                return
            size += len(chunk)
            if size > self.max_bytes:
                raise LLMProtocolError("Inference response exceeds limit")
            yield chunk

    def json(self, method, path, body=None):
        with self.response(method, path, body) as (connection, response, deadline):
            if "application/json" not in response.getheader("Content-Type", "").lower():
                raise LLMProtocolError("Expected JSON response")
            data = b"".join(self.chunks(connection, response, deadline))
        try:
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, UnicodeError):
            raise LLMProtocolError("Invalid JSON response") from None

    def events(self, path, body):
        with self.response("POST", path, body, "text/event-stream") as (connection, response, deadline):
            if "text/event-stream" not in response.getheader("Content-Type", "").lower():
                raise LLMProtocolError("Expected SSE response")
            pending = b""
            data = []
            for chunk in self.chunks(connection, response, deadline):
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    line = line.rstrip(b"\r")
                    if not line:
                        if data:
                            try:
                                yield b"\n".join(data).decode("utf-8")
                            except UnicodeError:
                                raise LLMProtocolError("Invalid SSE encoding") from None
                            data = []
                    elif line.startswith(b"data:"):
                        data.append(line[5:].lstrip(b" "))
            if pending or data:
                raise LLMProtocolError("Truncated SSE event")

    def close(self):
        with self._lock:
            self._closed = True
            connections = list(self._connections)
            sockets = list(self._sockets.values())
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for connection in connections:
            connection.close()
