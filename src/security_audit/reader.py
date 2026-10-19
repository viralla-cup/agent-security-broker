"""Allowlisted read-only projection of audit records, including legacy traces."""

from datetime import datetime
import json
from pathlib import Path
import re

from .events import (AuditContext, CONDITIONS, EXPLANATIONS, OPERATIONS,
                     outcome_fields, public_code, public_version)

MAX_LINE = 1_000_000


class AuditFormatError(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate key')
        result[key] = value
    return result


def _match(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _base(record):
    condition = record.get('condition')
    if not isinstance(condition, str) or condition not in CONDITIONS:
        raise ValueError('Condition')
    step, elapsed = record.get('step'), record.get('elapsed_ns')
    if type(step) is not int or step < 1 or type(elapsed) is not int or elapsed < 0:
        raise ValueError('Counters')
    if type(record.get('dispatched')) is not bool:
        raise ValueError('Dispatch')
    if not _match(record.get('policy_sha256'), r'[a-f0-9]{64}'):
        raise ValueError('Policy digest')
    return {'condition': condition, 'step': step, 'elapsed_ns': elapsed,
            'dispatched': record['dispatched'], 'principal': 'lab-agent',
            'policy_version': public_version(record.get('policy_version')),
            'policy_sha256': record['policy_sha256']}


def project_event(record, line_number, legacy_context):
    if not isinstance(record, dict):
        raise ValueError('Record')
    base = _base(record)
    if 'schema_version' not in record:
        # Old traces did not record wall-clock time or an episode identifier.
        status = record.get('status')
        if not isinstance(status, str) or status not in ('ok', 'denied', 'error'):
            raise ValueError('Legacy status')
        if status == 'ok' and not base['dispatched']:
            raise ValueError('Legacy dispatch')
        operation = record.get('tool')
        if operation is not None and (not isinstance(operation, str) or operation not in OPERATIONS):
            operation = None
        request_id = record.get('request_id')
        task_id = record.get('task_id')
        return {**base, 'schema_version': 1, 'timestamp': None,
                'event_id': f'legacy:{line_number}', 'session_id': None,
                'request_id': legacy_context.reference('req', request_id) if isinstance(request_id, str) else None,
                'task_id': legacy_context.reference('task', task_id) if isinstance(task_id, str) else None,
                'operation': operation, 'resource_id': None,
                **outcome_fields(status, record.get('code'), base['dispatched'], base['condition'])}
    if type(record['schema_version']) is not int or record['schema_version'] != 2:
        raise ValueError('Schema version')
    session = record.get('session_id')
    if not _match(session, r'[a-f0-9]{32}') or record.get('event_id') != f"{session}:{base['step']}":
        raise ValueError('Event identity')
    for key, prefix in (('request_id', 'req'), ('task_id', 'task'), ('resource_id', 'res')):
        value = record.get(key)
        if value is None and key != 'task_id':
            continue
        if not _match(value, prefix + r'-[a-f0-9]{24}'):
            raise ValueError('Reference')
    timestamp = record.get('timestamp')
    if not _match(timestamp, r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z'):
        raise ValueError('Timestamp')
    datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    operation = record.get('operation')
    if operation is not None and (not isinstance(operation, str) or operation not in OPERATIONS):
        raise ValueError('Operation')
    decision = record.get('decision')
    execution = record.get('execution_status')
    if (decision, execution, base['dispatched']) not in {
        ('ALLOW', 'SUCCEEDED', True), ('ALLOW', 'FAILED', True), ('ALLOW', 'REJECTED', True),
        ('DENY', 'NOT_STARTED', False), ('ERROR', 'NOT_STARTED', False),
    }:
        raise ValueError('Decision and execution')
    reason = public_code(record.get('reason_code'))
    execution_code = public_code(record.get('execution_code'))
    if decision == 'ALLOW' and reason != ('BASELINE_ALLOWED' if base['condition'] == 'B0' else 'AUTHORIZED'):
        raise ValueError('Allow reason')
    if execution == 'SUCCEEDED' and execution_code != 'OK':
        raise ValueError('Success reason')
    if execution == 'NOT_STARTED' and execution_code != 'NOT_DISPATCHED':
        raise ValueError('Non-dispatch reason')
    return {**base, 'schema_version': 2, 'timestamp': timestamp, 'session_id': session,
            'event_id': record['event_id'], 'request_id': record.get('request_id'),
            'task_id': record['task_id'], 'resource_id': record.get('resource_id'),
            'operation': operation, 'decision': decision, 'reason_code': reason,
            'explanation': EXPLANATIONS[reason], 'execution_status': execution,
            'execution_code': execution_code, 'execution_explanation': EXPLANATIONS[execution_code]}


def read_events(path):
    if Path(str(path) + '.pending').exists():
        raise AuditFormatError('Audit persistence is incomplete; execution effects may already exist.')
    context = AuditContext()
    with open(path, 'rb') as stream:
        number = 0
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            number += 1
            try:
                if len(line) > MAX_LINE or not line.endswith(b'\n'):
                    raise ValueError('Incomplete or oversized record')
                row = json.loads(line, object_pairs_hook=_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Constant')))
                if not isinstance(row, dict):
                    raise ValueError('Record')
                # Never render the request, response, paths, or arbitrary explanation text.
                yield project_event(row.get('audit', row), number, context)
            except (ValueError, TypeError, KeyError, RecursionError) as exc:
                raise AuditFormatError(f'Invalid audit record at line {number}.') from exc
