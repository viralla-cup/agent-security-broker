"""Inspect audit-only JSONL or the audit projection of an existing replay trace."""

import argparse
import json
import sys

from .reader import AuditFormatError, read_events


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only security audit inspection. No tool calls are executed.')
    parser.add_argument('path', help='Audit JSONL or legacy replay trace JSONL')
    parser.add_argument('--condition', choices=['B0', 'B2', 'B2a'])
    parser.add_argument('--decision', choices=['ALLOW', 'DENY', 'ERROR'])
    parser.add_argument('--execution', choices=['NOT_STARTED', 'SUCCEEDED', 'FAILED', 'REJECTED'])
    parser.add_argument('--jsonl', action='store_true', help='Print only validated audit fields as JSONL')
    args = parser.parse_args(argv)
    try:
        for event in read_events(args.path):
            if args.condition and event['condition'] != args.condition:
                continue
            if args.decision and event['decision'] != args.decision:
                continue
            if args.execution and event['execution_status'] != args.execution:
                continue
            if args.jsonl:
                print(json.dumps(event, ensure_ascii=True))
            else:
                timestamp = event['timestamp'] or 'TIME_NOT_RECORDED'
                operation = event['operation'] or 'UNVALIDATED_OPERATION'
                request = event['request_id'] or 'UNVALIDATED_REQUEST'
                print(f"{timestamp} | {event['condition']} | {operation} | {event['decision']} -> {event['execution_status']}")
                print(f"  Event: {event['event_id']} | Request: {request} | Task: {event['task_id']}")
                print(f"  Policy: {event['policy_version']} | SHA256: {event['policy_sha256']}")
                print(f"  Decision: {event['reason_code']} - {event['explanation']}")
                print(f"  Execution: {event['execution_code']} - {event['execution_explanation']}")
    except AuditFormatError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError:
        print('Could not read the audit file.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
