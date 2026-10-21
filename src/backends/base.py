"""Provider-neutral proposal contract for the restricted experimental loop."""

from typing import Protocol

from broker.schema import Action, Rejected, parse_json


class BackendError(Exception):
    """Only fixed public error codes may cross the inference relay."""

    def __init__(self, code="BACKEND_ERROR"):
        self.code = code if code in {
            "BACKEND_ERROR", "INVALID_PROPOSAL", "MODEL_REFUSAL", "MODEL_INCOMPLETE",
            "BACKEND_TIMEOUT", "BACKEND_HTTP_ERROR", "BACKEND_RESPONSE_LIMIT",
            "API_BUDGET_LIMIT", "API_USAGE_ERROR", "CREDENTIAL_LEAK_BLOCKED",
        } else "BACKEND_ERROR"
        super().__init__(self.code)


class Backend(Protocol):
    def next_action(self, history: list[dict], tool_schema: dict) -> dict:
        """Return a tool proposal or a stop signal; do not execute any action."""
        ...


TOOL_SCHEMA = {
    "read_text": {
        "type": "object", "properties": {"path": {"type": "string"}},
        "required": ["path"], "additionalProperties": False,
    },
    "write_new": {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"], "additionalProperties": False,
    },
}


def validate_proposal(value):
    if not isinstance(value, dict):
        raise BackendError("INVALID_PROPOSAL")
    if set(value) == {"stop"} and value["stop"] in ("complete", "no_safe_continuation"):
        return value
    if set(value) != {"tool", "arguments"}:
        raise BackendError("INVALID_PROPOSAL")
    try:
        Action.parse({"request_id": "validation", "task_id": "mvp-task", **value})
    except Rejected:
        raise BackendError("INVALID_PROPOSAL") from None
    return value


def decode_proposal(raw):
    try:
        return validate_proposal(parse_json(raw))
    except Rejected:
        raise BackendError("INVALID_PROPOSAL") from None
