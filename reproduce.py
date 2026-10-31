"""Verify the released Main v1.1 results offline without changing evidence."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


CHECKER = Path("publication/main-v1.1-en-v1.0/render_publication.py")
SUCCESS = "PUBLIC_CHECKS_PASSED_NOT_INDEPENDENT_REVIEW"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="check public file integrity and descriptive results; no API or Docker",
    )
    args = parser.parse_args(argv)
    if not args.offline:
        parser.error("choose --offline to verify results, or --help for usage")

    root = Path(__file__).resolve().parent
    checker = root / CHECKER
    if not checker.is_file():
        print(f"FAIL: Required checker is missing: {CHECKER.as_posix()}", file=sys.stderr)
        return 2

    try:
        result = subprocess.run(
            [sys.executable, "-B", "-S", str(checker), "--verify-only"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        print(f"FAIL: Could not start the offline checker: {exc}", file=sys.stderr)
        return 2

    if result.returncode:
        print(f"FAIL: Offline verification failed (exit {result.returncode}).", file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip().splitlines()[-1], file=sys.stderr)
        return result.returncode

    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = None
    if not isinstance(report, dict) or report.get("status") != SUCCESS:
        print("FAIL: The checker did not return the expected verification report.", file=sys.stderr)
        return 1

    sys.stdout.write(result.stdout)
    print("PASS: Offline public checks passed; this is not an independent review.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
