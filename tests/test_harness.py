"""Deterministic contract tests: no model downloads or inference required."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from coding_tools import Tool, ToolRegistry, create_workspace_registry
from harness import CodingHarness, HarnessConfig, CheckpointStore, create_harness, register_harness
from llm import ChatResponse


def call(name, arguments, id="call1"):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.seen = []
        self.closed = False

    def chat(self, messages, tools=()):
        self.seen.append(json.loads(json.dumps(messages)))
        return next(self.responses)

    def close(self):
        self.closed = True


class HarnessTests(unittest.TestCase):
    def test_tool_round_trip_and_plan(self):
        todo = {"content": "inspect", "status": "completed"}
        model = ScriptedModel([ChatResponse("", (call("write_todos", {"todos": [todo]}),)), ChatResponse("done")])
        events = []
        state = CodingHarness(model, ToolRegistry(), hooks=(events.append,)).run("work")
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.output, "done")
        self.assertEqual(state.todos, [todo])
        self.assertEqual(model.seen[1][-1]["tool_call_id"], "call1")
        self.assertEqual(events[-1]["event"], "finished")
        self.assertFalse(model.closed)  # caller owns the parent model

    def test_write_approval_and_denial(self):
        with tempfile.TemporaryDirectory() as root:
            for allowed in (False, True):
                model = ScriptedModel([ChatResponse("", (call("write_file", {"path": "a.txt", "content": "hello"}),)), ChatResponse("done")])
                agent = CodingHarness(model, create_workspace_registry(root), approval=lambda n, a: allowed)
                state = agent.run("write")
                self.assertEqual(json.loads(state.messages[-2]["content"])["ok"], allowed)
            self.assertEqual((Path(root) / "a.txt").read_text(), "hello")

    def test_all_calls_paired_for_invalid_unknown_and_throwing_tools(self):
        calls = [call("read_file", {}, "a"), call("unknown", {}, "b"), call("read_file", {}, "c")]
        calls[-1]["function"]["arguments"] = "not json"
        model = ScriptedModel([ChatResponse("", tuple(calls)), ChatResponse("done")])
        state = CodingHarness(model, ToolRegistry()).run("test")
        results = [m for m in state.messages if m["role"] == "tool"]
        self.assertEqual([r["tool_call_id"] for r in results], ["a", "b", "c"])
        self.assertTrue(all(not json.loads(r["content"])["ok"] for r in results))

    def test_step_context_and_cancel_limits(self):
        model = ScriptedModel([ChatResponse("", (call("write_todos", {"todos": []}),))])
        state = CodingHarness(model, ToolRegistry(), HarnessConfig(max_steps=1)).run("work")
        self.assertEqual(state.status, "step_limit")
        self.assertEqual(state.messages[-1]["role"], "tool")
        model = ScriptedModel([])
        state = CodingHarness(model, ToolRegistry(), HarnessConfig(max_context_chars=1)).run("work")
        self.assertEqual(state.status, "context_limit")
        cancel = threading.Event(); cancel.set()
        state = CodingHarness(ScriptedModel([]), ToolRegistry()).run("work", cancel=cancel)
        self.assertEqual(state.status, "cancelled")

    def test_malformed_call_batch_fails_before_assistant_is_recorded(self):
        model = ScriptedModel([ChatResponse("", (call("read_file", {}), call("read_file", {})))])
        agent = CodingHarness(model, ToolRegistry())
        with tempfile.TemporaryDirectory() as root:
            store = CheckpointStore(Path(root) / "state.json")
            agent.checkpoint = store
            with self.assertRaises(ValueError): agent.run("work")
            saved = store.load()
            self.assertEqual(saved.status, "failed")
            self.assertEqual(saved.messages[-1]["role"], "user")

    def test_observer_failure_does_not_break_tool_pairs(self):
        def broken(event): raise RuntimeError("bad observer")
        agent = CodingHarness(ScriptedModel([ChatResponse("", (call("write_todos", {"todos": []}),)), ChatResponse("ok")]), ToolRegistry(), hooks=(broken,))
        state = agent.run("work")
        self.assertEqual(state.status, "completed")
        self.assertTrue(agent.hook_errors)
        self.assertEqual(state.messages[-2]["role"], "tool")

    def test_checkpoints_resume_and_versions(self):
        with tempfile.TemporaryDirectory() as root:
            store = CheckpointStore(Path(root) / "sub" / "state.json")
            state = CodingHarness(ScriptedModel([ChatResponse("first")]), ToolRegistry(), checkpoint=store).run("one")
            restored = store.load()
            self.assertEqual(restored.messages, state.messages)
            next_state = CodingHarness(ScriptedModel([ChatResponse("second")]), ToolRegistry()).run("two", restored)
            self.assertEqual(next_state.steps, 2)
            Path(store.path).write_text('{"harness_version":"future"}')
            with self.assertRaises(ValueError): store.load()
        with self.assertRaises(ValueError): create_harness("missing")
        with self.assertRaises(ValueError): register_harness("v1", CodingHarness)

    def test_isolated_readonly_subagent_and_cleanup(self):
        children = []
        def factory():
            child = ScriptedModel([ChatResponse("child result")]); children.append(child); return child
        parent = ScriptedModel([ChatResponse("", (call("task", {"task": "review"}),)), ChatResponse("reviewed")])
        state = CodingHarness(parent, ToolRegistry(), subagent_factory=factory).run("parent task")
        self.assertTrue(children[0].closed)
        self.assertEqual(children[0].seen[0][-1]["content"], "review")
        self.assertNotIn("parent task", str(children[0].seen))
        self.assertIn("child result", state.messages[-2]["content"])

    def test_invalid_configuration(self):
        for values in ({"max_steps": 0}, {"max_tool_calls": True}, {"max_subagent_depth": -1}, {"system_prompt": ""}):
            with self.subTest(values=values), self.assertRaises(ValueError): HarnessConfig(**values)

    def test_registry_is_reusable_and_resume_rejects_unpaired_turns(self):
        registry = ToolRegistry()
        first = CodingHarness(ScriptedModel([ChatResponse("one")]), registry)
        second = CodingHarness(ScriptedModel([ChatResponse("two")]), registry)
        self.assertEqual(registry.schemas(), [])
        state = first.run("work")
        self.assertEqual(second.run("more", state).output, "two")
        state.messages.append({"role": "assistant", "content": "", "tool_calls": [call("read_file", {})]})
        with self.assertRaises(ValueError): first.run(state=state)

    def test_truncated_response_is_incomplete(self):
        state = CodingHarness(ScriptedModel([ChatResponse("unfinished", finish_reason="length")]), ToolRegistry()).run("work")
        self.assertEqual(state.status, "incomplete")

    def test_workspace_binding_and_completed_resume(self):
        with tempfile.TemporaryDirectory() as root:
            first = CodingHarness(ScriptedModel([ChatResponse("done")]), ToolRegistry(), workspace_root=root)
            state = first.run("work")
            self.assertIs(first.run(state=state), state)
            other = CodingHarness(ScriptedModel([]), ToolRegistry(), workspace_root=str(Path(root) / "other"))
            with self.assertRaises(ValueError): other.run("continue", state)

    def test_harness_uses_real_mcp_plugin_without_provider_coupling(self):
        from mcp_local import MCPClient
        repository = str(Path(__file__).resolve().parent.parent)
        with tempfile.TemporaryDirectory() as root:
            Path(root, "note.txt").write_text("plugin result")
            with MCPClient([sys.executable, "-m", "mcp_local.server", "--root", root], cwd=repository) as client:
                registry = ToolRegistry()
                client.register_tools(registry, namespace="test")
                model = ScriptedModel([ChatResponse("", (call("test__read_file", {"path": "note.txt"}),)), ChatResponse("done")])
                state = CodingHarness(model, registry, approval=lambda n,a: n == "test__read_file").run("read")
                result = json.loads(state.messages[-2]["content"])
                self.assertTrue(result["ok"])
                self.assertIn("plugin result", str(result))

    def test_registered_harness_subclass_uses_its_version(self):
        class Custom(CodingHarness): version = "test-custom"
        register_harness("test-custom", Custom)
        instance = create_harness("test-custom", model=ScriptedModel([ChatResponse("custom")]), tools=ToolRegistry())
        self.assertEqual(instance.run("task").harness_version, "test-custom")

    def test_invalid_tool_function_shape_rejected(self):
        invalid = call("read_file", {})
        invalid["function"]["arguments"] = {}
        with self.assertRaises(ValueError):
            CodingHarness(ScriptedModel([ChatResponse("", (invalid,))]), ToolRegistry()).run("work")

    def test_cli_help_and_bad_arguments(self):
        root = str(Path(__file__).resolve().parent.parent)
        result = subprocess.run([sys.executable, "-m", "cli", "--help"], cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--harness", result.stdout)
        result = subprocess.run([sys.executable, "-m", "cli", "--resume"], cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__": unittest.main()
