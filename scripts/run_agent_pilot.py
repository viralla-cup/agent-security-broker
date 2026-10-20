"""Trusted pilot orchestration. Only fixed commands run; model text stays JSON data."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import Thread
import time
import uuid

from run_replay import ROOT, IMAGE, Episode, command, docker, source_manifest, write_json
from agent_loop import Limits, encoded_size
from backends.base import BackendError, TOOL_SCHEMA
from backends.fake import FakeBackend
from backends.openai import OpenAIBackend
from broker.schema import parse_json
from lab.agent_worker import MAX_FRAME
from lab.pilot_evidence import export_episode


def run_worker(episode, backend, task, limits):
    """Relay inference only; detailed audit and snapshots never enter model history."""
    frames = Queue(maxsize=1)
    process = subprocess.Popen(
        ["docker", "exec", "-i", episode.client, "python", "-m", "lab.agent_worker"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    exchanges, calls = [], []
    deadline = time.monotonic() + limits.max_seconds + 30
    result = {"stop_reason": "INFRASTRUCTURE_ERROR"}
    healthy = False

    def read_frames():
        while True:
            line = process.stdout.readline(MAX_FRAME + 1)
            frames.put(line)
            if not line or len(line) > MAX_FRAME:
                break

    reader = Thread(target=read_frames, daemon=True)
    reader.start()

    def send(value):
        encoded = json.dumps(value, ensure_ascii=True).encode() + b"\n"
        if len(encoded) > MAX_FRAME:
            raise ValueError("Relay size limit")
        process.stdin.write(encoded)
        process.stdin.flush()

    try:
        send({"task": task["prompt"], "limits": asdict(limits)})
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            line = frames.get(timeout=remaining)
            if not line or len(line) > MAX_FRAME or not line.endswith(b"\n"):
                raise ValueError("Incomplete relay frame")
            frame = parse_json(line)
            if frame["kind"] == "model":
                if len(calls) >= limits.max_model_calls or frame["tool_schema"] != TOOL_SCHEMA:
                    raise ValueError("Relay call limit or schema mismatch")
                if encoded_size(frame["history"]) > limits.max_history_bytes:
                    raise ValueError("Relay history limit")
                call = {"number": len(calls) + 1}
                calls.append(call)
                try:
                    proposal = backend.next_action(frame["history"], TOOL_SCHEMA)
                    if encoded_size(proposal) > limits.max_proposal_bytes:
                        raise BackendError("BACKEND_RESPONSE_LIMIT")
                    call.update(outcome="PROPOSAL", proposal=proposal)
                    send({"proposal": proposal})
                except BackendError as exc:
                    call.update(outcome=exc.code)
                    send({"error": exc.code})
                finally:
                    call["metadata"] = backend.last_call
            elif frame["kind"] == "tool":
                if len(exchanges) >= limits.max_steps:
                    raise ValueError("Relay step limit")
                event = episode.collect_audit()
                exchanges.append({"request": frame["request"], "response": frame["response"], "audit": event})
            elif frame["kind"] == "done":
                result = frame["outcome"]
                process.stdin.close()
                healthy = process.wait(timeout=10) == 0
                break
            else:
                raise ValueError("Unexpected relay frame")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, Empty, subprocess.SubprocessError):
        # Error messages can contain untrusted response text. Export a fixed reason only.
        result = {"stop_reason": "INFRASTRUCTURE_ERROR"}
    finally:
        if not healthy:
            # Stop the isolated planner before observing final state; never retry uncertain calls.
            command(["docker", "rm", "-f", episode.client], check=False)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        if not process.stdin.closed:
            process.stdin.close()
        reader.join(timeout=1)
        process.stdout.close()
    return result, exchanges, calls, healthy


def main():
    parser = argparse.ArgumentParser(description="Restricted experimental agent pilot, not a product adapter.")
    parser.add_argument("--backend", choices=["fake", "openai"], default="fake")
    parser.add_argument("--condition", choices=["B0", "B2", "B2a", "all"], default="B2")
    parser.add_argument("--task", choices=["clean", "recovery", "all"], default="clean")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL"))
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--allow-paid-api", action="store_true", help="Use only after explicit author approval of model/data/budget")
    parser.add_argument("--plan", action="store_true", help="Show bounds and configuration presence without any API call or Docker run")
    args = parser.parse_args()
    limits = Limits()
    manifest_path = ROOT / "experiments/manifests/pilot.json"
    manifest = json.loads(manifest_path.read_text())
    tasks = [t for t in manifest["tasks"] if args.task in ("all", t["id"])]
    conditions = ["B0", "B2", "B2a"] if args.condition == "all" else [args.condition]
    episodes = len(tasks) * len(conditions)
    # Validate public model labels before printing them; no credential value is printed.
    if args.backend == "openai":
        import re
        if args.model is not None and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", args.model):
            parser.error("Invalid model identifier")
        if not 256 <= args.max_output_tokens <= 4096:
            parser.error("Output token budget must be between 256 and 4096")
    plan = {"backend": args.backend, "model": args.model if args.backend == "openai" else FakeBackend.model,
            "episodes": episodes, "max_model_calls": episodes * limits.max_model_calls,
            "max_output_tokens_total": episodes * limits.max_model_calls * args.max_output_tokens if args.backend == "openai" else 0,
            "max_history_bytes_per_call": limits.max_history_bytes, "limits": asdict(limits),
            "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
            "paid_api_authorized_by_flag": args.allow_paid_api, "network_calls_made": 0}
    if args.plan:
        print(json.dumps(plan, indent=2))
        return
    if args.backend == "openai":
        if not args.allow_paid_api:
            parser.error("Paid API use requires explicit author approval and --allow-paid-api")
        if not args.model or not os.environ.get("OPENAI_API_KEY"):
            parser.error("Set OPENAI_MODEL and OPENAI_API_KEY in the trusted host environment")
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out = ROOT / "results" / ("pilot-" + tag)
    raw_dir = ROOT / ".local" / "pilot" / tag
    out.mkdir(exist_ok=False)
    raw_dir.mkdir(parents=True, exist_ok=False)
    write_json(out / "metadata.json", {
        "git_base_commit": command(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "git_dirty": bool(command(["git", "status", "--porcelain"]).stdout),
        "source_sha256": source_manifest(), "image_id": docker("image", "inspect", IMAGE, "--format", "{{.Id}}"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "plan": plan, "runtime": {"host_python": sys.version.split()[0], "adapter": "stdlib-urllib-responses-v1"},
    })
    rows = []
    paired = {}
    try:
        for task in tasks:
            for condition in conditions:
                backend = FakeBackend() if args.backend == "fake" else OpenAIBackend(
                    args.model, os.environ["OPENAI_API_KEY"], max_output_tokens=args.max_output_tokens)
                with Episode(condition, "pilot-v1-" + task["id"]) as episode:
                    baseline = (episode.before, episode.isolation)
                    if task["id"] in paired and paired[task["id"]] != baseline:
                        raise ValueError("Paired initial state or containment mismatch")
                    paired[task["id"]] = baseline
                    loop, exchanges, calls, healthy = run_worker(episode, backend, task, limits)
                    after = episode.snapshot()
                    public, raw = export_episode(task, condition, backend, limits, episode, loop, exchanges, calls, healthy, after)
                    name = task["id"] + "-" + condition
                    write_json(raw_dir / (name + ".json"), raw)
                    write_json(out / (name + ".json"), public)
                    with (out / "audit.jsonl").open("a", encoding="utf-8") as stream:
                        for exchange in exchanges:
                            stream.write(json.dumps(exchange["audit"]) + "\n")
                    rows.append(public)
                    print(f"{name}: stop={loop['stop_reason']}, completed={public['observed']['task_completed']}, safe={public['observed']['safe_task_completed']}")
        # Fixed fake fixtures have specified engineering outcomes. Real outcomes are never tuned to match.
        engineering_pass = None
        if args.backend == "fake":
            engineering_pass = all(
                r["observed"]["infrastructure_ok"] and r["observed"]["task_completed"]
                and r["observed"]["prohibited_effect"] == (r["task"] == "recovery" and r["condition"] == "B0")
                and (r["task"] != "recovery" or r["condition"] == "B0" or r["observed"]["safe_completion_after_denial"])
                for r in rows)
        summary = {"episodes": len(rows), "actual_llm_episodes": sum(r["actual_llm_episodes"] for r in rows),
                   "fake_engineering_pass": engineering_pass,
                   "paired_initial_states_and_containment_equal": True if len(conditions) > 1 else None,
                   "claims": "No feedback-benefit or portability claim; fake continuation is scripted engineering evidence."}
        write_json(out / "summary.json", summary)
        print("Evidence:", out)
        if engineering_pass is False or any(not r["observed"]["infrastructure_ok"] for r in rows):
            raise SystemExit(1)
    except Exception:
        write_json(out / "failure.json", {"code": "PILOT_INFRASTRUCTURE_ERROR", "completed_episodes": len(rows)})
        raise SystemExit("Pilot infrastructure failed; partial effects may exist. Private details omitted.") from None


if __name__ == "__main__":
    main()
