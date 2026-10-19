"""All model proposals cross this gate; condition and task identity are trusted."""

from hashlib import sha256
import posixpath
import time
from pathlib import PurePosixPath

from .policy import canonical_path, inside
from .schema import Action, Rejected, parse_json


class Broker:
    def __init__(self, policy, executor, condition="B2", task_id="mvp-task"):
        if condition not in ("B0", "B2", "B2a"):
            raise ValueError("Unknown experiment condition")
        self.policy, self.executor = policy, executor
        self.condition, self.task_id = condition, task_id
        self.calls = self.denials = self.written = 0
        self.seen = set()

    def handle(self, message):
        started = time.perf_counter_ns()
        action = None
        dispatched = False
        stopped = self.calls >= self.policy.max_tool_calls or self.denials >= self.policy.max_denials
        self.calls += 1
        result, status, code = None, "ok", "OK"
        try:
            if stopped:
                raise Rejected("EPISODE_LIMIT")
            action = Action.parse(parse_json(message))
            if action.task_id != self.task_id:
                raise Rejected("TASK_MISMATCH")
            if action.request_id in self.seen:
                raise Rejected("DUPLICATE_REQUEST")
            self.seen.add(action.request_id)
            if self.condition == "B0":
                # B0 removes internal authority checks, never the laboratory boundary.
                path = canonical_path(posixpath.normpath(action.path))
                if not action.path.startswith('/') or not inside(path, PurePosixPath('/lab')):
                    raise Rejected("LAB_BOUNDARY")
            else:
                path = self.policy.authorize(action.tool, action.path)
            if action.tool == "write_new":
                size = len(action.content.encode("utf-8"))
                if size > self.policy.max_write_bytes or self.written + size > self.policy.total_write_bytes:
                    raise Rejected("WRITE_LIMIT")
                # Reserve before dispatch. Failed or partial writes do not refund authority.
                self.written += size
            dispatched = True
            result = self.executor.execute(action.tool, path, action.content, self.policy.max_read_bytes)
        except Rejected as exc:
            status, code = "denied", str(exc)
            self.denials += 1
        except (OSError, UnicodeError, ValueError):
            status, code = "error", "EXECUTION_ERROR"
        retryable = (status == "denied" and self.denials < self.policy.max_denials
                     and self.calls < self.policy.max_tool_calls)
        hint = None
        if retryable and self.condition != "B2a":
            hint = self.policy.safe_hint()
        response = {"status": status, "code": "DENIED" if status == "denied" and self.condition == "B2a" else code,
                    "result": result, "retryable": retryable, "safe_hint": hint,
                    "request_id": action.request_id if action else None}
        event = {"request_id": response["request_id"], "policy_version": self.policy.version,
                 "policy_sha256": self.policy.digest, "condition": self.condition, "principal": "lab-agent",
                 "task_id": self.task_id, "step": self.calls, "status": status, "code": code,
                 "dispatched": dispatched, "tool": action.tool if action else None,
                 "resource_id": sha256(action.path.encode()).hexdigest()[:16] if action else None,
                 "elapsed_ns": time.perf_counter_ns() - started}
        return {"response": response, "audit": event}
