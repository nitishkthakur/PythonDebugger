"""Run state and explicit, caller-owned atomic checkpoints."""
import json
import os
from pathlib import Path
import tempfile
from dataclasses import dataclass, field, asdict


@dataclass
class RunState:
    messages: list = field(default_factory=list)
    todos: list = field(default_factory=list)
    steps: int = 0
    status: str = "ready"
    output: str = ""
    harness_version: str = "v1"
    workspace_root: str = ""


class CheckpointStore:
    """Persist trusted local transcripts; paths must be selected by the caller."""
    def __init__(self, path):
        self.path = Path(path)

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".agent-", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(asdict(state), stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, str(self.path))
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def load(self):
        if self.path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("checkpoint exceeds 16 MiB")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("harness_version") != "v1":
            raise ValueError("unsupported checkpoint version")
        state = RunState(**data)
        if (not isinstance(state.messages, list) or not isinstance(state.todos, list)
                or type(state.steps) is not int or state.steps < 0
                or not isinstance(state.status, str) or not isinstance(state.output, str)):
            raise ValueError("invalid checkpoint state")
        return state
