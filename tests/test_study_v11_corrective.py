"""P1/P2 corrective regressions: injected faults, no experiments or provider I/O."""
import json
from pathlib import Path

import pytest

import test_study_v11 as t
from backends.base import BackendError
from lab.oracle import snapshot
from lab.study import seed_for, install_fixture
from lab.study_journal import JournalError, atomic_json
from study_timeout_helpers import LedgerTimeout, service_copy


class OfflineTimeout:
    name = 'deterministic-fake'
    model = 'offline-timeout-injection'
    last_call = {'request_sent': True}  # Synthetic observation, not actual network I/O.

    def next_action(self, *args):
        raise BackendError('BACKEND_TIMEOUT')


def real_execution(root, collision, monkeypatch):
    original = t.runner.v1.write_json
    def save(path, value):
        if collision == 'service_save' and path.name == 'service-evidence.json':
            raise OSError('injected service save failure')
        if collision == 'checkpoint' and path.name == 'checkpoint-003.json':
            raise OSError('injected final checkpoint failure')
        return original(path, value)
    monkeypatch.setattr(t.runner.v1, 'write_json', save)

    def execute(task, condition, backend, out, raw, **kwargs):
        def factory(condition, task):
            ep = t.LocalEpisode(root/'lab', condition, seed_for(task))
            install_fixture(ep.root, task); ep.before = snapshot(ep.root)
            return ep
        def collect(ep):
            if collision == 'service_collect':
                raise OSError('injected service collection failure')
            return {**service_copy(ep),'synthetic_service':'private evidence must remain private'}
        def worker(*args, **options):
            # Drive the real Agent Loop/Core with a deterministic fault backend.
            result, exchanges, calls, healthy = t.local_worker(*args, **options)
            if collision == 'execution':
                raise RuntimeError('injected execution failure')
            if collision == 'observation':
                args[0].verify_observation_complete = lambda: (_ for _ in ()).throw(ValueError('injected gap'))
            return result, exchanges, calls, collision != 'worker'
        timeout=LedgerTimeout(task).attach(backend.journal,backend.index)
        return t.runner.v1.execute_episode(task, condition, timeout, out, raw,
            episode_factory=factory, worker=worker, collect_service=collect,
            credential_check=lambda ep:None, clock=lambda:0, **kwargs)
    return execute


@pytest.mark.parametrize('collision,allowed', [('healthy',True),('worker',False),
    ('service_save',False),('service_collect',False),('checkpoint',False),
    ('execution',False),('observation',False)])
def test_timeout_collision_uses_independent_health(tmp_path, monkeypatch, collision, allowed):
    j=t.create(tmp_path); first=real_execution(tmp_path,collision,monkeypatch)
    def execute(*args, **kwargs):
        return (first if kwargs['position']['schedule_index']==1 else t.execute_stub)(*args,**kwargs)
    checked=[]
    result=t.runner.run_segment(j,t.runtime(j),execute=execute,stop_after=2,
        input_check=lambda s,t=None:s.verify(t),
        check_environment=lambda *a:checked.append(True) or t.runtime(j))
    row=result['episodes'][0]
    assert len(result['episodes'])==(2 if allowed else 1)
    assert len(checked)==int(allowed)
    assert row['observed']['episode_valid'] is False
    assert j.timeout_isolated(row,1) is allowed
    raw=json.loads((j.private/'R01-r1/B2/episode.json').read_text())
    assert row['operational_health']==raw['operational_health']
    if collision in ('healthy','worker','service_save','service_collect','checkpoint'):
        assert row['loop']['stop_reason']=='BACKEND_TIMEOUT'
        assert row['observed']['observation_complete'] is True
    if collision=='worker':assert row['operational_health']['worker_healthy'] is False
    if collision=='service_save':
        assert row['operational_health']['service_collected'] is True
        assert row['operational_health']['service_saved'] is False
    assert 'synthetic_service' not in json.dumps(result)
    assert 'service_evidence_sha256' not in json.dumps(result)
    assert t.reload(j).summary()['completed_episode_records']==len(result['episodes'])


@pytest.mark.parametrize('damage',['missing_health','private_health','service_missing','service_changed','broker_failure'])
def test_timeout_missing_or_contradictory_evidence_rejected(tmp_path,damage):
    j=t.create(tmp_path); first=t.timeout_execute({1})
    def execute(*a,**kw):
        row,baseline=first(*a,**kw);raw=a[4];out=a[3]
        if damage=='missing_health':row.pop('operational_health')
        elif damage=='broker_failure':row['operational_health']['broker_execution_ok']=False
        elif damage=='private_health':
            saved=json.loads((raw/'episode.json').read_text());saved['operational_health']['worker_healthy']=False
            atomic_json(raw/'episode.json',saved,replace=True)
        elif damage=='service_missing':(raw/'service-evidence.json').unlink()
        else:atomic_json(raw/'service-evidence.json',{'changed':True},replace=True)
        atomic_json(out/'episode.json',row,replace=True)
        return row,baseline
    result=t.segment(j,execute=execute)
    assert len(result['episodes'])==1 and result['stop_reason']=='INVALID_EPISODE'
    assert j.state['last_finish']['timeout_environment_ok'] is False


