# Local LLM design proposal

Status: original design proposal, partially superseded by the implemented v1.
Requested on 2026-10-30. The current public API is documented in
[coding-agent.md](coding-agent.md) and `llm/AGENTS.md`: dictionary messages with
`chat(messages, tools=(), options=None) -> ChatResponse`, and text-delta `stream`.
Typed ChatRequest/ChatEvent and managed process startup below remain proposals.
Tool calling is now implemented for the coding harness. BaseLLM, llama.cpp chat,
health, model discovery, streaming, bounds and cleanup are implemented and tested.

## Goal and constraints

Provide a reusable parent class with stable methods, attributes, inputs, outputs,
and errors. Implement llama.cpp as its first subclass so callers can change
backends without rewriting their conversation or evaluation code.

Use a locally installed `llama-server` with GGUF models the user has already
downloaded. Python communicates with it over numeric loopback HTTP using only
the standard library. No model downloads, automatic installs, cloud services,
or Python binding dependencies. The feature is optional: normal debugger startup
must neither need llama.cpp nor contact an inference server.

The user relaxed the single-file rule on 2026-10-30. Shared inference code will
live in `llm/`, separate from the debugger (`app/`), local chat website (`webapp/`),
and terminal chat (`cli/`). All applications use the same parent contract and
backend subclasses. The original sketches below record design rationale; use
the implementation index for actual filenames and supported signatures.

## Dependency direction

```text
Future application / evaluation callers
                 |
                 v
     BaseLLM + shared value types
                 ^
                 | inherits
          LlamaCppLLM
                 |
                 v
       LocalHTTPTransport ----> existing llama-server ----> local GGUF

Later optional managed mode:
       LlamaCppServerProcess ----> owns a child llama-server
```

The parent knows nothing about llama.cpp flags, endpoints, subprocesses, GGUF
paths, or chat templates. The adapter translates the common contract into the
backend protocol. Conversation storage and prompt construction belong to callers.
The model server applies its configured chat template; do not hand-build model
specific prompt wrappers in the parent.

## Proposed file structure

```text
AGENTS.md                     root constraints, mandatory testing, and navigation
debugger.py                   compatibility launcher for app/
app/                          implemented modular Python debugger
  AGENTS.md
webapp/                       future local chat website; guidance only
  AGENTS.md
cli/                          future terminal chat; guidance only
  AGENTS.md
llm/                          shared package; guidance exists, Python files planned
  AGENTS.md
  __init__.py                 planned explicit public exports
  base.py                     planned BaseLLM wrappers and abstract hooks
  types.py                    planned immutable common value types
  errors.py                   planned shared error hierarchy
  llama_cpp.py                planned LlamaCppLLM subclass and backend config
  transport.py                planned bounded local HTTP/SSE transport
  process.py                  later optional managed llama-server lifecycle
docs/
  AGENTS.md                   indexes this proposal and architecture.md
  architecture.md             current implemented architecture
  llm-design.md               this proposed contract and boundaries
tests/
  AGENTS.md                   index new test files when implemented
  test_llm.py                 planned shared contract and adapter tests
  test_llama_process.py       planned only when managed processes are added
evaluations/
  AGENTS.md                   index real-model scenarios when added
  local-llm-smoke.md          planned manual, opt-in real-model procedure
memory/
  AGENTS.md
  plan.md                     live implementation checklist
  session-history.md          chronological decisions and outcomes
  learned-facts.md            durable requirements and verified facts
```

The application/shared-library folders exist with `AGENTS.md` indexes. Only
`app/` currently has runtime code. Add the planned LLM modules as they are
implemented and tested, without empty Python stubs or speculative provider
hierarchies. Existing tests and examples remain where they are.

## Shared data contract

Use Python 3.8-compatible standard-library dataclasses, `abc.ABC`, and `typing`.
Prefer immutable value objects (including tuples for message collections).

