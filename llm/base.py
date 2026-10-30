"""Stable synchronous inference contract with inherited validation/lifecycle."""
from abc import ABC, abstractmethod
import copy
import json
import threading

from .errors import (LLMBusyError, LLMClosedError, LLMValidationError,
                     LLMUnsupportedFeatureError)
from .types import GenerationOptions, HealthStatus, LLMCapabilities


class BaseLLM(ABC):
    provider = "base"
    capabilities = LLMCapabilities()

    def __init__(self, model, options=None):
        if not isinstance(model, str) or not model.strip():
            raise LLMValidationError("model must be a nonempty identifier")
        self._model = model
        self._options = self._resolve_options(options)
        self._closed = False
        self._busy = False
        self._lock = threading.RLock()

    @property
    def model(self):
        return self._model

    @property
    def options(self):
        return self._options

    @property
    def closed(self):
        return self._closed

    def _resolve_options(self, options):
        if options is None:
            return getattr(self, "_options", GenerationOptions())
        if isinstance(options, GenerationOptions):
            return options
        if isinstance(options, dict):
            try:
                return GenerationOptions(**options)
            except TypeError:
                raise LLMValidationError("Unknown generation option") from None
        raise LLMValidationError("options must be GenerationOptions or a mapping")

    def _begin(self, messages, tools, options):
        if not isinstance(messages, (tuple, list)) or not messages:
            raise LLMValidationError("messages must be a nonempty sequence")
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in ("system", "user", "assistant", "tool"):
                raise LLMValidationError("Invalid message role")
            if not isinstance(message.get("content"), str) and not (message.get("role") == "assistant" and message.get("tool_calls") and message.get("content") is None):
                raise LLMValidationError("Messages must contain text")
            if message["role"] == "tool" and not isinstance(message.get("tool_call_id"), str):
                raise LLMValidationError("Tool messages require tool_call_id")
        if not isinstance(tools, (tuple, list)):
            raise LLMValidationError("tools must be a sequence")
        if tools and not self.capabilities.tool_calling:
            raise LLMUnsupportedFeatureError("Provider does not support tool calls")
        for tool in tools:
            if not isinstance(tool, dict) or tool.get("type") != "function" or not isinstance(tool.get("function"), dict):
                raise LLMValidationError("Invalid function tool schema")
            fn = tool["function"]
            if not isinstance(fn.get("name"), str) or not fn["name"] or not isinstance(fn.get("parameters"), dict):
                raise LLMValidationError("Tool needs name and parameters")
        resolved = self._resolve_options(options)
        try:
            json.dumps((messages, tools), allow_nan=False)
        except (TypeError, ValueError):
            raise LLMValidationError("Messages and schemas must be JSON data") from None
        with self._lock:
            if self._closed:
                raise LLMClosedError("Provider is closed")
            if self._busy:
                raise LLMBusyError("Provider already has an active request")
            self._busy = True
        return copy.deepcopy(messages), copy.deepcopy(tools), resolved

    def _end(self):
        with self._lock:
            self._busy = False

    def chat(self, messages, tools=(), options=None):
        messages, tools, options = self._begin(messages, tools, options)
        try:
            return self._chat(messages, tools, options)
        finally:
            self._end()

    def stream(self, messages, tools=(), options=None):
        """Yield text deltas; explicitly close an abandoned iterator."""
        if not self.capabilities.streaming:
            raise LLMUnsupportedFeatureError("Provider does not support streaming")
        messages, tools, options = self._begin(messages, tools, options)
        try:
            yield from self._stream(messages, tools, options)
        finally:
            self._end()

    def health(self):
        if self.closed:
            return HealthStatus("closed")
        return self._health()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._close()

    def __enter__(self):
        if self.closed:
            raise LLMClosedError("Provider is closed")
        return self

    def __exit__(self, *args):
        self.close()

    @abstractmethod
    def _chat(self, messages, tools, options):
        raise NotImplementedError

    @abstractmethod
    def _health(self):
        raise NotImplementedError

    def _stream(self, messages, tools, options):
        raise LLMUnsupportedFeatureError("Provider does not support streaming")

    def _close(self):
        pass
