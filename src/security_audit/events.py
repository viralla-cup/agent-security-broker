"""Audit semantics and safe explanations, independent of authorization logic."""

from datetime import datetime, timezone
import hashlib
import hmac
import re
import secrets
import uuid

SCHEMA_VERSION = 3
OPERATIONS = {'read_text', 'write_new'}
CONDITIONS = {'B0', 'B2', 'B2a'}
EXPLANATIONS = {
    'AUTHORIZED': 'The request passed the broker checks for this task.',
    'BASELINE_ALLOWED': 'Shared laboratory checks passed; internal resource policy is disabled in B0.',
    'INVALID_SCHEMA': 'The request does not satisfy the supported action schema.',
    'UNKNOWN_TOOL': 'The requested operation is not registered.',
    'TASK_MISMATCH': 'The request does not match the task assigned by the trusted runner.',
    'DUPLICATE_REQUEST': 'This request identifier has already been used in the episode.',
    'INVALID_PATH': 'The resource name uses an unsupported path representation.',
    'PATH_OUTSIDE_SCOPE': 'A protected-resource restriction or missing task grant blocks this operation.',
    'LAB_BOUNDARY': 'The request would leave the disposable laboratory boundary.',
    'WRITE_LIMIT': 'A per-write or cumulative write budget would be exceeded.',
    'EPISODE_LIMIT': 'The episode has reached its call or denial limit.',
    'READ_LIMIT': 'The executor rejected the read because its byte limit was exceeded.',
    'UNSUPPORTED_OBJECT': 'The executor rejected an unsupported filesystem object.',
    'EXECUTION_ERROR': 'The executor reported an I/O, encoding, or value error. Partial effects may exist.',
    'EVALUATION_ERROR': 'Broker evaluation failed before executor dispatch.',
    'OK': 'The executor returned normally. Independent outcome checks are still required.',
    'NOT_DISPATCHED': 'The executor was not called for this request.',
    'UNCLASSIFIED': 'No recognized public reason is available; private details are omitted.',
}


def public_code(value):
    return value if isinstance(value, str) and value in EXPLANATIONS else 'UNCLASSIFIED'


def public_version(value):
    # Policy versions are trusted public labels, never model-provided text.
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', value):
        return value
    return '[redacted]'


def outcome_fields(status, code, dispatched, condition):
    code = public_code(code)
    decision = 'ALLOW' if dispatched else 'DENY'
    evaluation = 'FAILED' if not dispatched and status != 'denied' else 'COMPLETED'
    reason = ('BASELINE_ALLOWED' if condition == 'B0' else 'AUTHORIZED') if dispatched else code
    if evaluation == 'FAILED':
        reason = 'EVALUATION_ERROR'
    execution = ('SUCCEEDED' if status == 'ok' else 'REJECTED' if status == 'denied' else 'FAILED') if dispatched else 'NOT_STARTED'
    execution_code = ('OK' if status == 'ok' else code) if dispatched else 'NOT_DISPATCHED'
    return {'decision': decision, 'evaluation_status': evaluation,
            'reason_code': reason, 'explanation': EXPLANATIONS[reason],
            'execution_status': execution, 'execution_code': execution_code,
            'execution_explanation': EXPLANATIONS[execution_code]}


class AuditContext:
    def __init__(self):
        self.session_id = uuid.uuid4().hex
        self._key = secrets.token_bytes(32)

    def reference(self, kind, value):
        if value is None:
            return None
        data = (kind + '\0' + value).encode('utf-8', errors='replace')
        digest = hmac.new(self._key, data, hashlib.sha256).hexdigest()[:24]
        return kind + '-' + digest

    def event(self, *, action, task_id, policy, condition, step, status, code, dispatched, elapsed_ns):
        return {
            'schema_version': SCHEMA_VERSION,
            'timestamp': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
            'event_id': f'{self.session_id}:{step}', 'session_id': self.session_id,
            'request_id': self.reference('req', action.request_id) if action else None,
            'task_id': self.reference('task', task_id), 'principal': 'lab-agent',
            'operation': action.tool if action else None,
            'resource_id': self.reference('res', action.path) if action else None,
            'condition': condition, 'step': step,
            'policy_version': public_version(policy.version), 'policy_sha256': policy.digest,
            'dispatched': dispatched, 'elapsed_ns': elapsed_ns,
            **outcome_fields(status, code, dispatched, condition),
        }
