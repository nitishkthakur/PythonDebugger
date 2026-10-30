"""Offline provider contracts and local HTTP/SSE regressions; no models required."""
import dataclasses
import http.server
import json
import threading
import time
import unittest
from unittest import mock

from llm import (BaseLLM, ChatResponse, GenerationOptions, HealthStatus,
                 LLMBusyError, LLMClosedError, LLMHTTPError, LLMProtocolError,
                 LLMUnsupportedFeatureError, LLMValidationError, LlamaCppLLM)
from llm import LLMTimeoutError
from llm.transport import LocalHTTPTransport


MESSAGES = [{"role": "user", "content": "hello"}]
TOOL = {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}


class FakeLLM(BaseLLM):
    def _chat(self, messages, tools, options):
        return ChatResponse(messages[-1]["content"])

    def _health(self):
        return HealthStatus("ready")


class BaseContractTests(unittest.TestCase):
    def test_abstract_base_cannot_be_constructed(self):
        with self.assertRaises(TypeError):
            BaseLLM("x")

    def test_subclass_inherits_chat_health_context_and_close(self):
        with FakeLLM("fake") as provider:
            self.assertEqual(provider.model, "fake")
            self.assertEqual(provider.chat(MESSAGES).content, "hello")
            self.assertTrue(provider.health())
        self.assertTrue(provider.closed)
        provider.close()
        self.assertEqual(provider.health().status, "closed")
        with self.assertRaises(LLMClosedError):
            provider.chat(MESSAGES)
        with self.assertRaises(LLMClosedError):
            provider.__enter__()

    def test_options_are_immutable_and_per_request_overrides_do_not_leak(self):
        stops = ["END"]
        options = GenerationOptions(stop=stops)
        stops.append("NEW")
        self.assertEqual(options.stop, ("END",))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            options.max_tokens = 1
        provider = FakeLLM("fake", options)
        provider.chat(MESSAGES, options={"max_tokens": 1})
        self.assertIs(provider.options, options)

    def test_invalid_models_messages_and_options(self):
        for model in ("", None, 3):
            with self.subTest(model=model), self.assertRaises(LLMValidationError):
                FakeLLM(model)
        provider = FakeLLM("fake")
        for messages in ([], {}, [None], [{"role": "bogus", "content": "x"}],
                         [{"role": "tool", "content": "x"}], [{"role": "user", "content": 3}]):
            with self.subTest(messages=messages), self.assertRaises(LLMValidationError):
                provider.chat(messages)
        for options in ({"max_tokens": 0}, {"max_tokens": True}, {"temperature": float("nan")},
                        {"top_p": 2}, {"stop": "x"}, {"seed": True}, {"unknown": 3}):
            with self.subTest(options=options), self.assertRaises(LLMValidationError):
                provider.chat(MESSAGES, options=options)
        self.assertEqual(provider.chat(MESSAGES).content, "hello")

    def test_unsupported_capabilities_are_explicit(self):
        provider = FakeLLM("fake")
        with self.assertRaises(LLMUnsupportedFeatureError):
            provider.chat(MESSAGES, tools=[TOOL])
        with self.assertRaises(LLMUnsupportedFeatureError):
            list(provider.stream(MESSAGES))

    def test_busy_and_error_paths_release_state(self):
        provider = FakeLLM("fake")
        def nested(*args):
            provider.chat(MESSAGES)
        with mock.patch.object(provider, "_chat", side_effect=nested):
            with self.assertRaises(LLMBusyError):
                provider.chat(MESSAGES)
        self.assertEqual(provider.chat(MESSAGES).content, "hello")


class HTTPProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(self.server.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(self.server.payload).encode())

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                self.server.request_body = json.loads(body)
                self.send_response(self.server.status)
                self.send_header("Content-Type", self.server.content_type)
                self.end_headers()
                if self.server.slow:
                    try:
                        for byte in self.server.body:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.025)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    return
                self.wfile.write(self.server.body)

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = "http://127.0.0.1:%s" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def setUp(self):
        self.server.status = 200
        self.server.slow = False
        self.server.content_type = "application/json"
        self.server.payload = {"status": "ok"}
        self.server.body = json.dumps({"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]}).encode()
        self.provider = LlamaCppLLM("test", self.endpoint)
        self.addCleanup(self.provider.close)

    def test_chat_serializes_contract_without_mutating_inputs(self):
        response = self.provider.chat(MESSAGES, options={"max_tokens": 12})
        self.assertEqual(response.content, "hello")
        self.assertEqual(response.usage, {})
        self.assertEqual(self.server.request_body["max_tokens"], 12)
        self.assertFalse(self.server.request_body["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(MESSAGES, [{"role": "user", "content": "hello"}])

    def test_structured_tool_call_round_trip(self):
        call = {"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
        self.server.body = json.dumps({"choices": [{"message": {"content": None, "tool_calls": [call]}, "finish_reason": "tool_calls"}]}).encode()
        response = self.provider.chat(MESSAGES, [TOOL])
        self.assertEqual(response.tool_calls, (call,))
        self.assertEqual(response.finish_reason, "tool_calls")
        self.assertEqual(self.server.request_body["tools"], [TOOL])

    def test_health_and_models(self):
        self.assertTrue(self.provider.health())
        self.server.status = 503
        self.assertEqual(self.provider.health().status, "loading")
        self.server.status = 200
        self.server.payload = {"data": [{"id": "test"}]}
        self.assertEqual(self.provider.list_models(), ("test",))

    def test_http_errors_are_sanitized_and_no_retry_occurs(self):
        self.server.status = 401
        self.server.body = b"secret diagnostic"
        with self.assertRaises(LLMHTTPError) as error:
            self.provider.chat(MESSAGES)
        self.assertEqual(error.exception.status, 401)
        self.assertNotIn("secret", str(error.exception))
        self.assertFalse(self.provider._busy)

    def test_bad_json_shapes_and_content_type(self):
        for body in (b"not json", b"[]", b"{}", b'{"choices":[]}',
                     b'{"choices":[{"message":{"content":3}}]}'):
            self.server.body = body
            with self.subTest(body=body), self.assertRaises(LLMProtocolError):
                self.provider.chat(MESSAGES)
        self.server.content_type = "text/html"
        with self.assertRaises(LLMProtocolError):
            self.provider.chat(MESSAGES)

    def test_bounded_response(self):
        self.provider._transport.max_bytes = 1024
        self.server.body = b" " * 2048
        with self.assertRaises(LLMProtocolError):
            self.provider.chat(MESSAGES)

    def test_stream_unicode_and_terminal_event(self):
        self.server.content_type = "text/event-stream"
        event = json.dumps({"choices": [{"delta": {"content": "héllo"}}]}, ensure_ascii=False)
        self.server.body = (": ping\r\n\r\ndata: " + event + "\r\n\r\ndata: [DONE]\n\n").encode()
        self.assertEqual("".join(self.provider.stream(MESSAGES)), "héllo")
        self.assertFalse(self.provider._busy)
        self.assertFalse(self.provider._transport._connections)

    def test_stream_eof_and_invalid_events_fail(self):
        self.server.content_type = "text/event-stream"
        for body in (b"data: {}\n\n", b"data: bad\n\n", b"data: {}"):
            self.server.body = body
            with self.subTest(body=body), self.assertRaises(LLMProtocolError):
                list(self.provider.stream(MESSAGES))
        self.assertFalse(self.provider._busy)

    def test_abandoned_stream_closes_connection_and_releases_busy(self):
        self.server.content_type = "text/event-stream"
        self.server.body = b'data: {"choices":[{"delta":{"content":"a"}}]}\n\ndata: [DONE]\n\n'
        stream = self.provider.stream(MESSAGES)
        self.assertEqual(next(stream), "a")
        with self.assertRaises(LLMBusyError):
            self.provider.chat(MESSAGES)
        stream.close()
        self.assertFalse(self.provider._busy)
        self.assertFalse(self.provider._transport._connections)

    def test_invalid_endpoint_and_transport_limits(self):
        for endpoint in ("http://example.com", "http://localhost", "https://127.0.0.1", "http://127.0.0.1/path", "http://user:pass@127.0.0.1", "http://127.0.0.1?x=1"):
            with self.subTest(endpoint=endpoint), self.assertRaises(LLMValidationError):
                LocalHTTPTransport(endpoint)
        for timeout in (0, -1, float("inf"), True):
            with self.subTest(timeout=timeout), self.assertRaises(LLMValidationError):
                LocalHTTPTransport(self.endpoint, timeout)

    def test_closed_transport_rejects_new_requests_without_opening_connection(self):
        transport = LocalHTTPTransport(self.endpoint)
        transport.close()
        with self.assertRaises(LLMClosedError):
            transport.json("GET", "/health")
        self.assertFalse(transport._connections)

    def test_http10_slow_drip_is_interrupted_by_total_deadline(self):
        self.server.slow = True
        provider = LlamaCppLLM("test", self.endpoint, timeout=0.08)
        started = time.monotonic()
        try:
            with self.assertRaises(LLMTimeoutError):
                provider.chat(MESSAGES)
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertFalse(provider._transport._connections)
        finally:
            provider.close()


if __name__ == "__main__":
    unittest.main()
