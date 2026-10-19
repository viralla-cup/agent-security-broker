"""Single-threaded Unix socket gate; only this service has the /lab tmpfs."""

import argparse
import json
import os
import socket
import time

from broker.broker import Broker
from broker.filesystem import FileExecutor
from broker.policy import Policy
from broker.schema import MAX_MESSAGE
from .fixtures import prepare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=["B0", "B2", "B2a"], required=True)
    parser.add_argument("--seed", required=True)
    args = parser.parse_args()
    prepare("/lab", args.seed)
    policy = Policy.load("/app/policies/filesystem.yaml")
    executor = FileExecutor()
    broker = Broker(policy, executor, args.condition)
    deadline = time.monotonic() + 300
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind("/channel/broker.sock")
        os.chmod("/channel/broker.sock", 0o666)
        server.listen(2)
        server.settimeout(1)
        print(json.dumps({"ready": True, "policy_sha256": policy.digest}), flush=True)
        try:
            while time.monotonic() < deadline:
                try:
                    conn, _ = server.accept()
                except TimeoutError:
                    continue
                with conn:
                    conn.settimeout(5)
                    # Linux peer credentials bind the fixed agent identity; JSON cannot change it.
                    import struct
                    _, uid, _ = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != 10002:
                        continue
                    with conn.makefile("rwb") as stream:
                        while time.monotonic() < deadline:
                            try:
                                line = stream.readline(MAX_MESSAGE + 1)
                            except (OSError, TimeoutError):
                                break
                            if not line:
                                break
                            if len(line) > MAX_MESSAGE:
                                line = b"null"
                            envelope = broker.handle(line)
                            stream.write(json.dumps(envelope).encode() + b"\n")
                            stream.flush()
                            if broker.calls >= policy.max_tool_calls or broker.denials >= policy.max_denials:
                                break
        finally:
            executor.close()


if __name__ == "__main__":
    main()
