"""Predeclared Docker fault/stop checks for the paired runner; deterministic doubles only."""

from datetime import datetime, timezone
import json
import uuid

from run_controlled_pair import (ROOT, SEED, SeededFakeBackend, execute_pair, verified_runtime,
                                 check_credential_isolation, write_json)
from backends.base import BackendError


class StopBackend(SeededFakeBackend):
    def next_action(self, history, schema):
        return {"stop": "no_safe_continuation"}


class TimeoutBackend(SeededFakeBackend):
    def next_action(self, history, schema):
        raise BackendError("BACKEND_TIMEOUT")


def main():
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out = ROOT / "results" / ("paired-docker-checks-" + tag)
    raw = ROOT / ".local" / "controlled-pair-checks" / tag
    out.mkdir(exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    write_json(out / "metadata.json", {**verified_runtime(), "kind": "offline_controlled_pair_fault_checks",
                                      "paid_api_calls": 0, "cases": ["valid_stop", "backend_timeout", "invalid_setup"]})
    checks = {}
    for case in ("valid_stop", "backend_timeout", "invalid_setup"):
        case_out, case_raw = out / case, raw / case
        case_out.mkdir(); case_raw.mkdir()
        created = []

        def factory():
            created.append(1)
            if case == "backend_timeout": return TimeoutBackend()
            if case == "valid_stop" and len(created) == 1: return StopBackend()
            return SeededFakeBackend()

        def credential_check(ep):
            check_credential_isolation(ep)
            if case == "invalid_setup":
                original = ep.send
                def inconsistent(request):
                    result = original(request)
                    # Deliberate observer-association corruption, not a policy change.
                    ep.receipts[0]["request_sha256"] = "0" * 64
                    return result
                ep.send = inconsistent

        summary = execute_pair(case_out, case_raw, factory, credential_check=credential_check)
        a = summary["condition_outcomes"]["B2"]
        assert summary["real_api_attempts"] == summary["actual_llm_episodes"] == 0
        if case == "valid_stop":
            assert summary["pair_valid"] and not a["task_completed"] and a["episode_valid"]
            assert summary["condition_outcomes"]["B2a"]["safe_completion_after_denial"]
        else:
            assert not summary["pair_valid"] and summary["conditions_executed"] == ["B2"]
            assert a["outcome_class"] == ("invalid_setup" if case == "invalid_setup" else "infrastructure_failure")
            if case == "invalid_setup":
                row = json.loads((case_out / "B2/episode.json").read_text())
                assert row["observed_model_calls"] == 0
        checks[case] = True
        print(case + ": PASS", flush=True)
    write_json(out / "summary.json", {"checks": checks, "paid_api_calls": 0})
    print("Evidence:", out)


if __name__ == "__main__":
    main()
