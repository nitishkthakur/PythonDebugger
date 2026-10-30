"""llama.cpp chat adapter; attaches to a server without owning its process."""
import json
from dataclasses import asdict

from .base import BaseLLM
from .errors import (LLMConnectionError, LLMHTTPError, LLMProtocolError,
                     LLMTimeoutError, LLMUnsupportedFeatureError)
from .transport import LocalHTTPTransport
from .types import ChatResponse, HealthStatus, LLMCapabilities


class LlamaCppLLM(BaseLLM):
    provider = "llama_cpp"
    capabilities = LLMCapabilities(streaming=True, tool_calling=True)

    def __init__(self, model, endpoint="http://127.0.0.1:9931", timeout=60,
                 options=None, enable_thinking=False):
        super().__init__(model, options)
        self._transport = LocalHTTPTransport(endpoint, timeout)
        self.enable_thinking = bool(enable_thinking)

    def _body(self, messages, tools, options, stream=False):
        body = {"model": self.model, "messages": messages, "stream": stream,
                "chat_template_kwargs": {"enable_thinking": self.enable_thinking}}
        body.update({key: value for key, value in asdict(options).items() if value is not None})
        if tools:
            body["tools"] = tools
        return body

    def _chat(self, messages, tools, options):
        payload = self._transport.json("POST", "/v1/chat/completions", self._body(messages, tools, options))
        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = message.get("content")
            calls = message.get("tool_calls") or []
            if content is None:
                content = ""
            if not isinstance(content, str) or not isinstance(calls, list):
                raise ValueError()
            for call in calls:
                if not isinstance(call, dict) or not isinstance(call.get("id"), str) or call.get("type") != "function":
                    raise ValueError()
                function = call["function"]
                if not isinstance(function.get("name"), str) or not isinstance(function.get("arguments"), str):
                    raise ValueError()
            reason = choice.get("finish_reason")
            if not content and not calls:
                raise ValueError()
            usage = payload.get("usage") or {}
            if not isinstance(usage, dict):
                raise ValueError()
            return ChatResponse(content, tuple(calls), reason if reason in ("stop", "length", "tool_calls") else "unknown", usage)
        except (KeyError, TypeError, IndexError, ValueError, AttributeError):
            raise LLMProtocolError("Invalid chat response") from None

    def _health(self):
        try:
            value = self._transport.json("GET", "/health")
            return HealthStatus("ready" if value.get("status") == "ok" else "unavailable")
        except LLMHTTPError as exc:
            return HealthStatus("loading" if exc.status == 503 else "unavailable")
        except (LLMConnectionError, LLMTimeoutError):
            return HealthStatus("unavailable")

    def list_models(self):
        if self.closed:
            from .errors import LLMClosedError
            raise LLMClosedError("Provider is closed")
        payload = self._transport.json("GET", "/v1/models")
        try:
            models = tuple(item["id"] for item in payload["data"])
            if any(not isinstance(model, str) for model in models):
                raise ValueError()
            return models
        except (KeyError, TypeError, ValueError):
            raise LLMProtocolError("Invalid model list") from None

    def _stream(self, messages, tools, options):
        if tools:
            raise LLMUnsupportedFeatureError("Use chat for structured tool calls; stream is text-only")
        events = self._transport.events("/v1/chat/completions", self._body(messages, tools, options, True))
        try:
            for event in events:
                if event == "[DONE]":
                    return
                try:
                    payload = json.loads(event)
                    for choice in payload.get("choices", []):
                        delta = choice["delta"]
                        if delta.get("tool_calls"):
                            raise LLMUnsupportedFeatureError("Tool calls cannot be consumed as text deltas")
                        content = delta.get("content")
                        if content is not None:
                            if not isinstance(content, str):
                                raise ValueError()
                            yield content
                except (ValueError, KeyError, TypeError, AttributeError):
                    raise LLMProtocolError("Invalid streaming response") from None
            raise LLMProtocolError("Stream ended without DONE")
        finally:
            events.close()

    def _close(self):
        self._transport.close()
