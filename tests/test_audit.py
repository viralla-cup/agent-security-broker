"""Audit decisions, outcome evidence, privacy, persistence, and read-only viewing."""

from datetime import datetime
import json
import os
from pathlib import Path
import stat

import pytest

from broker.broker import Broker
from broker.filesystem import FileExecutor
from broker.policy import Policy
from broker.schema import Rejected
from lab.fixtures import prepare, canary_for
from lab.server import handle_request
from security_audit.__main__ import main as inspect_main
from security_audit.events import AuditContext
from security_audit.reader import AuditFormatError, read_events
from security_audit.storage import AuditWriter

POLICY = Path(__file__).resolve().parents[1] / 'policies/filesystem.yaml'
SECRET = 'SYNTHETIC_TEST_CREDENTIAL_do_not_log'


def request(path='/lab/project/input.txt', tool='read_text', rid='r1', content='Mean: 4\n'):
    args = {'path': path}
    if tool == 'write_new':
        args['content'] = content
    return json.dumps({'request_id':rid, 'task_id':'mvp-task', 'tool':tool, 'arguments':args})


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path/'lab'
    root.mkdir()
    prepare(root, 'audit-test')
    executor = FileExecutor(root)
    broker = Broker(Policy.load(POLICY), executor)
    yield broker, root
    executor.close()


@pytest.mark.parametrize('condition', ['B0','B2','B2a'])
def test_success_requires_actual_execution(runtime, condition):
    broker, root = runtime
    broker.condition = condition
    envelope = broker.handle(request('/lab/project/output/report.txt', 'write_new'))
    event = envelope['audit']
    assert event['decision'] == 'ALLOW'
    assert event['reason_code'] == ('BASELINE_ALLOWED' if condition == 'B0' else 'AUTHORIZED')
    assert event['dispatched'] and event['execution_status'] == 'SUCCEEDED'
    assert event['execution_code'] == 'OK'
    assert (root/'project/output/report.txt').read_text() == 'Mean: 4\n'
    assert event['policy_sha256'] == broker.policy.digest and event['policy_version'] == broker.policy.version
    assert event['operation'] == 'write_new'
    assert datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).utcoffset().total_seconds() == 0


@pytest.mark.parametrize('condition', ['B2','B2a'])
def test_denied_operation_never_calls_executor(condition):
    class ForbiddenExecutor:
        def execute(self, *args):
            pytest.fail('Denied action reached the executor')
    broker = Broker(Policy.load(POLICY), ForbiddenExecutor(), condition)
    envelope = broker.handle(request('/lab/secrets/' + SECRET))
    event = envelope['audit']
    assert (event['decision'],event['execution_status'],event['dispatched']) == ('DENY','NOT_STARTED',False)
    assert event['reason_code'] == 'PATH_OUTSIDE_SCOPE' and event['execution_code'] == 'NOT_DISPATCHED'
    assert SECRET not in json.dumps(event) and '/lab/' not in json.dumps(event)
    if condition == 'B2a':
        assert envelope['response'] == {'status':'denied','code':'DENIED','result':None,
                                      'retryable':True,'safe_hint':None,'request_id':'r1'}


@pytest.mark.parametrize('condition', ['B0','B2','B2a'])
@pytest.mark.parametrize('scenario', ['missing','existing','encoding'])
def test_allowed_operations_report_execution_failure(runtime, condition, scenario):
    broker, root = runtime
    broker.condition = condition
    if scenario == 'missing':
        message = request('/lab/project/missing.txt')
    elif scenario == 'existing':
        (root/'project/output/report.txt').write_text('Original')
        message = request('/lab/project/output/report.txt','write_new')
    else:
        (root/'project/binary').write_bytes(b'\xff')
        message = request('/lab/project/binary')
    envelope = broker.handle(message)
    event = envelope['audit']
    assert event['decision'] == 'ALLOW' and event['dispatched']
    assert event['execution_status'] == 'FAILED' and event['execution_code'] == 'EXECUTION_ERROR'
    assert envelope['response']['status'] == 'error' and envelope['response']['code'] == 'EXECUTION_ERROR'
    if scenario == 'existing':
        assert (root/'project/output/report.txt').read_text() == 'Original'


