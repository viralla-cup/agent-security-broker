"""Offline API-contract tests. HTTP doubles never contact a provider."""

from io import BytesIO
import json
from urllib.error import HTTPError, URLError

import pytest

from backends.base import BackendError, TOOL_SCHEMA
from backends.openai import OpenAIBackend, NoRedirect

KEY = "SYNTHETIC_KEY_FOR_OFFLINE_TESTS"
MODEL = "test-model"


class HTTPDouble:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return BytesIO(response if isinstance(response, bytes) else json.dumps(response).encode())


def tool_response(arguments='{"path":"/lab/project/input.txt"}', name="read_text"):
    return {"status": "completed", "model": MODEL, "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            "output": [{"type": "function_call", "name": name, "arguments": arguments}]}


def final_response(text='{"stop":"complete"}'):
    return {**tool_response(), "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def test_responses_contract_and_feedback_roundtrip_without_network():
    double = HTTPDouble([tool_response(), final_response('{"stop":"no_safe_continuation"}')])
    backend = OpenAIBackend(MODEL, KEY, opener=double)
    history = [{"kind": "task", "text": "Synthetic task"}]
    assert backend.next_action(history, TOOL_SCHEMA)["tool"] == "read_text"
    history.append({"kind": "tool_result", "status": "denied", "code": "DENIED", "safe_hint": None})
    assert backend.next_action(history, TOOL_SCHEMA) == {"stop": "no_safe_continuation"}
    for request, timeout in double.requests:
        data = json.loads(request.data)
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert KEY not in request.data.decode()
        assert data["model"] == MODEL and data["store"] is False and data["parallel_tool_calls"] is False
        assert data["max_output_tokens"] == 2048 and timeout == 20
        assert {tool["name"] for tool in data["tools"]} == {"read_text", "write_new"}
        assert all(tool["type"] == "function" and tool["strict"] for tool in data["tools"])
    assert json.loads(json.loads(double.requests[-1][0].data)["input"][0]["content"]) == history


@pytest.mark.parametrize("response,code", [
    (b"{bad", "INVALID_PROPOSAL"),
    (b"x" * 262145, "BACKEND_RESPONSE_LIMIT"),
    ({"status": "incomplete", "output": []}, "MODEL_INCOMPLETE"),
    ({"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]}, "MODEL_REFUSAL"),
    (tool_response(name="shell"), "INVALID_PROPOSAL"),
    (tool_response('{"path":"one","path":"two"}'), "INVALID_PROPOSAL"),
    (tool_response('{"path":1}'), "INVALID_PROPOSAL"),
    ({**tool_response(), "output": tool_response()["output"] * 2}, "INVALID_PROPOSAL"),
    (final_response("PRIVATE_UNSTRUCTURED_TEXT"), "INVALID_PROPOSAL"),
    (final_response('{"tool":"read_text","arguments":{"path":"/lab/project/input.txt"}}'), "INVALID_PROPOSAL"),
    (HTTPError("https://example.invalid", 401, KEY, {}, None), "BACKEND_HTTP_ERROR"),
    (URLError(KEY), "BACKEND_ERROR"),
    (TimeoutError(KEY), "BACKEND_TIMEOUT"),
])
def test_provider_failures_are_bounded_sanitized_and_not_retried(response, code):
    if isinstance(response, dict):
        response.setdefault("usage", tool_response()["usage"])
    double = HTTPDouble([response])
    backend = OpenAIBackend(MODEL, KEY, opener=double)
    with pytest.raises(BackendError) as error:
        backend.next_action([], TOOL_SCHEMA)
    assert str(error.value) == code and KEY not in str(error.value)
    assert len(double.requests) == 1


def test_redirect_does_not_forward_credentials():
    with pytest.raises(BackendError, match="BACKEND_HTTP_ERROR"):
        NoRedirect().redirect_request(None, None, None, None, None, None)


@pytest.mark.parametrize("model,key,tokens", [("", KEY, 2048), ("model\nbad", KEY, 2048),
                                            (MODEL, "", 2048), (MODEL, KEY, 100000)])
def test_invalid_backend_configuration_fails_before_http(model, key, tokens):
    with pytest.raises(ValueError):
        OpenAIBackend(model, key, max_output_tokens=tokens)


def test_invalid_tool_set_and_oversized_history_fail_before_http():
    backend = OpenAIBackend(MODEL, KEY, opener=HTTPDouble([]))
    for history, schema in [([], {"shell": {}}), ([{"text": "x" * 131073}], TOOL_SCHEMA)]:
        with pytest.raises(BackendError):
            backend.next_action(history, schema)
