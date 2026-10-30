"""Regression checks for the modular application layout and its documentation."""
import ast
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import settings, worker  # noqa: E402


class ApplicationLayoutTests(unittest.TestCase):
    def test_module_entry_point_help(self):
        result = subprocess.run([sys.executable, "-B", "-S", "-m", "app", "--help"],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--settings", result.stdout)
        self.assertIn("--script", result.stdout)

    def test_script_launchers_work_from_unrelated_directory_in_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            for entry in (ROOT / "debugger.py", ROOT / "app" / "debugger.py"):
                with self.subTest(entry=entry.name, parent=entry.parent.name):
                    result = subprocess.run([sys.executable, "-I", "-S", str(entry), "--help"],
                                            cwd=directory, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("--no-browser", result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_imports_do_not_start_transports_processes_or_threads(self):
        script = textwrap.dedent("""\
            import importlib
            import sys
            import threading
            def audit(event, args):
                if event in ('socket.bind', 'socket.connect', 'subprocess.Popen', 'webbrowser.open'):
                    raise AssertionError('import side effect: ' + event)
            sys.addaudithook(audit)
            before = threading.active_count()
            for name in ('app', 'app.worker', 'app.settings', 'app.ui',
                         'app.debugger', 'app.__main__', 'debugger'):
                importlib.import_module(name)
            assert threading.active_count() == before
            """)
        result = subprocess.run([sys.executable, "-B", "-S", "-c", script],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_entry_points_reject_missing_folder_without_writing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = os.path.join(directory, "missing")
            settings_path = os.path.join(directory, "settings.json")
            commands = (["-m", "app"], [str(ROOT / "app" / "debugger.py")],
                        [str(ROOT / "debugger.py")])
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run([sys.executable, "-B", "-S"] + command
                                            + [missing, "--no-browser", "--settings", settings_path],
                                            cwd=str(ROOT), capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("not a folder", result.stderr)
                    self.assertFalse(os.path.exists(settings_path))

    def test_settings_keep_existing_distribution_root_location(self):
        with mock.patch.object(settings.os, "access", return_value=True):
            self.assertEqual(settings.SettingsStore.default_path(),
                             str(ROOT / "debugger_settings.json"))

    def test_settings_keep_home_fallback_when_distribution_is_read_only(self):
        with mock.patch.object(settings.os, "access", return_value=False):
            self.assertEqual(settings.SettingsStore.default_path(),
                             os.path.join(os.path.expanduser("~"), ".debugger_py_settings.json"))

    def test_tracer_excludes_its_extracted_worker_module(self):
        tracer = worker.Dbg(None)
        self.assertFalse(tracer.is_user(worker.__file__))
        self.assertTrue(tracer.is_user(str(ROOT / "examples" / "demo.py")))

    def test_all_runtime_python_sources_use_python38_grammar(self):
        sources = [ROOT / "debugger.py"]
        for folder in ("app", "cli", "llm", "coding_tools", "mcp_local", "harness"):
            sources.extend(sorted((ROOT / folder).glob("*.py")))
        for path in sources:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=8)


class GuidanceTests(unittest.TestCase):
    def test_maintained_folders_have_local_guidance(self):
        for folder in (".", "app", "webapp", "cli", "llm", "docs", "tests",
                       "examples", "memory", "evaluations", "coding_tools", "mcp_local", "harness"):
            with self.subTest(folder=folder):
                self.assertTrue((ROOT / folder / "AGENTS.md").is_file())

    def test_implemented_file_indexes_resolve(self):
        for folder in (".", "app", "docs", "tests", "examples", "memory", "cli", "llm", "harness"):
            index = ROOT / folder / "AGENTS.md"
            text = index.read_text(encoding="utf-8")
            names = re.findall(r"^\| `([^`]+)` \|", text, re.MULTILINE)
            self.assertTrue(names, "no indexed files in %s" % index)
            for name in names:
                with self.subTest(index=folder, file=name):
                    self.assertTrue((index.parent / name).is_file(), name)

    def test_local_markdown_links_resolve(self):
        paths = [ROOT / "README.md", ROOT / "AGENTS.md"]
        paths += sorted((ROOT / "docs").glob("*.md"))
        paths += sorted((ROOT / "memory").glob("*.md"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                with self.subTest(document=path.name, target=target):
                    self.assertTrue((path.parent / target).exists())


if __name__ == "__main__":
    unittest.main()
