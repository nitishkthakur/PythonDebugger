"""MCP 2025-03-26 workspace-tools server over newline-delimited stdio."""
import argparse
import json
import sys

from coding_tools import ToolError, create_workspace_registry
from .client import MAX_FRAME, PROTOCOL


def serve(registry, input_stream=None, output_stream=None):
    source = input_stream or sys.stdin.buffer
    sink = output_stream or sys.stdout.buffer
    initialized = notified = False

    def send(message):
        data = json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
        if len(data) > MAX_FRAME:
            data = json.dumps({"jsonrpc": "2.0", "id": message.get("id"),
                               "error": {"code": -32603, "message": "response exceeds limit"}}).encode() + b"\n"
        sink.write(data)
        sink.flush()

    while True:
        line = source.readline(MAX_FRAME + 1)
        if not line:
            return
        if len(line) > MAX_FRAME or not line.endswith(b"\n"):
            return
        request_id = None
        try:
            try:
                message = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeError):
                send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "invalid JSON"}})
                continue
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
                send({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}})
                continue
            request_id = message.get("id")
            method, params = message["method"], message.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            if method == "notifications/initialized" and initialized:
                notified = True
                continue
            if "id" not in message:
                continue
            if method == "initialize":
                if initialized:
                    raise ValueError("already initialized")
                info = params.get("clientInfo")
                if (not isinstance(params.get("protocolVersion"), str)
                        or not isinstance(params.get("capabilities"), dict)
                        or not isinstance(info, dict)
                        or not isinstance(info.get("name"), str)
                        or not isinstance(info.get("version"), str)):
                    raise ValueError("invalid initialize parameters")
                initialized = True
                result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "workspace-coding-tools", "version": "1"}}
            elif method == "ping":
                result = {}
            elif not notified:
                raise ValueError("initialize and initialized required")
            elif method == "tools/list":
                if params.get("cursor"):
                    raise ValueError("invalid cursor")
                result = {"tools": [{"name": x["function"]["name"], "description": x["function"]["description"],
                                     "inputSchema": x["function"]["parameters"]} for x in registry.schemas()]}
            elif method == "tools/call":
                if (not isinstance(params.get("name"), str)
                        or not isinstance(params.get("arguments", {}), dict)
                        or params["name"] not in {item["function"]["name"] for item in registry.schemas()}):
                    raise ValueError("unknown tool or invalid arguments")
                try:
                    value = registry.call(params.get("name"), params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
                except ToolError as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            else:
                send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method not found"}})
                continue
            send({"jsonrpc": "2.0", "id": request_id, "result": result})
        except (ValueError, TypeError, KeyError):
            send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "invalid parameters or lifecycle"}})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local workspace MCP stdio server")
    parser.add_argument("--root", required=True)
    parser.add_argument("--allow-execute", action="store_true")
    args = parser.parse_args(argv)
    serve(create_workspace_registry(args.root, args.allow_execute))


if __name__ == "__main__":
    main()
