"""Workspace file tools and bounded, explicitly enabled command execution."""
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import threading

from .registry import Tool, ToolError, ToolRegistry


MAX_BYTES = 1_000_000


def object_schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


STRING = {"type": "string", "maxLength": MAX_BYTES}


class WorkspaceTools:
    def __init__(self, root, allow_execute=False):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("workspace must be a directory")
        self.allow_execute = bool(allow_execute)
        self.registry = ToolRegistry()
        self._lock = threading.RLock()
        entries = [
            ("list_files", "List files within the workspace.", {"path": STRING}, (), self.list_files),
            ("read_file", "Read a bounded UTF-8 file.", {"path": STRING}, ("path",), self.read_file),
            ("search_text", "Search literal text in workspace UTF-8 files.",
             {"query": STRING, "path": STRING}, ("query",), self.search_text),
            ("write_file", "Atomically write UTF-8 text within the workspace.",
             {"path": STRING, "content": STRING}, ("path", "content"), self.write_file),
            ("edit_file", "Replace exactly one matching text span atomically.",
             {"path": STRING, "old_text": STRING, "new_text": STRING},
             ("path", "old_text", "new_text"), self.edit_file),
            ("git_status", "Read Git status; never mutates the repository.", {}, (), self.git_status),
            ("git_diff", "Read working-tree Git diff.", {}, (), self.git_diff),
        ]
        if self.allow_execute:
            entries.append(("run_command", "Execute argv in the workspace (not a sandbox).",
                            {"argv": {"type": "array", "items": STRING, "maxItems": 100},
                             "timeout": {"type": "number", "minimum": 0.1, "maximum": 60}},
                            ("argv",), self.run_command))
        for name, desc, props, required, handler in entries:
            self.registry.register(Tool(name, desc, object_schema(props, required), handler))

    def _path(self, name="."):
        if not isinstance(name, str) or "\x00" in name:
            raise ToolError("invalid path")
        candidate = (self.root / name).resolve()
        try:
            relative = candidate.relative_to(self.root)
        except ValueError:
            raise ToolError("path is outside workspace")
        if any(part in (".git", ".env", "debugger_settings.json") for part in relative.parts):
            raise ToolError("protected workspace path")
        return candidate

    def _files(self, name="."):
        base = self._path(name)
        if base.is_file():
            yield base
            return
        count = 0
        for directory, dirs, names in os.walk(str(base), followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in (".git", ".venv", "__pycache__")
                             and not Path(directory, d).is_symlink())
            for filename in sorted(names):
                try:
                    path = self._path(str(Path(directory, filename)))
                except ToolError:
                    continue
                if path.is_file():
                    yield path
                    count += 1
                    if count >= 2000:
                        return

    def list_files(self, args):
        return {"files": [str(path.relative_to(self.root)) for path in self._files(args.get("path", "."))],
                "limit": 2000}

    def _read(self, path):
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ToolError("path must be a regular file")
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ToolError("file exceeds byte limit")
        try:
            return data.decode("utf-8")
        except UnicodeError:
            raise ToolError("file is not UTF-8")

    def read_file(self, args):
        return {"content": self._read(self._path(args["path"]))}

    def search_text(self, args):
        if not args["query"]:
            raise ToolError("query must not be empty")
        hits = []
        for path in self._files(args.get("path", ".")):
            try:
                text = self._read(path)
            except (ToolError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if args["query"] in line:
                    hits.append({"path": str(path.relative_to(self.root)), "line": number, "text": line[:2000]})
                    if len(hits) >= 200:
                        return {"matches": hits, "truncated": True}
        return {"matches": hits, "truncated": False}

    def _write(self, path, content):
        data = content.encode("utf-8")
        if len(data) > MAX_BYTES:
            raise ToolError("content exceeds byte limit")
        if not path.parent.is_dir():
            raise ToolError("parent directory does not exist")
        mode = path.stat().st_mode & 0o777 if path.exists() else None
        fd, temporary = tempfile.mkstemp(prefix=".agent-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if mode is not None:
                os.chmod(temporary, mode)
            os.replace(temporary, str(path))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def write_file(self, args):
        with self._lock:
            self._write(self._path(args["path"]), args["content"])
        return {"written": True}

    def edit_file(self, args):
        with self._lock:
            path = self._path(args["path"])
            content = self._read(path)
            old = args["old_text"]
            if not old or content.count(old) != 1:
                raise ToolError("old_text must match exactly once")
            self._write(path, content.replace(old, args["new_text"], 1))
        return {"edited": True}

    def _command(self, argv, timeout):
        proc = subprocess.Popen(argv, cwd=str(self.root), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=(os.name == "posix"))
        captured = bytearray()
        limited = threading.Event()

        def kill():
            try:
                if os.name == "posix":
                    os.killpg(proc.pid, signal.SIGKILL)
                elif proc.poll() is None:
                    proc.kill()
            except ProcessLookupError:
                pass

        def drain():
            while True:
                data = proc.stdout.read(4096)
                if not data:
                    return
                available = max(0, 65536 - len(captured))
                captured.extend(data[:available])
                if len(data) > available:
                    limited.set()
                    kill()
                    return

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill()
            proc.wait()
        finally:
            kill()  # Also release inherited pipes held by owned descendants.
            reader.join(timeout=2)
            proc.stdout.close()
        return {"returncode": proc.returncode, "output": bytes(captured).decode("utf-8", "replace"),
                "truncated": limited.is_set(), "timed_out": timed_out}

    def git_status(self, args):
        return self._command(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "status", "--short",
                              "--", ".", ":(glob,exclude)**/.env", ":(glob,exclude)**/debugger_settings.json"], 10)

    def git_diff(self, args):
        return self._command(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "diff",
                              "--no-ext-diff", "--no-textconv", "--", ".",
                              ":(glob,exclude)**/.env", ":(glob,exclude)**/debugger_settings.json"], 10)

    def run_command(self, args):
        if not self.allow_execute:
            raise ToolError("command execution is disabled")
        if not args["argv"] or not args["argv"][0]:
            raise ToolError("argv must not be empty")
        return self._command(args["argv"], args.get("timeout", 30))


def create_workspace_registry(root, allow_execute=False):
    return WorkspaceTools(root, allow_execute).registry
