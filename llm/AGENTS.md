# Shared LLM package index

Read root guidance and `docs/llm-design.md` before implementing here.

Implemented reusable inference package. The current v1 public contract is
`chat(messages, tools=(), options=None) -> ChatResponse`, where messages/tools
are JSON dictionaries and `tool_calls` preserve OpenAI-style call IDs, names,
and argument strings. This supersedes the earlier typed ChatRequest sketch.
`stream(...)` yields text chunks; structured tool calls use `chat`, rather than
silently discarding tool-call events. Close abandoned stream iterators explicitly.

| File | Responsibility |
| --- | --- |
| `__init__.py` | Small, explicit public API exports |
| `base.py` | Abstract BaseLLM contract, shared validation, lifecycle, backend hooks |
| `types.py` | Frozen GenerationOptions, ChatResponse, capabilities, HealthStatus |
| `errors.py` | Shared LLM exception hierarchy |
| `llama_cpp.py` | LlamaCppLLM subclass and backend configuration/protocol translation |
| `transport.py` | Bounded loopback HTTP and SSE transport |

The optional process manager is not implemented. LlamaCppLLM attaches to an
existing server and never stops it. Model metadata can be inspected explicitly
with `list_models()`. Default endpoint uses numeric loopback; cloud URLs,
hostnames, URL credentials, redirects, and proxy lookup are not supported.

Run `python3 -m unittest discover -s tests -p test_llm.py -v`: fake provider
contract and local HTTP/SSE tests require no models or installed llama.cpp.
The real Qwen smoke evaluation is separate and opt-in.

Applications (`app/`, `webapp/`, `cli/`) depend on these contracts. This package
must never depend on those applications. Use inheritance for backend contracts
and composition for transport/process ownership. Support Python 3.8 without
packages, automatic downloads, cloud requests, or import-time inference/server
startup. Keep tests in `tests/`; real-model checks are opt-in under `evaluations/`.
Update planned/implemented status and this index as files are actually added.
