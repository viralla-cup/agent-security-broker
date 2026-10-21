"""Offline live-pilot safety checks. Synthetic credentials; no provider requests."""

from dataclasses import replace
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import pytest

from agent_loop import Limits, run_agent
from backends.base import BackendError, TOOL_SCHEMA
from backends.openai import APIBudget, OpenAIBackend, input_token_reservation
from test_backends import HTTPDouble, KEY, MODEL, tool_response


@pytest.mark.parametrize("remaining,expected", [(30, 20), (2.5, 2.5), (0.01, 0.01)])
def test_http_timeout_is_capped_by_remaining_episode(remaining, expected):
    double = HTTPDouble([tool_response()])
    backend = OpenAIBackend(MODEL, KEY, opener=double, deadline=100 + remaining, clock=lambda: 100)
    backend.next_action([], TOOL_SCHEMA)
    assert double.requests[0][1] == pytest.approx(expected)


@pytest.mark.parametrize("remaining", [0, -1, float("nan"), float("inf")])
def test_expired_or_invalid_deadline_sends_no_request(remaining):
    double = HTTPDouble([])
    backend = OpenAIBackend(MODEL, KEY, opener=double, deadline=remaining, clock=lambda: 0)
    with pytest.raises(BackendError, match="BACKEND_TIMEOUT"):
        backend.next_action([], TOOL_SCHEMA)
    assert not double.requests and backend.calls == 0
    assert not backend.last_call["request_sent"]


def test_late_response_never_dispatches_or_retries():
    ticks = iter([0, 11])
    double = HTTPDouble([tool_response()])
    backend = OpenAIBackend(MODEL, KEY, opener=double, deadline=10, clock=lambda: next(ticks))
    result = run_agent("Task", backend, lambda _: pytest.fail("Late proposal dispatched"))
    assert result["stop_reason"] == "BACKEND_TIMEOUT" and result["steps"] == 0
    assert len(double.requests) == 1 and backend.reserved_output == 2048


@pytest.mark.parametrize("field,value", [("max_calls", 0), ("max_calls", 21),
                                        ("max_input_tokens_per_call", True),
                                        ("max_input_tokens_total", -1),
                                        ("max_output_tokens_total", 81921)])
def test_invalid_api_budgets_rejected(field, value):
    with pytest.raises(ValueError):
        replace(APIBudget(), **{field: value})


@pytest.mark.parametrize("field,value", [("max_input_tokens_per_call", 1),
                                        ("max_input_tokens_total", 1),
                                        ("max_output_tokens_total", 2047)])
def test_budget_check_happens_before_any_http(field, value):
    double = HTTPDouble([])
    backend = OpenAIBackend(MODEL, KEY, opener=double, budget=replace(APIBudget(), **{field: value}))
    with pytest.raises(BackendError, match="API_BUDGET_LIMIT"):
        backend.next_action([], TOOL_SCHEMA)
    assert not double.requests and not backend.last_call["request_sent"]


@pytest.mark.parametrize("limiter", ["calls", "input", "output"])
def test_reservations_accumulate_without_refund(limiter):
    double = HTTPDouble([tool_response(), tool_response()])
    probe = OpenAIBackend(MODEL, KEY, opener=double)
    probe.next_action([], TOOL_SCHEMA)
    reservation = input_token_reservation(double.requests[0][0].data)
    budget = APIBudget(max_calls=1 if limiter == "calls" else 8,
                       max_input_tokens_total=reservation if limiter == "input" else 65536,
                       max_output_tokens_total=2048 if limiter == "output" else 16384)
    double = HTTPDouble([tool_response()])
    backend = OpenAIBackend(MODEL, KEY, opener=double, budget=budget)
    backend.next_action([], TOOL_SCHEMA)
    assert backend.reserved_input == reservation and backend.reserved_output == 2048
    with pytest.raises(BackendError, match="API_BUDGET_LIMIT"):
        backend.next_action([], TOOL_SCHEMA)
    assert len(double.requests) == 1


@pytest.mark.parametrize("failure", [TimeoutError(KEY), URLError(KEY),
                                    HTTPError("https://example.invalid", 429, KEY, {}, None),
                                    HTTPError("https://example.invalid", 500, KEY, {}, None)])
def test_uncertain_failure_blocks_even_explicit_backend_reuse(failure):
    double = HTTPDouble([failure, tool_response()])
    backend = OpenAIBackend(MODEL, KEY, opener=double)
    result = run_agent("Task", backend, lambda _: pytest.fail("Unexpected dispatch"))
    assert result["steps"] == 0 and result["model_calls"] == 1 and result["retries"] == 0
    assert backend.last_call["request_sent"] and backend.reserved_output == 2048
    with pytest.raises(BackendError):
        backend.next_action([], TOOL_SCHEMA)
    assert len(double.requests) == 1
    assert KEY not in json.dumps(backend.last_call)


@pytest.mark.parametrize("usage", [None, [], {}, {"input_tokens": True},
                                  {"input_tokens": 999999, "output_tokens": 1, "total_tokens": 1000000},
                                  {"input_tokens": 1, "output_tokens": 4096, "total_tokens": 4097},
                                  {"input_tokens": 1, "output_tokens": 1, "total_tokens": 5}])
def test_missing_or_excess_usage_stops_before_tool_dispatch(usage):
    double = HTTPDouble([{**tool_response(), "usage": usage}])
    backend = OpenAIBackend(MODEL, KEY, opener=double)
    result = run_agent("Task", backend, lambda _: pytest.fail("Unchecked response dispatched"))
    assert result["stop_reason"] == "API_USAGE_ERROR" and result["steps"] == 0
    assert len(double.requests) == 1


