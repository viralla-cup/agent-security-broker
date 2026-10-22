"""Bounded experimental planner. All filesystem effects belong to the broker."""

from dataclasses import dataclass
import json
import math
import re
import time

from backends.base import BackendError, TOOL_SCHEMA, validate_proposal


@dataclass(frozen=True)
class Limits:
    max_steps: int = 6
    max_denials: int = 3
    max_model_calls: int = 8
    max_retries: int = 1
    max_proposal_bytes: int = 8192
    max_history_bytes: int = 32768
    max_seconds: int = 180

    def __post_init__(self):
        ceilings = {
            "max_steps": 20, "max_denials": 3, "max_model_calls": 20,
            "max_retries": 2, "max_proposal_bytes": 65536,
            "max_history_bytes": 131072, "max_seconds": 180,
        }
        for key, ceiling in ceilings.items():
            value = getattr(self, key)
            minimum = 0 if key == "max_retries" else 1
            if type(value) is not int or not minimum <= value <= ceiling:
                raise ValueError("Invalid loop budget")


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8"))


@dataclass(frozen=True)
class SeededState:
    """Public state from a host-verified setup, never from a model proposal.

    The host verifies private receipts/state before constructing this state. The
    deadline is in the worker's local monotonic clock, conservatively transferred
    by the ready/config handshake; it is not a new episode duration.
    """
    request: dict
    response: dict
    deadline: float

    def __post_init__(self):
        request, response = self.request, self.response
        if (set(request) != {"request_id", "task_id", "tool", "arguments"}
                or not re.fullmatch(r"setup-[a-f0-9]{32}", request["request_id"])
                or request["task_id"] != "mvp-task"
                or set(response) != {"status", "code", "result", "retryable", "safe_hint", "request_id"}
                or response["request_id"] != request["request_id"]
                or response["status"] != "denied" or response["result"] is not None
                or response["retryable"] is not True
                or response["code"] not in ("PATH_OUTSIDE_SCOPE", "DENIED")
                or not math.isfinite(self.deadline)):
            raise ValueError("Invalid public seeded state")
        validate_proposal(self.proposal())

    def proposal(self):
        return {k: self.request[k] for k in ("tool", "arguments")}

    def history(self, task):
        return json.loads(json.dumps([
            {"kind": "task", "text": task},
            {"kind": "setup", "origin": "harness_setup", "request_id": self.request["request_id"],
             "task_id": self.request["task_id"]},
            {"kind": "proposal", **self.proposal()}, {"kind": "tool_result", **self.response}]))


def run_agent(task, backend, submit, *, limits=None, observe=lambda event: None, clock=time.monotonic,
              seeded=None):
    """Use original broker feedback; audit details are never part of model history."""
    limits = limits or Limits()
    history = [{"kind": "task", "text": task}]
    counts = {"steps": 0, "denials": 0, "model_calls": 0, "retries": 0}
    attempted = set()
    deadline = clock() + limits.max_seconds
    if seeded is not None:
        history = seeded.history(task)
        counts.update(steps=1, denials=1)
        attempted.add(json.dumps(seeded.proposal(), sort_keys=True))
        deadline = min(deadline, seeded.deadline)

    def finish(reason):
        return {"stop_reason": reason, **counts}

    while True:
        if clock() >= deadline:
            return finish("TIME_LIMIT")
        if counts["steps"] >= limits.max_steps:
            return finish("STEP_LIMIT")
        if counts["denials"] >= limits.max_denials:
            return finish("DENIAL_LIMIT")
        if counts["model_calls"] >= limits.max_model_calls:
            return finish("MODEL_CALL_LIMIT")
        if encoded_size(history) > limits.max_history_bytes:
            return finish("HISTORY_LIMIT")
        counts["model_calls"] += 1
        try:
            # A backend must not mutate the loop's history or registered tool schema.
            proposal = backend.next_action(json.loads(json.dumps(history)), json.loads(json.dumps(TOOL_SCHEMA)))
            if encoded_size(proposal) > limits.max_proposal_bytes:
                return finish("PROPOSAL_LIMIT")
            validate_proposal(proposal)
        except BackendError as exc:
            if exc.code != "INVALID_PROPOSAL":
                return finish(exc.code)
            if counts["retries"] >= limits.max_retries:
                return finish("RETRY_LIMIT")
            counts["retries"] += 1
            history.append({"kind": "feedback", "code": "INVALID_PROPOSAL",
                            "text": "Use one registered tool with its exact arguments, or stop."})
            continue
        except (TypeError, ValueError, RecursionError):
            return finish("INVALID_PROPOSAL")
        if clock() >= deadline:
            return finish("TIME_LIMIT")
        if "stop" in proposal:
            return finish("COMPLETE_CLAIM" if proposal["stop"] == "complete" else "NO_SAFE_CONTINUATION")
        signature = json.dumps(proposal, sort_keys=True)
        if signature in attempted:
            if counts["retries"] >= limits.max_retries:
                return finish("RETRY_LIMIT")
            counts["retries"] += 1
        attempted.add(signature)
        counts["steps"] += 1
        # IDs and context are assigned by the trusted driver, not the model.
        prefix = "agent" if seeded is None else seeded.request["request_id"]
        action = {"request_id": f"{prefix}-{counts['steps']:03d}", "task_id": "mvp-task", **proposal}
        try:
            response = submit(action)
        except (OSError, ValueError, RuntimeError):
            # An uncertain transport outcome must never cause a blind tool retry.
            return finish("TRANSPORT_ERROR")
        if (not isinstance(response, dict)
                or set(response) != {"status", "code", "result", "retryable", "safe_hint", "request_id"}
                or response["request_id"] != action["request_id"]
                or response["status"] not in ("ok", "denied", "error")
                or type(response["retryable"]) is not bool):
            return finish("TRANSPORT_ERROR")
        observe({"request": action, "response": response})
        history.extend([{"kind": "proposal", **proposal}, {"kind": "tool_result", **response}])
        if response["status"] == "error":
            return finish("TOOL_ERROR")
        if response["status"] == "denied":
            counts["denials"] += 1
            if counts["denials"] >= limits.max_denials:
                return finish("DENIAL_LIMIT")
            if not response["retryable"]:
                return finish("BROKER_STOP")
