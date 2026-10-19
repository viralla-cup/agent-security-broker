"""A strict, deliberately small action contract. No executable model output."""

from dataclasses import dataclass
import json
import re

MAX_MESSAGE = 400_000


class Rejected(ValueError):
    pass


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected("INVALID_SCHEMA")
        result[key] = value
    return result


def parse_json(raw: bytes | str):
    if len(raw) > MAX_MESSAGE:
        raise Rejected("INVALID_SCHEMA")
    try:
        return json.loads(raw, object_pairs_hook=unique_mapping,
                          parse_constant=lambda _: (_ for _ in ()).throw(Rejected("INVALID_SCHEMA")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Rejected("INVALID_SCHEMA") from exc


def bounded_string(value, limit):
    if not isinstance(value, str):
        raise Rejected("INVALID_SCHEMA")
    try:
        if len(value.encode("utf-8")) > limit:
            raise Rejected("INVALID_SCHEMA")
    except UnicodeError as exc:
        raise Rejected("INVALID_SCHEMA") from exc
    return value


@dataclass(frozen=True)
class Action:
    request_id: str
    task_id: str
    tool: str
    path: str
    content: str | None = None

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict) or set(raw) != {"request_id", "task_id", "tool", "arguments"}:
            raise Rejected("INVALID_SCHEMA")
        rid = bounded_string(raw["request_id"], 64)
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", rid):
            raise Rejected("INVALID_SCHEMA")
        task = bounded_string(raw["task_id"], 64)
        tool = raw["tool"]
        if not isinstance(tool, str) or tool not in ("read_text", "write_new"):
            raise Rejected("UNKNOWN_TOOL")
        args = raw["arguments"]
        required = {"path"} if tool == "read_text" else {"path", "content"}
        if not isinstance(args, dict) or set(args) != required:
            raise Rejected("INVALID_SCHEMA")
        path = bounded_string(args["path"], 1024)
        content = bounded_string(args["content"], 65536) if tool == "write_new" else None
        return cls(rid, task, tool, path, content)


TOOL_SCHEMA = {
    "read_text": {"path": "absolute POSIX path (string)"},
    "write_new": {"path": "absolute POSIX path (string)", "content": "UTF-8 string, <= 65536 bytes"},
}
