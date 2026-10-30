"""Provider-independent registry and workspace regressions."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from coding_tools import Tool, ToolError, ToolRegistry, WorkspaceTools


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tools = WorkspaceTools(self.root)
        self.call = self.tools.registry.call

    def test_registry_validates_schema_and_rejects_duplicate_unknown_tools(self):
        registry = ToolRegistry()
        schema = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1}},
                  "required": ["n"], "additionalProperties": False}
        tool = Tool("count", "Count", schema, lambda args: args["n"])
        registry.register(tool)
        self.assertEqual(registry.call("count", {"n": 2}), 2)
        for arguments in ({}, {"n": True}, {"n": 0}, {"n": 1, "extra": 2}, []):
            with self.subTest(arguments=arguments), self.assertRaises(ToolError):
                registry.call("count", arguments)
        with self.assertRaises(ValueError):
            registry.register(tool)
        for invalid in (Tool("bad.name", "Bad", {}, lambda args: None),
                        Tool("bad", "Bad", None, lambda args: None),
                        Tool("bad", "Bad", {"type": "object"}, None)):
            with self.assertRaises(ValueError):
                registry.register(invalid)
        with self.assertRaises(ToolError):
            registry.call("missing", {})
        exposed = registry.schemas()
        exposed[0]["function"]["parameters"]["required"].clear()
        with self.assertRaises(ToolError):
            registry.call("count", {})
        cloned = registry.clone()
        cloned.register(Tool("other", "Other", {"type": "object"}, lambda args: 3))
        self.assertEqual(len(cloned.schemas()), 2)
        self.assertEqual(len(registry.schemas()), 1)
        cloned._tools["count"].input_schema["required"].clear()
        with self.assertRaises(ToolError):
            registry.call("count", {})

    def test_write_read_search_edit_and_mode_crlf_preservation(self):
        self.call("write_file", {"path": "sample.py", "content": "value = 1\r\n"})
        path = self.root / "sample.py"
        path.chmod(0o640)
        self.assertEqual(self.call("read_file", {"path": "sample.py"})["content"], "value = 1\r\n")
        self.assertEqual(self.call("search_text", {"query": "value"})["matches"][0]["line"], 1)
        self.call("edit_file", {"path": "sample.py", "old_text": "1", "new_text": "2"})
        self.assertEqual(path.read_bytes(), b"value = 2\r\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.call("list_files", {})["files"], ["sample.py"])
        self.assertEqual(list(self.root.glob(".agent-*")), [])

    def test_edits_must_match_once_and_fail_without_modifying_file(self):
        (self.root / "a").write_text("same same")
        for old in ("", "missing", "same"):
            with self.subTest(old=old), self.assertRaises(ToolError):
                self.call("edit_file", {"path": "a", "old_text": old, "new_text": "changed"})
        self.assertEqual((self.root / "a").read_text(), "same same")

    def test_escape_symlink_and_protected_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            other = Path(outside) / "secret"
            other.write_text("secret")
            (self.root / "escape").symlink_to(other)
            for path in ("../outside", str(other), "escape", ".env", ".git/config", "debugger_settings.json"):
                with self.subTest(path=path), self.assertRaises(ToolError):
                    self.call("write_file", {"path": path, "content": "bad"})
            self.assertEqual(other.read_text(), "secret")
            self.assertNotIn("escape", self.call("list_files", {})["files"])

    def test_nonregular_binary_and_large_reads_fail(self):
        (self.root / "binary").write_bytes(b"\xff")
        (self.root / "large").write_bytes(b"a" * 1_000_001)
        for name in ("binary", "large", "."):
            with self.subTest(name=name), self.assertRaises(ToolError):
                self.call("read_file", {"path": name})
        if hasattr(os, "mkfifo"):
            os.mkfifo(str(self.root / "pipe"))
            with self.assertRaises(ToolError):
                self.call("read_file", {"path": "pipe"})
        with self.assertRaises(ToolError):
            self.call("search_text", {"query": ""})

    def test_missing_parent_and_unicode_byte_limit(self):
        with self.assertRaises(ToolError):
            self.call("write_file", {"path": "missing/a", "content": "x"})
        with self.assertRaises(ToolError):
            self.call("write_file", {"path": "large", "content": "é" * 600000})

    def test_execution_is_explicit_and_argv_timeout_output_are_bounded(self):
        with self.assertRaises(ToolError):
            self.call("run_command", {"argv": [sys.executable, "--version"]})
        call = WorkspaceTools(self.root, allow_execute=True).registry.call
        self.assertIn("literal;echo", call("run_command", {"argv": [sys.executable, "-c", "import sys; print(sys.argv[1])", "literal;echo"]})["output"])
        result = call("run_command", {"argv": [sys.executable, "-c", "print('x'*100000)"]})
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["output"]), 65536)
        self.assertTrue(call("run_command", {"argv": [sys.executable, "-c", "import time; time.sleep(10)"], "timeout": 0.1})["timed_out"])
        for arguments in ({"argv": []}, {"argv": ["echo"], "timeout": 0}, {"argv": "echo"}):
            with self.assertRaises(ToolError):
                call("run_command", arguments)

    def test_git_inspection_stays_inside_nested_workspace_and_excludes_secrets(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        nested = self.root / "nested"
        nested.mkdir()
        for name in ("outside", "nested/inside", "nested/.env", "nested/debugger_settings.json"):
            (self.root / name).write_text("initial\n")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        for name in ("outside", "nested/inside", "nested/.env", "nested/debugger_settings.json"):
            (self.root / name).write_text("changed " + name + "\n")
        call = WorkspaceTools(nested).registry.call
        for tool in ("git_diff", "git_status"):
            output = call(tool, {})["output"]
            self.assertIn("inside", output)
            self.assertNotIn("outside", output)
            self.assertNotIn(".env", output)
            self.assertNotIn("debugger_settings", output)


if __name__ == "__main__":
    unittest.main()