| Type | Fields / behavior |
| --- | --- |
| `LLMConfig` | Logical `model` identifier, `request_timeout_s`, default `GenerationOptions`; immutable and contains no backend flags |
| `ChatMessage` | `role` (`system`, `user`, `assistant`) and text `content`; text-only in v1 |
| `GenerationOptions` | `max_tokens`, `temperature`, `top_p`, tuple of `stop` strings, optional `seed`; validated finite numbers and bounds |
| `ChatRequest` | Tuple of messages plus optional complete per-request options override; no mutation of shared defaults |
| `TokenUsage` | Optional `input_tokens`, `output_tokens`, `total_tokens`; unavailable counts stay `None` |
| `ChatResponse` | Text, actual model identifier, normalized finish reason, usage, optional backend request ID |
| `ChatEvent` | Either `delta` with incremental text, or one terminal `done` carrying a `ChatResponse` |
| `LLMCapabilities` | Explicit supported features such as text chat and streaming; unsupported advanced features are not assumed |
| `HealthStatus` | `ready`, `loading`, `unavailable`, or `closed`, with a sanitized explanation |

Finish reasons normalize to `stop`, `length`, or `unknown` initially. Unsupported
response shapes must fail clearly rather than return empty successful responses.
Tool calls, structured output, embeddings, images, and tokenization are future
capabilities; do not pretend all models support them or add a generic unvalidated
`**kwargs` escape hatch to the stable API.

## Parent class and inheritance

Proposed public surface (signature sketch, not runtime implementation):

```python
class BaseLLM(ABC):
    # Read-only properties: provider, config, capabilities, closed
    def chat(self, request: ChatRequest) -> ChatResponse: ...
    def stream(self, request: ChatRequest) -> Iterator[ChatEvent]: ...
    def health(self) -> HealthStatus: ...
    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, exc_type, exc_value, traceback): ...

    @abstractmethod
    def _chat(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    def _health(self) -> HealthStatus: ...

    def _stream(self, request: ChatRequest) -> Iterator[ChatEvent]: ...
    def _close(self) -> None: ...


class LlamaCppLLM(BaseLLM):
    # provider = "llama_cpp"
    # Implements backend hooks; inherits the public contract.
    ...
```

The base owns validation, default-option resolution, closed-state checks,
capability checks, and idempotent cleanup/context management. Public wrappers
call backend hooks; subclasses implement transport/protocol behavior. Default
`_stream` raises `LLMUnsupportedFeatureError`; default `_close` is a no-op.
Subclasses must not require callers to use backend-specific public methods.

Use one synchronous API in v1. Do not add parallel async methods yet. Initial
clients permit one active generation per instance; overlapping calls raise
`LLMBusyError`. Closing an instance releases active transport resources. Closing
the stream iterator must release its connection in `finally`; never rely on
garbage collection. `stream` emits incremental text followed by a single `done`
event on successful completion. Cancellation or failure raises an error without
emitting a misleading success event. Reconstructed text must match the final
response; test this invariant.

## Errors and caller expectations

All operational errors derive from `LLMError`: configuration/validation,
connection/unavailable, timeout, backend HTTP error, protocol/malformed response,
unsupported feature, busy, cancelled, and closed errors. Preserve a safe backend
status/code where helpful without including prompts, credentials, or raw response
bodies in normal errors. Do not automatically retry generation: a retry could
repeat work or output. Health checks may be explicitly retried by startup logic.

Distinguish a model loading (health HTTP 503 with a loading response), an absent
server, an unknown model, and a malformed response. Unknown usage stays unknown.
Do not estimate tokens from character counts. A seeded request does not promise
identical output across hardware, builds, or model configurations.

## llama.cpp adapter and transport

`LlamaCppConfig` contains the numeric loopback endpoint (default proposed:
`http://127.0.0.1:8080`), optional in-memory API key, and bounded transport limits.
Keep it separate from backend-neutral `LLMConfig`. The model identifier is the
server's model ID or alias, not necessarily a GGUF filesystem path.

- Use `GET /health` for readiness, `GET /v1/models` to resolve/validate the loaded
  model identity, and `POST /v1/chat/completions` for text chat and streaming.