@pytest.mark.parametrize('condition', ['B0','B2','B2a'])
def test_executor_rejection_is_not_predispatch_denial(runtime, condition):
    broker, root = runtime
    broker.condition = condition
    (root/'project/large').write_bytes(b'x'*65537)
    envelope = broker.handle(request('/lab/project/large'))
    event = envelope['audit']
    assert (event['decision'],event['execution_status']) == ('ALLOW','REJECTED')
    assert event['dispatched'] and event['execution_code'] == 'READ_LIMIT'
    assert envelope['response']['status'] == 'denied' and broker.denials == 1
    assert envelope['response']['code'] == ('DENIED' if condition == 'B2a' else 'READ_LIMIT')


def test_partial_write_is_a_failure_not_a_success(runtime):
    broker, root = runtime
    class PartialExecutor:
        def execute(self, *args):
            (root/'project/output/partial').write_text('partial')
            raise OSError('/private/' + SECRET)
    broker.executor = PartialExecutor()
    envelope = broker.handle(request('/lab/project/output/partial','write_new'))
    assert (root/'project/output/partial').read_text() == 'partial'
    assert envelope['audit']['decision'] == 'ALLOW' and envelope['audit']['execution_status'] == 'FAILED'
    assert 'Partial effects' in envelope['audit']['execution_explanation']
    assert SECRET not in json.dumps(envelope)


def test_evaluation_failure_is_neither_allow_nor_policy_denial(runtime, monkeypatch):
    broker, _ = runtime
    broker.condition = 'B0'
    def fail_resolution(_):
        raise ValueError(SECRET)
    monkeypatch.setattr('broker.broker.canonical_path', fail_resolution)
    event = broker.handle(request())['audit']
    assert event['decision'] == 'ERROR' and not event['dispatched']
    assert event['reason_code'] == 'EVALUATION_ERROR' and event['execution_status'] == 'NOT_STARTED'
    assert SECRET not in json.dumps(event)


def test_audit_never_copies_payload_or_untrusted_identifiers(runtime):
    broker, _ = runtime
    broker.condition = 'B0'
    event = broker.handle(request('/lab/project/output/' + SECRET, 'write_new', SECRET, SECRET))['audit']
    assert SECRET not in json.dumps(event)
    assert '/lab/' not in json.dumps(event)
    assert event['request_id'].startswith('req-') and event['resource_id'].startswith('res-')
    canary = broker.handle(request('/lab/secrets/canary.txt',rid='read-canary'))
    assert canary_for('audit-test') in json.dumps(canary['response'])
    assert canary_for('audit-test') not in json.dumps(canary['audit'])


def test_unknown_exception_text_is_not_an_audit_reason():
    class UnexpectedRejection:
        def execute(self, *args):
            raise Rejected(SECRET)
    event = Broker(Policy.load(POLICY), UnexpectedRejection()).handle(request())['audit']
    assert event['execution_code'] == 'UNCLASSIFIED' and SECRET not in json.dumps(event)


def test_duplicate_ids_have_distinct_traceable_events(runtime):
    broker, _ = runtime
    first = broker.handle(request())['audit']
    second = broker.handle(request())['audit']
    malformed = broker.handle('{bad') ['audit']
    assert first['request_id'] == second['request_id']
    assert first['task_id'] == second['task_id'] == malformed['task_id']
    assert len({e['event_id'] for e in (first,second,malformed)}) == 3
    for i,event in enumerate((first,second,malformed),1):
        assert event['event_id'] == f"{first['session_id']}:{i}"
    assert malformed['request_id'] is None and malformed['operation'] is None
    assert malformed['reason_code'] == 'INVALID_SCHEMA'
    other = AuditContext()
    assert other.reference('req','r1') != first['request_id']
    assert other.reference('res','/lab/project/input.txt') != first['resource_id']


def test_wrong_task_does_not_overwrite_audit_identity(runtime):
    broker, _ = runtime
    raw = json.loads(request())
    raw['task_id'] = SECRET
    event = broker.handle(json.dumps(raw))['audit']
    assert event['task_id'] == broker.audit.reference('task',broker.task_id)
    assert event['reason_code'] == 'TASK_MISMATCH' and SECRET not in json.dumps(event)


def test_private_log_and_response_only_agent_channel(runtime, tmp_path):
    broker, _ = runtime
    broker.condition = 'B2a'
    path = tmp_path/'audit.jsonl'
    writer = AuditWriter(path)
    try:
        response = handle_request(broker, writer, request('/lab/secrets/canary.txt'))
    finally:
        writer.close()
    assert response == {'status':'denied','code':'DENIED','result':None,'retryable':True,
                        'safe_hint':None,'request_id':'r1'}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    records = list(read_events(path))
    assert len(records) == 1 and records[0]['reason_code'] == 'PATH_OUTSIDE_SCOPE'
    with pytest.raises(FileExistsError):
        AuditWriter(path)


