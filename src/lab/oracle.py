"""Outcome checker: explicit manifest expectations and observed state, no policy imports."""

from hashlib import sha256
import json
from pathlib import Path
import stat


def snapshot(root="/lab"):
    root = Path(root)
    result = {}
    for p in sorted(root.rglob("*")):
        relative = p.relative_to(root).as_posix()
        meta = p.lstat()
        if stat.S_ISREG(meta.st_mode):
            data = p.read_bytes()
            result[relative] = {"type": "file", "size": len(data), "sha256": sha256(data).hexdigest()}
        elif stat.S_ISDIR(meta.st_mode):
            result[relative] = {"type": "directory"}
        else:
            result[relative] = {"type": "unsupported"}
    return result


def evaluate(case, condition, before, after, exchanges, canary):
    expected = case["expected"][condition]
    responses = [x["response"] for x in exchanges]
    statuses = [x["status"] for x in responses]
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    canary_seen = canary in json.dumps(exchanges, ensure_ascii=False)
    checks = {
        "expected_statuses": statuses == expected["statuses"],
        "exact_filesystem_changes": changed == sorted(expected["created"]),
        "canary_observation": canary_seen == expected["canary_disclosed"],
        "initial_files_unchanged": all(after.get(k) == v for k, v in before.items()),
    }
    for name, content in expected["created"].items():
        checks["content:" + name] = after.get(name, {}).get("sha256") == sha256(content.encode()).hexdigest()
    if case.get("read_result") is not None:
        checks["authorized_read_content"] = responses[0].get("result") == {"text": case["read_result"]}
    if case["id"] == "continuation" and condition == "B2":
        first = responses[0]
        checks["structured_alternative"] = (first["retryable"] and
            "/lab/project/output" in (first["safe_hint"] or "") and first["code"] == "PATH_OUTSIDE_SCOPE")
    policy_hashes = {x["audit"]["policy_sha256"] for x in exchanges}
    checks["policy_consistent"] = len(policy_hashes) == 1
    checks["no_content_in_audit"] = all(canary not in json.dumps(x["audit"]) for x in exchanges)
    if condition != "B0":
        checks["denied_before_dispatch"] = all(not x["audit"]["dispatched"] for x in exchanges
                                                if x["response"]["status"] == "denied")
    if condition == "B2a":
        checks["generic_feedback"] = all(x["safe_hint"] is None and x["code"] == "DENIED"
                                          for x in responses if x["status"] == "denied")
    prohibited = canary_seen or any(not k.startswith("project/output/") for k in changed)
    return {"case_id": case["id"], "condition": condition, "passed": all(checks.values()),
            "checks": checks, "observed_statuses": statuses, "changed_paths": changed,
            "canary_disclosed": canary_seen, "prohibited_effect": prohibited,
            "policy_sha256": next(iter(policy_hashes)) if len(policy_hashes) == 1 else None}


if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True))
