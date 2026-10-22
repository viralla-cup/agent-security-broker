"""Fixed B2 then B2a controlled-denial pilot. No retries or favorable-outcome selection."""

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid

from run_replay import ROOT, IMAGE, COMMON, Episode, command, docker, source_manifest, write_json
from run_agent_pilot import check_credential_isolation, run_worker
from backends.fake import SeededFakeBackend
from backends.openai import OpenAIBackend
from lab.controlled_recovery import KIND, SEED, MODEL, TASK, LIMITS, API_BUDGET, accept_setup
from lab.pilot_evidence import export_episode, summarize_episodes
from lab.pilot_observation import SETUP_PROPOSAL


def execution_plan(backend):
    return {
        "report_phase": "pre_run", "pre_run_network_calls_made": 0, "pilot_kind": KIND,
        "backend": backend, "conditions": ["B2", "B2a"], "episodes": 2,
        "model": MODEL if backend == "openai" else SeededFakeBackend.model,
        "proposed_real_model": MODEL, "reasoning_effort": "none", "service_tier": "default",
        "prompt_cache_options": {"ttl": "30m"}, "limits_per_episode": asdict(LIMITS),
        "setup_consumes": {"steps": 1, "denials": 1, "model_calls": 0},
        "api_budget_per_episode": asdict(API_BUDGET), "max_output_tokens_per_request": 1024,
        "api_timeout_seconds": 20, "max_api_requests": 12 if backend == "openai" else 0,
        "max_input_tokens_reserved_pair": 98304 if backend == "openai" else 0,
        "max_output_tokens_reserved_pair": 12288 if backend == "openai" else 0,
        "deadline_origin": "setup_start_per_episode", "max_episode_seconds_pair": 240,
        "input_estimation": "serialized_payload_bytes_plus_1024", "monetary_cap_guaranteed": False,
        "cost_assumptions": {"checked_date": "2026-10-22", "currency": "USD",
            "standard_input_per_million": 0.10, "conservative_30m_cache_write_input_per_million": 0.125,
            "output_per_million": 0.50, "estimated_pair_ceiling_excluding_taxes": 0.018432,
            "source": "https://developers.openai.com/api/docs/pricing"},
        "public_output": "results/controlled-pair-<unique-id>/{B2,B2a}/",
        "private_output": ".local/controlled-pair/<unique-id>/{B2,B2a}/",
        "paid_approval_required": True,
    }


def service_evidence(episode):
    """Best-effort private recovery of even unassociated or partially persisted events."""
    probe = ("import json;from pathlib import Path;"
             "names=['/tmp/security-audit.jsonl','/tmp/pilot-operation-receipts.jsonl'];"
             "print(json.dumps({n:{'text':Path(n).read_text() if Path(n).exists() else None,"
             "'pending':Path(n+'.pending').exists()} for n in names}))")
    return json.loads(docker("exec", episode.broker, "python", "-c", probe))


def execute_pair(out, raw_dir, backend_factory, *, episode_factory=Episode, worker=run_worker,
                 credential_check=check_credential_isolation, collect_service=service_evidence,
                 clock=time.monotonic):
    """One attempt per condition. Dependencies are injectable only for offline tests."""
    rows, baselines = [], []
    for condition in ("B2", "B2a"):
        public_dir, private_dir = out / condition, raw_dir / condition
        public_dir.mkdir(exist_ok=False)
        private_dir.mkdir(exist_ok=False)
        backend = SimpleNamespace(name="backend-unavailable", model="unavailable")
        state = {"exchanges": [], "calls": []}
        setup_valid, healthy, complete = None, False, False
        gate, after = {"valid": False, "checks": {}}, {}
        loop = {"stop_reason": "INFRASTRUCTURE_ERROR", "steps": 0, "denials": 0, "model_calls": 0, "retries": 0}
        # A failed container initialization still gets its own explicit failure record.
        episode = SimpleNamespace(seed=SEED, before={}, isolation={}, receipts=[], harness_requests=[])
        checkpoint_number = 0

        def checkpoint():
            nonlocal checkpoint_number
            checkpoint_number += 1
            write_json(private_dir / f"checkpoint-{checkpoint_number:03d}.json", {
                "pilot_kind": KIND, "condition": condition, "setup": gate,
                "before": episode.before, "exchanges": state["exchanges"], "model_calls": state["calls"],
                "operation_receipts": episode.receipts, "harness_requests": episode.harness_requests,
                "seed_transfer": getattr(episode, "seed_transfer", None),
            })

        try:
            backend = backend_factory()
            with episode_factory(condition, SEED) as episode:
                episode.harness_requests = []
                setup_valid = False
                try:
                    credential_check(episode)
                    baseline = (deepcopy(episode.before), deepcopy(episode.isolation))
                    if baselines and baseline != baselines[0]:
                        raise ValueError("Pair fixture or containment mismatch")
                    baselines.append(baseline)
                    started = clock()
                    deadline = started + LIMITS.max_seconds
                    request = {"request_id": "setup-" + uuid.uuid4().hex, "task_id": "mvp-task",
                               **deepcopy(SETUP_PROPOSAL)}
                    write_json(private_dir / "setup-intent.json", {
                        "pilot_kind": KIND, "request": request, "origin": "harness_setup",
                        "started_monotonic": started, "deadline_monotonic": deadline})
                    exchange = {"request": request, **episode.send(request)}
                    state["exchanges"].append(exchange)
                    episode.harness_requests.append({"event_id": exchange["audit"]["event_id"], "request": request})
                    loop.update(steps=1, denials=int(exchange["audit"]["decision"] == "DENY"))
                    after = episode.snapshot()
                    gate = accept_setup(episode, exchange, request, after, backend, deadline, clock())
                    episode.verify_observation_complete()
                    checkpoint()
                    setup_valid = gate["valid"]
                    if setup_valid:
                        loop, _, _, healthy = worker(
                            episode, backend, TASK, LIMITS, seeded_exchange=exchange, episode_deadline=deadline,
                            exchanges=state["exchanges"], calls=state["calls"], checkpoint=checkpoint)
                        # No inference was possible before the setup/handshake deadline.
                        if not state["calls"] and loop["stop_reason"] == "TIME_LIMIT":
                            setup_valid = False
                            gate["valid"] = False
                            gate["checks"]["worker_ready_within_deadline"] = False
                    else:
                        loop["stop_reason"] = "INVALID_SETUP"
                except Exception:
                    # Never export provider payloads, credentials or model text as error messages.
                    loop["stop_reason"] = "INFRASTRUCTURE_ERROR" if setup_valid else "INVALID_SETUP"
                    healthy = False
                finally:
                    try:
                        after = episode.snapshot()
                        episode.verify_observation_complete()
                        complete = True
                    except Exception:
                        healthy = False
                    try:
                        write_json(private_dir / "service-evidence.json", collect_service(episode))
                    except Exception:
                        write_json(private_dir / "service-collection-failure.json", {"code": "PRIVATE_COLLECTION_FAILED"})
                        healthy = False
                    checkpoint()
        except Exception:
            # Includes provisioning/teardown failure. Partial checkpoints remain intact.
            healthy = False
        public, raw = export_episode(TASK, condition, backend, LIMITS, episode, loop,
                                      state["exchanges"], state["calls"], healthy and complete, after,
                                      setup_valid=setup_valid, observation_complete=complete)
        public["setup_checks"] = gate
        public["observation_log_complete"] = complete
        raw["setup_checks"] = gate
        write_json(private_dir / "episode.json", raw)
        write_json(public_dir / "episode.json", public)
        rows.append(public)
        if not public["observed"]["pair_may_continue"]:
            break
    valid = len(rows) == 2 and all(r["observed"]["episode_valid"] for r in rows)
    summary = summarize_episodes(rows, fake_engineering_pass=None,
                                paired_initial_states_and_containment_equal=len(baselines) == 2 and baselines[0] == baselines[1])
    summary.update(pilot_kind=KIND, pair_valid=valid, fixed_order=["B2", "B2a"],
                   conditions_executed=[r["condition"] for r in rows],
                   conditions_not_started=[c for c in ("B2", "B2a") if c not in [r["condition"] for r in rows]],
                   condition_outcomes={r["condition"]: r["observed"] for r in rows})
    write_json(out / "summary.json", summary)
    return summary


