"""Small shared values, independent of inference engines and applications."""
from dataclasses import dataclass, field
import math
from typing import Optional, Tuple

from .errors import LLMValidationError


@dataclass(frozen=True)
class GenerationOptions:
    max_tokens: int = 1024
    temperature: float = 0.2
    top_p: float = 1.0
    stop: Tuple[str, ...] = ()
    seed: Optional[int] = None

    def __post_init__(self):
        if type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise LLMValidationError("max_tokens must be a positive integer")
        for name, low, high in (("temperature", 0, 2), ("top_p", 0, 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise LLMValidationError("Invalid %s" % name)
        if not isinstance(self.stop, (list, tuple)) or any(not isinstance(s, str) or not s for s in self.stop):
            raise LLMValidationError("stop must contain nonempty strings")
        object.__setattr__(self, "stop", tuple(self.stop))
        if self.seed is not None and type(self.seed) is not int:
            raise LLMValidationError("seed must be an integer")


@dataclass(frozen=True)
class LLMCapabilities:
    text_chat: bool = True
    streaming: bool = False
    tool_calling: bool = False


@dataclass(frozen=True)
class ChatResponse:
    """Frozen outer value; contained JSON dictionaries are caller-owned copies."""
    content: str
    tool_calls: tuple = ()
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)


@dataclass(frozen=True)
class HealthStatus:
    status: str
    message: str = ""

    def __bool__(self):
        return self.status == "ready"
