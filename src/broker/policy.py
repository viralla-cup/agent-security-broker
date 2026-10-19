"""Load trusted YAML once, reject ambiguous configuration, freeze every field."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import yaml

from .schema import Rejected, unique_mapping


class StrictLoader(yaml.SafeLoader):
    pass


def mapping(loader, node):
    return unique_mapping([(loader.construct_object(k), loader.construct_object(v))
                           for k, v in node.value])


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def canonical_path(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise Rejected("INVALID_PATH")
    if any(ord(c) < 32 or ord(c) > 126 for c in path) or any(c in path for c in "\\:%"):
        raise Rejected("INVALID_PATH")
    parts = path.split("/")[1:]
    if not parts or any(p in ("", ".", "..") for p in parts):
        raise Rejected("INVALID_PATH")
    return PurePosixPath(path)


def inside(path, root):
    return path == root or root in path.parents


@dataclass(frozen=True)
class Policy:
    version: str
    digest: str
    protected: tuple[PurePosixPath, ...]
    grants: tuple[tuple[str, PurePosixPath], ...]
    max_read_bytes: int
    max_write_bytes: int
    total_write_bytes: int
    max_tool_calls: int
    max_denials: int

    @classmethod
    def load(cls, file):
        data = Path(file).read_bytes()
        try:
            raw = yaml.load(data, Loader=StrictLoader)
            if not isinstance(raw, dict) or set(raw) != {"version", "default", "precedence", "protected_roots", "allow", "limits"}:
                raise ValueError("Invalid policy fields")
            if raw["default"] != "deny" or raw["precedence"] != "deny_overrides":
                raise ValueError("Only default denial with denial precedence is supported")
            if not isinstance(raw["version"], str) or not raw["version"]:
                raise ValueError("Invalid policy version")
            if not isinstance(raw["protected_roots"], list) or not raw["protected_roots"]:
                raise ValueError("Protected roots are required")
            grants = raw["allow"]
            if not isinstance(grants, dict) or set(grants) != {"read_text", "write_new"}:
                raise ValueError("Exactly two tool grants are required")
            limits = raw["limits"]
            ceilings = {"max_read_bytes": 65536, "max_write_bytes": 65536, "total_write_bytes": 262144,
                        "max_tool_calls": 20, "max_denials": 3}
            if not isinstance(limits, dict) or set(limits) != set(ceilings):
                raise ValueError("Invalid limits")
            if any(type(limits[k]) is not int or not 1 <= limits[k] <= v for k, v in ceilings.items()):
                raise ValueError("Limits exceed laboratory ceilings")
            protected = tuple(canonical_path(p) for p in raw["protected_roots"])
            frozen_grants = tuple((t, canonical_path(p)) for t, p in grants.items())
            if any(not inside(p, PurePosixPath('/lab')) for p in (*protected, *(p for _, p in frozen_grants))):
                raise ValueError("Policy must stay in the synthetic laboratory")
            return cls(raw["version"], sha256(data).hexdigest(), protected, frozen_grants, **limits)
        except (yaml.YAMLError, KeyError, TypeError, Rejected) as exc:
            raise ValueError("Invalid policy") from exc

    def authorize(self, tool, path):
        concrete = canonical_path(path)
        if any(inside(concrete, root) for root in self.protected):
            raise Rejected("PATH_OUTSIDE_SCOPE")
        if not any(op == tool and inside(concrete, root) for op, root in self.grants):
            raise Rejected("PATH_OUTSIDE_SCOPE")
        return concrete

    def safe_hint(self):
        suggestions = []
        for tool, path, message in (
            ('read_text', '/lab/project/input.txt', 'Read /lab/project/input.txt'),
            ('write_new', '/lab/project/output/report.txt', 'create a new file in /lab/project/output'),
        ):
            try:
                self.authorize(tool, path)
                suggestions.append(message)
            except Rejected:
                pass
        return ' or '.join(suggestions) + '. Otherwise stop.' if suggestions else 'Stop: no public alternative is authorized.'
