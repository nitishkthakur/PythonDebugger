"""Launch a configurable local coding agent without optional dependencies."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys

from coding_tools import create_workspace_registry
from harness import create_harness, HarnessConfig, CheckpointStore
from llm import LlamaCppLLM


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local versioned coding agent")
    parser.add_argument("task", nargs="?", help="coding task; required unless --resume")
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--model", default="unsloth/Qwen3.5-4B-GGUF:UD-Q3_K_XL")
    parser.add_argument("--endpoint", default="http://127.0.0.1:9931")
    parser.add_argument("--harness", default="v1")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--allow-execute", action="store_true", help="allow host commands; NOT a sandbox")
    parser.add_argument("--allow-mcp", action="store_true", help="approve tools from explicitly configured MCP servers")
    parser.add_argument("--subagents", action="store_true", help="enable isolated read-only task delegation")
    parser.add_argument("--mcp-config", help="local JSON list of {name, argv, cwd?} servers")
    parser.add_argument("--checkpoint", help="explicit local transcript file (may contain code)")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if not args.task and not args.resume:
        parser.error("task is required unless --resume is used")
    if args.resume and not args.checkpoint:
        parser.error("--resume requires --checkpoint")
    try:
        registry = create_workspace_registry(args.root, allow_execute=args.allow_execute)
        checkpoint = CheckpointStore(args.checkpoint) if args.checkpoint else None
        state = checkpoint.load() if args.resume else None
        config = HarnessConfig(max_steps=args.max_steps)
        root_instructions = Path(args.root).resolve() / "AGENTS.md"
        if root_instructions.is_file():
            if root_instructions.stat().st_size > 16000:
                raise ValueError("root AGENTS.md exceeds instruction budget")
            from dataclasses import replace
            config = replace(config, system_prompt=config.system_prompt + "\nWorkspace guidance:\n" + root_instructions.read_text(encoding="utf-8"))
        def approval(name, arguments):
            return ((args.allow_write and name in ("write_file", "edit_file"))
                    or (args.allow_execute and name == "run_command")
                    or (args.allow_mcp and name.startswith("mcp_")))
        with ExitStack() as stack:
            model = stack.enter_context(LlamaCppLLM(args.model, args.endpoint))
            if args.mcp_config:
                from mcp_local import MCPClient
                config_path = Path(args.mcp_config)
                if config_path.stat().st_size > 65536:
                    raise ValueError("MCP config exceeds 64 KiB")
                servers = json.loads(config_path.read_text(encoding="utf-8"))
                if not isinstance(servers, list) or len(servers) > 16:
                    raise ValueError("MCP config must be a list of at most 16 servers")
                for server in servers:
                    client = stack.enter_context(MCPClient(server["argv"], cwd=server.get("cwd")))
                    client.register_tools(registry, namespace="mcp_" + server["name"])
            factory = (lambda: LlamaCppLLM(args.model, args.endpoint)) if args.subagents else None
            agent = create_harness(args.harness, model=model, tools=registry, config=config,
                                   approval=approval, checkpoint=checkpoint, subagent_factory=factory,
                                   workspace_root=args.root)
            result = agent.run(args.task, state=state)
            print(result.output or "Agent stopped: " + result.status)
            return 0 if result.status == "completed" else 2
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130
    except Exception as error:
        print("Agent failed (%s): %s" % (type(error).__name__, error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