@pytest.mark.parametrize("channel", ["history", "response", "model"])
def test_key_cannot_enter_payload_proposal_or_metadata(channel):
    response = tool_response(json.dumps({"path": KEY})) if channel == "response" else tool_response()
    double = HTTPDouble([response])
    backend = OpenAIBackend(KEY if channel == "model" else MODEL, KEY, opener=double)
    history = [{"text": KEY}] if channel == "history" else []
    with pytest.raises(BackendError, match="CREDENTIAL_LEAK_BLOCKED"):
        backend.next_action(history, TOOL_SCHEMA)
    assert len(double.requests) == (1 if channel == "response" else 0)
    assert KEY not in json.dumps(backend.last_call)


def test_reservation_includes_schema_instructions_and_escaped_history():
    double = HTTPDouble([tool_response()])
    backend = OpenAIBackend(MODEL, KEY, opener=double, reasoning_effort="none", max_output_tokens=1024)
    backend.next_action([{"text": "Synthetic \u00e9"}], TOOL_SCHEMA)
    body = double.requests[0][0].data
    assert backend.reserved_input == len(body) + 1024
    payload = json.loads(body)
    assert payload["service_tier"] == "default" and payload["reasoning"] == {"effort": "none"}
    assert payload["max_output_tokens"] == 1024


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_agent_pilot as runner


def test_first_live_plan_is_offline_exactly_one_b2_recovery(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    monkeypatch.setenv("OPENAI_MODEL", "ignored-environment-model")
    monkeypatch.setattr(runner, "docker", lambda *a, **k: pytest.fail("Docker used by plan"))
    monkeypatch.setattr(runner, "OpenAIBackend", lambda *a, **k: pytest.fail("API used by plan"))
    runner.main(["--first-live-pilot", "--plan"])
    output = capsys.readouterr().out
    assert KEY not in output
    plan = json.loads(output)
    assert (plan["episodes"], plan["condition"], plan["task"], plan["model"]) == (1, "B2", "recovery", "gpt-6-luna")
    assert plan["max_model_calls"] == 6 and plan["max_output_tokens_total"] == 6144
    assert plan["limits"]["max_seconds"] == 120 and plan["limits"]["max_retries"] == 0
    assert plan["network_calls_made"] == 0 and not plan["monetary_cap_guaranteed"]
    estimate = plan["cost_estimate"]
    assert estimate["estimated_upper_bound_excluding_taxes_usd"] == pytest.approx(
        49152 * estimate["conservative_cache_write_input_per_million"] / 1e6
        + 6144 * estimate["output_per_million"] / 1e6)


@pytest.mark.parametrize("arguments", [["--first-live-pilot"],
                                      ["--first-live-pilot", "--condition", "all", "--plan"],
                                      ["--backend", "openai", "--condition", "all", "--plan"],
                                      ["--backend", "openai", "--max-seconds", "0", "--plan"],
                                      ["--backend", "openai", "--api-timeout", "0", "--plan"]])
def test_runner_rejects_unapproved_or_invalid_configuration_before_io(arguments, monkeypatch):
    monkeypatch.setattr(runner, "docker", lambda *a, **k: pytest.fail("Unexpected Docker call"))
    with pytest.raises(SystemExit) as error:
        runner.main(arguments)
    assert error.value.code == 2


def test_pre_request_stop_is_not_exported_as_a_paid_attempt():
    from types import SimpleNamespace
    from lab.pilot_evidence import export_episode
    backend = SimpleNamespace(name="openai-responses", model=MODEL)
    episode = SimpleNamespace(seed="test", before={}, isolation={})
    task = {"id": "recovery", "expected_text": "Mean: 4\n", "completion_paths": ["project/output/report.txt"]}
    call = {"number": 1, "outcome": "API_BUDGET_LIMIT", "metadata": {"request_sent": False}}
    public, _ = export_episode(task, "B2", backend, Limits(), episode,
                              {"stop_reason": "API_BUDGET_LIMIT"}, [], [call], True, {})
    assert public["real_api_attempts"] == 0 and public["actual_llm_episodes"] == 0


@pytest.mark.parametrize("container", ["client", "broker"])
def test_container_credentials_stop_pilot_without_exposing_values(container, monkeypatch):
    from types import SimpleNamespace
    episode = SimpleNamespace(client="client", broker="broker")
    monkeypatch.setattr(runner, "docker", lambda _, name, *args:
                        json.dumps(["OPENAI_API_KEY=" + KEY] if name == container else ["PATH=/usr/bin"]))
    with pytest.raises(ValueError) as error:
        runner.check_credential_isolation(episode)
    assert KEY not in str(error.value)


def test_plan_does_not_print_key_misconfigured_as_model(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    monkeypatch.setenv("OPENAI_MODEL", KEY)
    with pytest.raises(SystemExit):
        runner.main(["--backend", "openai", "--plan"])
    output = capsys.readouterr()
    assert KEY not in output.out + output.err


def test_response_read_timeout_never_retries_or_dispatches():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            raise TimeoutError(KEY)

    class SlowBody:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            return Response()

    double = SlowBody()
    backend = OpenAIBackend(MODEL, KEY, opener=double)
    result = run_agent("Task", backend, lambda _: pytest.fail("Timed-out proposal dispatched"))
    assert result["stop_reason"] == "BACKEND_TIMEOUT" and double.calls == 1


def test_first_live_request_settings_match_cost_assumptions():
    double = HTTPDouble([tool_response()])
    backend = OpenAIBackend("gpt-6-luna", KEY, opener=double, reasoning_effort="none", max_output_tokens=1024)
    backend.next_action([], TOOL_SCHEMA)
    payload = json.loads(double.requests[0][0].data)
    assert payload["prompt_cache_options"] == {"ttl": "30m"}
    assert payload["service_tier"] == "default"
