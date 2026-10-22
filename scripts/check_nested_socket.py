"""Offline regression through the production Docker server and UID-10002 socket client."""

from datetime import datetime, timezone
import json
import uuid

from run_replay import ROOT, IMAGE, Episode, command, docker, source_manifest, write_json
from lab.fixtures import INPUT


def main():
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out = ROOT / "results" / ("socket-checks-" + tag)
    out.mkdir(exist_ok=False)
    write_json(out / "metadata.json", {
        "kind": "offline_production_socket_regression", "source_sha256": source_manifest(),
        "image_id": docker("image", "inspect", IMAGE, "--format", "{{.Id}}"),
        "git_base_commit": command(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "json_nesting_levels": 10000, "payload_bytes_including_newline": 20002,
        "paid_api_calls": 0,
    })
    try:
        for condition in ("B0", "B2", "B2a"):
            with Episode(condition, "nested-socket-regression") as episode:
                result = command(["docker", "exec", "-i", episode.client, "python", "-m", "lab.client"],
                                 input="[" * 10000 + "0" + "]" * 10000 + "\n")
                response = json.loads(result.stdout)
                event = episode.collect_audit()
                episode.collect_receipt(event)
                assert response["status"] == "denied" and response["result"] is None
                assert response["code"] == ("DENIED" if condition == "B2a" else "INVALID_SCHEMA")
                assert response["request_id"] is None and response["retryable"]
                assert event["reason_code"] == "INVALID_SCHEMA" and event["decision"] == "DENY"
                assert event["evaluation_status"] == "COMPLETED" and not event["dispatched"]
                assert event["execution_status"] == "NOT_STARTED" and event["step"] == 1
                subsequent = episode.send({"request_id": "after-nesting", "task_id": "mvp-task",
                                           "tool": "read_text", "arguments": {"path": "/lab/project/input.txt"}})
                assert subsequent["response"]["status"] == "ok" and subsequent["response"]["result"] == {"text": INPUT}
                assert subsequent["audit"]["decision"] == "ALLOW" and subsequent["audit"]["execution_status"] == "SUCCEEDED"
                assert subsequent["audit"]["step"] == 2
                assert docker("inspect", episode.broker, "--format", "{{.State.Running}}") == "true"
                assert episode.snapshot() == episode.before
                episode.verify_observation_complete()
                write_json(out / (condition + ".json"), {
                    "condition": condition, "passed": True, "socket_response_received": True,
                    "core_rejection_preserved": True, "subsequent_valid_read_succeeded": True,
                    "broker_still_running": True, "filesystem_unchanged": True,
                    "private_receipts": len(episode.receipts), "isolation": episode.isolation,
                    "audit": [event, subsequent["audit"]],
                })
            print(condition + ": PASS (deep rejection and subsequent valid read)")
        write_json(out / "summary.json", {"passed": 3, "conditions": ["B0", "B2", "B2a"], "paid_api_calls": 0})
        print("Evidence:", out)
    except Exception:
        write_json(out / "failure.json", {"code": "SOCKET_REGRESSION_FAILED"})
        raise


if __name__ == "__main__":
    main()
