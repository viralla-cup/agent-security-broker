"""Offline UID-10002 agent loop; inference crosses a bounded stdio relay."""

import json
import sys

from agent_loop import Limits, run_agent
from backends.base import BackendError
from broker.schema import parse_json
from .client import send_action

MAX_FRAME = 400_000


def emit(frame):
    sys.stdout.write(json.dumps(frame, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def receive():
    line = sys.stdin.buffer.readline(MAX_FRAME + 1)
    if not line or len(line) > MAX_FRAME or not line.endswith(b"\n"):
        raise BackendError()
    return parse_json(line)


class RelayBackend:
    def next_action(self, history, tool_schema):
        emit({"kind": "model", "history": history, "tool_schema": tool_schema})
        reply = receive()
        if not isinstance(reply, dict):
            raise BackendError()
        if set(reply) == {"error"}:
            raise BackendError(reply["error"])
        if set(reply) != {"proposal"}:
            raise BackendError()
        return reply["proposal"]


def main():
    try:
        config = receive()
        outcome = run_agent(config["task"], RelayBackend(), send_action,
                            limits=Limits(**config["limits"]),
                            observe=lambda exchange: emit({"kind": "tool", **exchange}))
        emit({"kind": "done", "outcome": outcome})
    except Exception:
        # Never expose a task, path, provider payload, or traceback on stderr.
        emit({"kind": "worker_error"})
        raise SystemExit(1)


if __name__ == "__main__":
    main()
