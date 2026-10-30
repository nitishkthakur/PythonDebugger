"""Provider-independent tool contracts and input validation."""
import copy
from dataclasses import dataclass
import json
import math
import re
from typing import Callable


class ToolError(Exception):
    """Invalid invocation or failed tool operation; safe to show to the agent."""


def validate(value, schema, path="arguments"):
    """Validate our intentionally small JSON Schema subset, not full JSON Schema."""
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool,
             "integer": int, "number": (int, float), "null": type(None)}
    if kind and (kind not in types or not isinstance(value, types[kind])
                 or kind in ("integer", "number") and isinstance(value, bool)):
        raise ToolError("%s must be %s" % (path, kind))
    if isinstance(value, float) and not math.isfinite(value):
        raise ToolError("%s must be finite" % path)
    if "enum" in schema and value not in schema["enum"]:
        raise ToolError("%s has an unsupported value" % path)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise ToolError("%s.%s is required" % (path, key))
        for key, item in value.items():
            if key not in props:
                if schema.get("additionalProperties") is False:
                    raise ToolError("%s.%s is not supported" % (path, key))
            else:
                validate(item, props[key], path + "." + key)
    if isinstance(value, list):
        if len(value) > schema.get("maxItems", 10000):
            raise ToolError("%s contains too many items" % path)
        for item in value:
            validate(item, schema.get("items", {}), path + "[]")
    if isinstance(value, str) and len(value) > schema.get("maxLength", 1_000_000):
        raise ToolError("%s is too long" % path)
    if kind in ("integer", "number"):
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ToolError("%s is out of range" % path)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable

    def execute(self, arguments):
        validate(arguments, self.input_schema)
        return self.handler(arguments)


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        if not isinstance(tool, Tool) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tool.name):
            raise ValueError("invalid tool or name")
        if tool.name in self._tools:
            raise ValueError("duplicate tool: " + tool.name)
        if (not isinstance(tool.input_schema, dict) or tool.input_schema.get("type") != "object"
                or not isinstance(tool.description, str) or not callable(tool.handler)):
            raise ValueError("tool schema must describe an object")
        stored = Tool(tool.name, tool.description, copy.deepcopy(tool.input_schema), tool.handler)
        self._tools[tool.name] = stored
        return stored

    def register_many(self, tools):
        """Validate an entire plugin before publishing any of its tools."""
        pending = ToolRegistry()
        for tool in tools:
            pending.register(tool)
        if set(pending._tools).intersection(self._tools):
            raise ValueError("plugin contains an already registered tool")
        self._tools.update(pending._tools)

    def clone(self):
        """Copy registry membership and schemas; handlers keep their service owner."""
        result = ToolRegistry()
        result.register_many(self._tools.values())
        return result

    def schemas(self):
        return [{"type": "function", "function": {"name": tool.name,
                 "description": tool.description, "parameters": copy.deepcopy(tool.input_schema)}}
                for tool in self._tools.values()]

    def call(self, name, arguments):
        if name not in self._tools:
            raise ToolError("unknown tool: " + str(name))
        try:
            result = self._tools[name].execute(arguments)
            json.dumps(result, allow_nan=False)
            return result
        except ToolError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise ToolError("tool operation failed (%s)" % type(exc).__name__) from exc
