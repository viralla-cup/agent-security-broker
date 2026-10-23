"""Offline counterexamples against the pre-correction image; no provider transport."""
import sys
sys.path[:0] = ['/app/src', '/app/scripts', '/app/tests']
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import hashlib
import pytest
import test_study_v11 as t
from backends.base import BackendError
from lab.study_journal import timeout_evidence_ok, atomic_json
from lab.study import task_by_id, seed_for, install_fixture
from lab.oracle import snapshot


class Timeout:
    name = 'deterministic-fake'
    model = 'offline-timeout-injection'
    last_call = {'request_sent': True}  # Synthetic marker; no network implementation.
    def next_action(self, *args):
        raise BackendError('BACKEND_TIMEOUT')


def p1(root, collision):
    task = task_by_id('R01')
    def factory(condition, task):
        ep = t.LocalEpisode(root / 'lab', condition, seed_for(task))
        install_fixture(ep.root, task); ep.before = snapshot(ep.root)
        return ep
    def worker(*a, **k):
        result, exchanges, calls, healthy = t.local_worker(*a, **k)
        return result, exchanges, calls, collision != 'worker'
    with pytest.MonkeyPatch.context() as mp:
        original = t.runner.v1.write_json
        def save(path, value):
            if collision == 'service_save' and path.name == 'service-evidence.json':
                raise OSError('offline injected evidence persistence failure')
            return original(path, value)
        mp.setattr(t.runner.v1, 'write_json', save)
        row, _ = t.runner.v1.execute_episode(task, 'B2', Timeout(), root/'public', root/'private',
            episode_factory=factory, worker=worker, credential_check=lambda ep:None,
            collect_service=lambda ep:{}, clock=lambda:0)
    return {'collision':collision, 'stop_reason':row['loop']['stop_reason'],
        'observation_complete':row['observed']['observation_complete'],
        'episode_valid':row['observed']['episode_valid'],
        'service_file_exists':(root/'private/service-evidence.json').exists(),
        'timeout_continuation_accepted':timeout_evidence_ok(row)}


def p2(root):
    j = t.create(root, 'openai'); old = j.head.copy()
    def collision(*a, **k):
        atomic_json(j.directory/'HEAD.json', old, replace=True)
        j.append('request_reserved', segment=1, index=1, number=1, input=1024, output=1024)
    try:
        t.segment(j, execute=collision)
    except Exception as exc:
        error = type(exc).__name__
    loaded = t.reload(j)
    terminal = loaded.state['terminal']
    continued = t.segment(loaded, stop_after=1)
    return {'detected_exception':error, 'terminal_after_reload':terminal,
            'resumed_schedule_index':continued['episodes'][-1]['schedule_index'],
            'api_attempts':continued['real_api_attempts'],
            'transport':'none; synthetic authorization is not author attestation'}


with TemporaryDirectory() as temp:
    root = Path(temp)
    rows = []
    for case in ('healthy', 'worker', 'service_save'):
        path = root/case; path.mkdir(); rows.append(p1(path, case))
    path=root/'head';path.mkdir()
    result={'kind':'offline_engineering_reproduction', 'actual_provider_calls':0,
            'P1':rows, 'P2':p2(path),
            'source_sha256':{name:hashlib.sha256(Path('/app',name).read_bytes()).hexdigest()
                for name in ('scripts/run_expanded_study.py','scripts/run_expanded_study_v11.py','src/lab/study_journal.py')}}
    assert all(row['timeout_continuation_accepted'] for row in rows)
    assert result['P2']['terminal_after_reload'] is None
    assert result['P2']['resumed_schedule_index']==2
    print(json.dumps(result, indent=2))
