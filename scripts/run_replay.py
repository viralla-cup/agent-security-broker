"""Trusted host harness. Model text is never interpolated into Docker commands."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lab.fixtures import canary_for
from lab.oracle import evaluate

IMAGE = "agent-security-broker:mvp"
COMMON = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt",
          "no-new-privileges=true", "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
          "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m", "--log-driver", "none"]


def command(args, *, input=None, timeout=60, check=True):
    result = subprocess.run(args, input=input, text=True, encoding="utf-8", capture_output=True,
                            cwd=ROOT, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"Command {args[0]} failed ({result.returncode}): {result.stderr[:2000]}")
    return result


def docker(*args, **kwargs):
    return command(["docker", *args], **kwargs).stdout.strip()


def write_json(path, data):
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


class Episode:
    def __init__(self, condition, seed):
        suffix = uuid.uuid4().hex[:12]
        self.broker = "asb-broker-" + suffix
        self.client = "asb-client-" + suffix
        self.volume = "asb-channel-" + suffix
        self.condition, self.seed = condition, seed
        self.audit_count = 0
        self.audit_session = None

    def __enter__(self):
        try:
            docker("volume", "create", "--label", "asb.disposable=true", self.volume)
            docker("run", "-d", "--name", self.broker, *COMMON, "--user", "10001:10001",
                   "--tmpfs", "/lab:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700",
                   "--mount", f"type=volume,src={self.volume},dst=/channel", IMAGE,
                   "python", "-m", "lab.server", "--condition", self.condition, "--seed", self.seed)
            for _ in range(50):
                ready = command(["docker", "exec", self.broker, "python", "-c",
                                 "import pathlib,sys;sys.exit(not pathlib.Path('/channel/broker.sock').exists())"], check=False)
                if ready.returncode == 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Broker readiness timeout")
            # The client has the socket volume only. There is no laboratory mount.
            docker("run", "-d", "-i", "--name", self.client, *COMMON, "--user", "10002:10002",
                   "--mount", f"type=volume,src={self.volume},dst=/channel,readonly", IMAGE,
                   "python", "-m", "lab.client")
            self.isolation = self.check_isolation()
            self.before = self.snapshot()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def check_isolation(self):
        observed = {}
        for role, name in (("broker", self.broker), ("client", self.client)):
            info = json.loads(docker("inspect", name))[0]
            host = info["HostConfig"]
            record = {"user": info["Config"]["User"], "network": host["NetworkMode"],
                      "read_only": host["ReadonlyRootfs"], "privileged": host["Privileged"],
                      "cap_drop": host["CapDrop"], "security_opt": host["SecurityOpt"],
                      "pid_mode": host["PidMode"], "memory": host["Memory"], "pids_limit": host["PidsLimit"],
                      "nano_cpus": host["NanoCpus"], "tmpfs": host["Tmpfs"],
                      "mounts": [{"type": m["Type"], "destination": m["Destination"], "rw": m["RW"]}
                                 for m in info["Mounts"]]}
            assert record["network"] == "none" and record["read_only"] and not record["privileged"]
            assert record["cap_drop"] == ["ALL"] and "no-new-privileges=true" in record["security_opt"]
            assert record["pid_mode"] == "" and record["memory"] == 268435456 and record["pids_limit"] == 64
            assert all(m["type"] == "volume" and m["destination"] == "/channel" for m in record["mounts"])
            assert record["user"] == ("10001:10001" if role == "broker" else "10002:10002")
            observed[role] = record
        probe = json.loads(docker("exec", self.client, "python", "-m", "lab.client", "--isolation"))
        assert probe == {"uid": 10002, "lab_present": False, "docker_socket_present": False,
                         "audit_log_present": False,
                         "policy_writable": False, "effective_capabilities": "0000000000000000",
                         "no_new_privileges": "1", "seccomp": "2"}
        observed["client_probe"] = probe
        peer = json.loads(docker("exec", self.broker, "python", "-m", "lab.client", "--probe-rejected-peer"))
        assert peer == {"unauthorized_peer_rejected": True}
        observed["peer_probe"] = peer
        return observed

    def send(self, action):
        # exec starts the fixed transport, not a model-selected executable.
        response = docker("exec", "-i", self.client, "python", "-m", "lab.client",
                          input=json.dumps(action) + "\n", timeout=20)
        feedback = json.loads(response)
        assert set(feedback) == {'status', 'code', 'result', 'retryable', 'safe_hint', 'request_id'}
        return {'response': feedback, 'audit': self.collect_audit()}

    def collect_audit(self):
        """Observe one completed call; never expose this method to the agent."""
        # This trusted observer channel is never offered to the experimental agent.
        events = [json.loads(line) for line in docker(
            "exec", self.broker, "python", "-m", "security_audit", "/tmp/security-audit.jsonl", "--jsonl"
        ).splitlines()]
        if len(events) != self.audit_count + 1:
            raise RuntimeError('Audit persistence or event sequence failure; effects may already exist')
        event = events[-1]
        if event['step'] != len(events) or (self.audit_session and event['session_id'] != self.audit_session):
            raise RuntimeError('Audit session or step mismatch')
        self.audit_count += 1
        self.audit_session = event['session_id']
        return event

    def snapshot(self):
        return json.loads(docker("exec", self.broker, "python", "-m", "lab.oracle"))

    def __exit__(self, *_):
        for name in (self.client, self.broker):
            command(["docker", "rm", "-f", name], check=False)
        command(["docker", "volume", "rm", self.volume], check=False)


def source_manifest():
    paths = [p for p in ROOT.rglob('*') if p.is_file() and
             p.relative_to(ROOT).parts[0] in ('src', 'tests', 'scripts', 'policies', 'experiments') and
             '__pycache__' not in p.parts and p.suffix in ('.py', '.yaml', '.json')]
    paths += [ROOT / p for p in ('Dockerfile', 'requirements.lock', 'pytest.ini', '.dockerignore')]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
    out = args.output or ROOT / "results" / ("dev-" + run_id)
    out.mkdir(parents=True, exist_ok=False)
    raw_dir = ROOT / ".local" / "runs" / run_id
    raw_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = ROOT / "experiments/manifests/mvp.json"
    manifest = json.loads(manifest_path.read_text())
    metadata = {"run_id": run_id, "kind": manifest["kind"], "split": manifest["split"],
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "git_base_commit": command(["git", "rev-parse", "HEAD"]).stdout.strip(),
                "git_dirty": bool(command(["git", "status", "--porcelain"]).stdout),
                "source_sha256": source_manifest(),
                "docker_server": docker("version", "--format", "{{.Server.Version}}"),
                "image_id": docker("image", "inspect", IMAGE, "--format", "{{.Id}}"),
                "runtime": json.loads(docker("run", "--rm", *COMMON, IMAGE, "python", "-c",
                    "import sys,platform,json,importlib.metadata;print(json.dumps({'python':sys.version,'platform':platform.platform(),'packages':{x:importlib.metadata.version(x) for x in ['PyYAML','pytest','iniconfig','packaging','pluggy']}}))")),
                "actual_llm_episodes": 0}
    write_json(out / 'metadata.json', metadata)
    rows = []
    try:
        for case in manifest['cases']:
            seed = 'mvp-v1-' + case['id']
            for condition in ('B0', 'B2', 'B2a'):
                with Episode(condition, seed) as episode:
                    exchanges = [dict(request=a, **episode.send(a)) for a in case['actions']]
                    after = episode.snapshot()
                    result = evaluate(case, condition, episode.before, after, exchanges, canary_for(seed))
                    record = {"case_id": case['id'], "condition": condition, "kind": manifest['kind'],
                              "before": episode.before, "after": after, "isolation": episode.isolation,
                              "exchanges": exchanges, "outcome": result}
                    name = case['id'] + '-' + condition
                    write_json(raw_dir / (name + '.json'), record)
                    sanitized = json.loads(json.dumps(record).replace(canary_for(seed), '[REDACTED_SYNTHETIC_CANARY]'))
                    write_json(out / (name + '.json'), sanitized)
                    with (out / 'trace.jsonl').open('a', encoding='utf-8') as f:
                        for exchange in sanitized['exchanges']:
                            f.write(json.dumps({"case_id":case['id'], "condition":condition, **exchange}) + '\n')
                    with (out / 'audit.jsonl').open('a', encoding='utf-8') as f:
                        for exchange in exchanges:
                            f.write(json.dumps(exchange['audit']) + '\n')
                    rows.append(result)
                    print(f"{case['id']} {condition}: {'PASS' if result['passed'] else 'FAIL'}", flush=True)
        # Pairing is checked independently from the gate, after all observations exist.
        for case in manifest['cases']:
            paired = [json.loads((out / f"{case['id']}-{c}.json").read_text()) for c in ('B0','B2','B2a')]
            assert paired[0]['before'] == paired[1]['before'] == paired[2]['before']
            assert paired[0]['isolation'] == paired[1]['isolation'] == paired[2]['isolation']
        write_json(out / 'summary.json', {"all_passed": all(r['passed'] for r in rows),
                   "paired_initial_states_and_containment_equal": True, "episodes": rows,
                   "actual_llm_episodes": 0, "claims": "Development replay only; no empirical recovery or portability claim."})
        with (out / 'summary.csv').open('x', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['case_id','condition','passed','canary_disclosed','prohibited_effect'])
            writer.writeheader()
            writer.writerows({k:r[k] for k in writer.fieldnames} for r in rows)
        print('Results:', out)
        if not all(r['passed'] for r in rows):
            raise SystemExit(1)
    except Exception as exc:
        write_json(out / 'failure.json', {"type": type(exc).__name__, "message": str(exc), "completed_episodes":len(rows)})
        raise


if __name__ == '__main__':
    main()
