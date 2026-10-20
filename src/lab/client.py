"""JSON transport only; no agent API for shell, Docker, policy, or raw files."""

import json
import os
from pathlib import Path
import socket
import sys

MAX_MESSAGE = 400_000


def exchange(line):
    """Transport one JSON line; shared by replay and the restricted agent loop."""
    if len(line) > MAX_MESSAGE:
        raise ValueError("Message too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(10)
        conn.connect("/channel/broker.sock")
        with conn.makefile("rwb") as stream:
            stream.write(line)
            stream.flush()
            reply = stream.readline(MAX_MESSAGE + 1)
            if not reply or len(reply) > MAX_MESSAGE or not reply.endswith(b"\n"):
                raise RuntimeError("Invalid gate response")
            return reply


def send_action(action):
    return json.loads(exchange(json.dumps(action).encode("utf-8") + b"\n"))


def isolation_report():
    status = Path("/proc/self/status").read_text()
    values = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    return {"uid": os.getuid(), "lab_present": Path("/lab").exists(),
            "docker_socket_present": Path("/var/run/docker.sock").exists(),
            "audit_log_present": Path("/tmp/security-audit.jsonl").exists(),
            "policy_writable": os.access("/app/policies/filesystem.yaml", os.W_OK),
            "effective_capabilities": values["CapEff"].strip(),
            "no_new_privileges": values["NoNewPrivs"].strip(),
            "seccomp": values["Seccomp"].strip()}


def main():
    if sys.argv[1:] == ["--isolation"]:
        print(json.dumps(isolation_report()))
        return
    if sys.argv[1:] == ["--probe-rejected-peer"]:
        # Trusted harness probe executed as the broker UID, never an agent action.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect('/channel/broker.sock')
            try:
                conn.sendall(b'{}\n')
                rejected = conn.recv(1) == b''
            except (ConnectionResetError, BrokenPipeError):
                rejected = True
        print(json.dumps({'unauthorized_peer_rejected': rejected}))
        return
    # One connection per proposal allows model inference between bounded requests.
    for line in sys.stdin.buffer:
        sys.stdout.buffer.write(exchange(line))
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