- Prefer `http.client` with explicit connections. Accept numeric IPv4/IPv6
  loopback only; reject remote addresses, credentials in URLs, redirects, and
  invalid endpoint paths. Bypass environment proxies and DNS. Keep model-server
  credentials separate from the debugger's browser token.
- Encode UTF-8 JSON; validate status, content type, response shape, and bounded
  response/error sizes. For streaming, parse SSE incrementally across arbitrary
  byte boundaries, comments, multiline data, Unicode, and `[DONE]`. An early EOF
  without normal completion is a protocol error. Request final usage where the
  supported server version permits it; otherwise leave usage unknown.
- Apply connect/read timeouts and a total request deadline. Blocking reads must
  be bounded by remaining deadline. Closing a stream releases its socket; verify
  actual backend cancellation behavior during the real-model smoke check.
- Keep HTTP transport injectable for tests, without exposing it to application
  callers. Inference runs in the Python host, separate from debugger workers.
  No browser endpoint, CSP change, automatic code submission, or UI integration
  is included in this first component.

## Downloaded model and process ownership

Phase one attaches to a server the user starts with a local GGUF. This supplies
the inheritance/API and inference functionality without coupling it to process
management. Document a local invocation after checking the installed executable
version; never download a model or infer its path automatically.

Phase two may add a composed `LlamaCppServerProcess` and `LlamaCppLaunchConfig`:
explicit executable and local model paths, context size, thread count, GPU layer
setting, startup timeout, and numeric loopback bind address. Validate options
against the selected installed version. Launch with an argument list, no shell,
explicit local model and offline settings; disallow download-related flags.
Capture bounded diagnostics and poll readiness with a deadline.

The process manager owns only the child it started. Closing an attached client
must not stop someone else's server. Managed teardown uses bounded terminate /
wait / kill and releases pipes; failures must not orphan children. Model switching
creates a new managed instance after cleanup; avoid an implicit shared singleton.
Do not inherit or reuse debugger subprocess generation state for LLM lifecycle.

## Delivery and validation

1. Define types, errors, base wrappers/hooks, and a tiny fake subclass; test the
   contract, immutable options, invalid input, capabilities, and closed state.
2. Implement attach-mode llama.cpp chat, health/model identity, endpoint validation,
   error normalization, timeouts, and local fake HTTP server tests.
3. Add incremental streaming, cancellation/cleanup, deadline handling, and tests
   for fragmented SSE, Unicode, terminal metadata, malformed payloads, and EOF.
4. Run the required smoke evaluation with the user's `Qwen3.5-4B-UD-Q3_K_XL`
   GGUF and local llama-server executable once available. Check readiness,
   nonstreaming chat, streaming, and transport cleanup using this exact model.
   Keep the normal automated suite independent of model availability. Record
   exact server version, model alias/quantization, relevant configuration, success
   criteria, observed timing, and failures without prompts/private paths in logs.
5. Add managed local process mode only as a distinct follow-up, with fake-process
   lifecycle tests and an optional real launch/cleanup check.

Run the existing Python regression suite for runtime changes, plus the new LLM
tests. Default tests require neither installed llama.cpp nor model files/GPU and
must use no internet. Real-model checks are explicit opt-in and report skips
honestly. User-facing configuration and UI integration are separate later scope;
update README and embedded Help if those behaviors are introduced.

## Source and remaining assumptions

Protocol basis: [official llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/tree/master/tools/server),
reviewed 2026-10-30, covering local model serving, health, model identity, chat,
streaming, and offline flags. Pin and test the actual installed build before
promising compatibility; upstream master is not a stable version guarantee.

Assumptions for the first implementation: text chat, a single selected loaded
model per client, user-managed server startup, and no UI. The user selected
`Qwen3.5-4B-UD-Q3_K_XL` as the required real-model test target and is downloading
it (2026-10-30). The installed model is now verified on the local server at
127.0.0.1:9931, with alias `unsloth/Qwen3.5-4B-GGUF:UD-Q3_K_XL`. The Python
provider passed health, discovery, chat, streaming and connection cleanup checks.
Private local model paths are deliberately not persisted in these documents.