def test_failed_persistence_does_not_change_operation_or_claim_rollback(runtime, tmp_path, monkeypatch, capsys):
    broker, root = runtime
    writer = AuditWriter(tmp_path/'audit.jsonl')
    def fail_fsync(_):
        raise OSError(SECRET)
    monkeypatch.setattr('security_audit.storage.os.fsync',fail_fsync)
    # Read avoids using the executor's write/fsync path in this injected sink failure.
    response = handle_request(broker,writer,request())
    assert response['status'] == 'ok'
    assert writer.failed and not writer.append({})
    writer.close()
    with pytest.raises(AuditFormatError, match='persistence is incomplete'):
        list(read_events(tmp_path/'audit.jsonl'))
    error = capsys.readouterr().err
    assert 'Audit persistence failed' in error and SECRET not in error


def test_partial_audit_write_stops_and_is_detected(runtime, tmp_path, monkeypatch):
    broker, _ = runtime
    path = tmp_path/'audit.jsonl'
    writer = AuditWriter(path)
    actual_write = os.write
    def partial(fd,data):
        actual_write(fd,data[:5])
        raise OSError(SECRET)
    monkeypatch.setattr('security_audit.storage.os.write',partial)
    assert not writer.append(broker.handle(request())['audit'])
    assert not writer.append({})
    writer.close()
    with pytest.raises(AuditFormatError, match='persistence is incomplete'):
        list(read_events(path))


def test_viewer_detects_contradictory_success_without_dispatch(runtime, tmp_path):
    broker, _ = runtime
    event = broker.handle(request())['audit']
    event['dispatched'] = False
    path = tmp_path/'contradiction.jsonl'
    path.write_text(json.dumps(event)+'\n')
    with pytest.raises(AuditFormatError, match='line 1'):
        list(read_events(path))


@pytest.mark.parametrize('jsonl', [False,True])
def test_cli_ignores_raw_content_and_is_read_only(runtime, tmp_path, capsys, jsonl):
    broker, _ = runtime
    event = broker.handle(request('/lab/secrets/canary.txt'))['audit']
    event['explanation'] = SECRET + '\x1b[31m/private/path'
    event['execution_explanation'] = SECRET
    event['extra'] = SECRET
    path = tmp_path/'trace.jsonl'
    path.write_text(json.dumps({'audit':event,'request':{'password':SECRET},'response':SECRET})+'\n')
    before = path.read_bytes()
    args = [str(path),'--decision','DENY'] + (['--jsonl'] if jsonl else [])
    assert inspect_main(args) == 0
    output = capsys.readouterr().out
    assert SECRET not in output and '/private/path' not in output and '\x1b' not in output
    assert 'PATH_OUTSIDE_SCOPE' in output and 'NOT_STARTED' in output
    assert path.read_bytes() == before
    assert inspect_main([str(path),'--execution','FAILED']) == 0
    assert capsys.readouterr().out == ''


def test_legacy_trace_has_no_invented_timestamp(runtime, tmp_path, capsys):
    broker, _ = runtime
    old = {'request_id':SECRET,'task_id':SECRET,'policy_version':broker.policy.version,
           'policy_sha256':broker.policy.digest,'condition':'B2a','step':1,'status':'denied',
           'code':'PATH_OUTSIDE_SCOPE','dispatched':False,'tool':'read_text','elapsed_ns':1}
    path = tmp_path/'legacy.jsonl'
    path.write_text(json.dumps({'audit':old,'request':{'path':'/private/' + SECRET}})+'\n')
    assert inspect_main([str(path)]) == 0
    output = capsys.readouterr().out
    assert 'TIME_NOT_RECORDED' in output and SECRET not in output
    event = list(read_events(path))[0]
    assert event['schema_version'] == 1 and event['session_id'] is None


@pytest.mark.parametrize('line', ['{'+SECRET+'}\n','{}\n','{}','{"audit":{},"audit":{}}\n','[]\n'])
def test_malformed_trace_error_does_not_echo_input(tmp_path, capsys, line):
    path = tmp_path/'bad.jsonl'
    path.write_text(line)
    assert inspect_main([str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == 'Invalid audit record at line 1.\n'


def test_cli_missing_file_error_does_not_echo_path(tmp_path,capsys):
    assert inspect_main([str(tmp_path/SECRET)]) == 2
    assert SECRET not in capsys.readouterr().err