def verified_runtime():
    sources = source_manifest()
    copied = {p: h for p, h in sources.items() if p not in ("Dockerfile", ".dockerignore")}
    probe = ("import sys,json,hashlib;from pathlib import Path;"
             "print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in json.load(sys.stdin)}))")
    observed = json.loads(command(["docker", "run", "--rm", "-i", *COMMON, IMAGE, "python", "-c", probe],
                                  input=json.dumps(list(copied))).stdout)
    if observed != copied:
        raise ValueError("Rebuild the Docker image: source mismatch")
    return {"source_sha256": sources, "image_id": docker("image", "inspect", IMAGE, "--format", "{{.Id}}"),
            "docker_server": docker("version", "--format", "{{.Server.Version}}"),
            "copied_source_files_verified": len(copied)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fixed controlled-denial B2/B2a pair; explicit paid approval required.")
    parser.add_argument("--backend", choices=("fake", "openai"), default="fake")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--allow-paid-api", action="store_true")
    args = parser.parse_args(argv)
    plan = execution_plan(args.backend)
    if args.plan:
        print(json.dumps(plan, indent=2))
        return
    if args.backend == "openai" and (not args.allow_paid_api or not os.environ.get("OPENAI_API_KEY")):
        parser.error("Author approval, --allow-paid-api and host OPENAI_API_KEY are required")
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out, raw_dir = ROOT / "results" / ("controlled-pair-" + tag), ROOT / ".local" / "controlled-pair" / tag
    out.mkdir(exist_ok=False)
    raw_dir.mkdir(parents=True, exist_ok=False)
    write_json(out / "plan.json", plan)
    try:
        write_json(out / "metadata.json", {**verified_runtime(),
            "git_base_commit": command(["git", "rev-parse", "HEAD"]).stdout.strip(),
            "git_dirty": bool(command(["git", "status", "--porcelain"]).stdout),
            "proposal_sha256": hashlib.sha256((ROOT / "docs/controlled-recovery-proposal.md").read_bytes()).hexdigest(),
            "task_prompt_sha256": hashlib.sha256(TASK["prompt"].encode()).hexdigest()})
        factory = SeededFakeBackend if args.backend == "fake" else lambda: OpenAIBackend(
            MODEL, os.environ["OPENAI_API_KEY"], budget=API_BUDGET, max_output_tokens=1024,
            timeout=20, reasoning_effort="none")
        summary = execute_pair(out, raw_dir, factory)
        print(json.dumps({"pair_valid": summary["pair_valid"], "conditions": summary["condition_outcomes"],
                          "real_api_attempts": summary["real_api_attempts"]}, indent=2))
        print("Public evidence:", out)
        print("Private evidence:", raw_dir)
        if not summary["pair_valid"]:
            raise SystemExit(1)
    except Exception:
        write_json(out / "failure.json", {"pilot_kind": KIND, "code": "PAIR_INFRASTRUCTURE_ERROR"})
        raise SystemExit("Pair stopped; retained partial evidence. No retry was attempted.") from None


if __name__ == "__main__":
    main()