@pytest.mark.parametrize('backend',['fake','openai'])
@pytest.mark.parametrize('damage',['old_valid_head','missing_head','changed_tail'])
def test_detected_integrity_failure_cannot_be_reopened(tmp_path,backend,damage):
    j=t.create(tmp_path,backend);old=j.head.copy();saved={}
    def execute(*a,**k):
        saved['head']=(j.directory/'HEAD.json').read_bytes()
        tail=j.directory/f"{j.head['sequence']:08d}.json"
        saved['tail_path']=tail;saved['tail']=tail.read_bytes()
        if damage=='old_valid_head':atomic_json(j.directory/'HEAD.json',old,replace=True)
        elif damage=='missing_head':(j.directory/'HEAD.json').unlink()
        else:tail.write_text('{}')
        j.append('request_reserved',segment=1,index=1,number=1,input=1024,output=1024)
        pytest.fail('Must stop before reservation or provider transport')
    with pytest.raises(JournalError):t.segment(j,execute=execute)
    assert j.state['terminal']=='CHECKPOINT_OR_INPUT_FAILURE'
    assert j.blocker.is_dir() and not j.state['requests']
    # Ordinary append is unavailable, but quarantine remains durable.
    with pytest.raises(JournalError):j.append('run_stop',reason='CHECKPOINT_OR_INPUT_FAILURE')
    with pytest.raises(JournalError):t.reload(j)
    # Repairing HEAD/tail alone must never erase the detected violation.
    (j.directory/'HEAD.json').write_bytes(saved['head'])
    saved['tail_path'].write_bytes(saved['tail'])
    with pytest.raises(JournalError):t.reload(j)


def test_quarantine_does_not_depend_on_journal_or_detail_write(tmp_path,monkeypatch):
    j=t.create(tmp_path);old=j.head.copy()
    original=Path.open
    def fail_detail(path,*a,**k):
        if path.name=='reason.json':raise OSError('injected detail failure')
        return original(path,*a,**k)
    def execute(*a,**k):
        atomic_json(j.directory/'HEAD.json',old,replace=True)
        monkeypatch.setattr(Path,'open',fail_detail)
        j.append('request_reserved',segment=1,index=1,number=1,input=1,output=1)
    with pytest.raises(JournalError):t.segment(j,execute=execute)
    assert j.blocker.is_dir() and not (j.blocker/'reason.json').exists()
    with pytest.raises(JournalError):t.reload(j)


def test_load_detected_corruption_remains_blocked_after_repair(tmp_path):
    j=t.create(tmp_path);t.segment(j,stop_after=1)
    head=(j.directory/'HEAD.json').read_bytes()
    (j.directory/'HEAD.json').write_text('{}')
    with pytest.raises(JournalError):t.reload(j)
    (j.directory/'HEAD.json').write_bytes(head)
    with pytest.raises(JournalError):t.reload(j)


def test_quarantine_blocks_paid_entry_before_review_preflight_or_credentials(tmp_path,monkeypatch):
    j=t.create(tmp_path,'openai');j.block_resume()
    # main's filesystem layout, without changing the journal or synthetic plan.
    root=tmp_path/'cli';public=root/'results/study-v1.1-offline-test';private=root/'.local/study-v1.1/offline-test'
    public.parent.mkdir(parents=True);private.parent.mkdir(parents=True)
    j.public.rename(public);j.private.rename(private)
    monkeypatch.setattr(t.runner,'ROOT',root)
    monkeypatch.setattr(t.runner,'frozen_plan',lambda:j.plan)
    monkeypatch.setattr(t.runner.v1,'require_review',lambda *a:pytest.fail('No review/paid path allowed'))
    monkeypatch.setattr(t.runner,'environment_check',lambda *a:pytest.fail('No Docker/experiment allowed'))
    class NoCredentials(dict):
        def __getitem__(self,key):
            if key=='OPENAI_API_KEY':pytest.fail('No credential access allowed')
            return super().__getitem__(key)
    monkeypatch.setattr(t.runner.os,'environ',NoCredentials())
    with pytest.raises(JournalError):t.runner.main(['--run-id','offline-test','--backend','openai','--resume',
        '--allow-paid-api','--review-record','unused','--authorization','unused'])


def test_ordinary_unanchored_tail_still_recovers_without_quarantine(tmp_path):
    j=t.create(tmp_path);old=j.head.copy();t.segment(j,stop_after=1)
    # No active writer ever detected this lag: ordinary interrupted HEAD update.
    atomic_json(j.directory/'HEAD.json',old,replace=True)
    recovered=t.reload(j)
    assert not recovered.blocker.exists()
    assert t.segment(recovered,stop_after=1)['episodes'][-1]['schedule_index']==2
