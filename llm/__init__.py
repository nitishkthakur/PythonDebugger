"""Reusable provider contracts. Importing never connects to a model server."""
from .base import BaseLLM
from .llama_cpp import LlamaCppLLM
from .types import ChatResponse, GenerationOptions, HealthStatus, LLMCapabilities
from .errors import (LLMError, LLMValidationError, LLMConnectionError,
                     LLMTimeoutError, LLMProtocolError, LLMHTTPError,
                     LLMClosedError, LLMBusyError, LLMUnsupportedFeatureError)

__all__ = ["BaseLLM", "LlamaCppLLM", "ChatResponse", "GenerationOptions",
           "HealthStatus", "LLMCapabilities", "LLMError", "LLMValidationError",
           "LLMConnectionError", "LLMTimeoutError", "LLMProtocolError", "LLMHTTPError",
           "LLMClosedError", "LLMBusyError", "LLMUnsupportedFeatureError"]
