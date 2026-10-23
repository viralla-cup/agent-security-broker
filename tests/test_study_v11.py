"""Failure injection and local-broker integration; never use provider credentials."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_expanded_study_v11 as runner
from analyze_expanded_study import analyze
from lab.study import plan, seal_plan, schedule_positions, digest, expected_state, seed_for, install_fixture
from lab.study_journal import Journal, JournalError, RunLock, atomic_json, artifact_hashes
from backends.base import BackendError, TOOL_SCHEMA
from backends.openai import OpenAIBackend
from test_expanded_study import synthetic_row, local_worker
from test_controlled_pair import LocalEpisode
from lab.oracle import snapshot


@pytest.fixture(autouse=True)
def cleanup(tmp_path):
    yield
    assert 'pytest-of-' in str(tmp_path.resolve())
    shutil.rmtree(tmp_path)


def frozen():
    return seal_plan({**plan('main'), 'version':'expanded-study-v1.1', 'request_timeout_seconds':30,
                     'source_sha256':{}, 'protocol_sha256':'synthetic-test-only'})


def create(tmp_path, backend='fake', p=None):
    raw=tmp_path/'private';raw.mkdir()
    return Journal.create(tmp_path/'public',raw,p or frozen(),'offline-test',backend)


def runtime(j):
    return {'image_id':'sha256:offline-test-only','source_sha256':j.plan['source_sha256']}


def execute_stub(task, condition, backend, out, raw, *, position, integrity_check, **kwargs):
    out.mkdir(parents=True);raw.mkdir(parents=True)
    row=synthetic_row(position,backend.journal.plan)
    row['observed'].update(initial_files_unchanged=True, action_origin_counts={'unattributed':0},
                           outcome_class='model_outcome', infrastructure_ok=True)
    row['setup_checks']={'valid':True};row['isolation']={}
    atomic_json(out/'episode.json',row);atomic_json(raw/'episode.json',{'synthetic':True})
    return row,None


def segment(j, **kwargs):
    authorization='synthetic-authorization-not-attestation-'+j.head['sha256']
    if j.state['created']['backend']=='openai':
        j.append('authorization_reserved',number=len(j.state['segments'])+1,approved_head=j.head.copy(),
                 authorization_sha256=authorization,authorization_id_sha256=authorization,
                 review_sha256='synthetic-review-not-attestation')
    return runner.run_segment(j,runtime(j),authorization,
        'synthetic-review-not-attestation', input_check=lambda s,t=None:s.verify(t),
        check_environment=lambda p,i:runtime(j),execute=kwargs.pop('execute',execute_stub), **kwargs)


def reload(j):
    return Journal(j.public,j.private,j.plan)


def test_full_main_and_repeated_completed_resume(tmp_path):
    j=create(tmp_path);s=segment(j)
    assert s['batch_complete'] and len(s['episodes'])==56 and not s['unstarted']
    assert s['real_api_attempts']==0 and s['evidence_kind']=='fake_backend_engineering'
    assert len({p['episode_id'] for p in j.state['started'].values()})==56
    a=analyze(s,j.plan)
    assert all(p['status']=='complete_valid' for p in a['schedule_integrity']['pairs'].values())
    j=reload(j);before=j.head.copy()
    segment(j,execute=lambda *a,**k:pytest.fail('Must not execute twice'))
    assert j.head==before


def test_between_episode_resume_preserves_order_and_negative_outcomes(tmp_path):
    j=create(tmp_path);first=segment(j,stop_after=1)
    assert len(first['episodes'])==1 and not first['episodes'][0]['observed']['safe_task_completed']
    original=artifact_hashes(j.public/'R01-r1/B2')
    j=reload(j);s=segment(j)
    assert len(s['segments'])==2 and len(s['episodes'])==56
    assert artifact_hashes(j.public/'R01-r1/B2')==original
    assert [e['schedule_index'] for e in s['episodes']]==list(range(1,57))


def test_crash_before_final_commit_is_never_replayed(tmp_path):
    j=create(tmp_path)
    def crash(*args,**kwargs):
        execute_stub(*args,**kwargs)
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):segment(j,execute=crash)
    assert (j.public/'R01-r1/B2/episode.json').exists()
    j=reload(j);s=segment(j)
    assert len(s['episodes'])==55 and len(s['started_without_episode_record'])==1
    assert s['schedule_exhausted'] and not s['batch_complete']
    assert analyze(s,j.plan)['schedule_integrity']['pairs']['R01-r1']['status']=='incomplete'


def test_uncertain_inflight_request_survives_with_reserved_budget(tmp_path):
    j=create(tmp_path,'openai')
    def crash(task,condition,backend,*args,**kwargs):
        j.append('request_reserved',segment=j.state['active'],index=backend.index,number=1,input=8192,output=1024)
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):segment(j,execute=crash)
    j=reload(j)
    assert j.summary()['uncertain_api_attempts']==1 and j.summary()['api_attempts_reserved']==1
    s=segment(j,stop_after=1)
    assert s['episodes'][0]['schedule_index']==2
    assert s['api_attempts_reserved']==1 and s['input_tokens_reserved']==8192
    assert s['real_api_attempts']==0 and not s['api_attempt_accounting_complete']


@pytest.mark.parametrize('damage',['head','missing_head','missing_tail','missing_middle','changed_event','public','private','added_private','segment_metadata','plan'])
def test_corrupt_checkpoint_or_evidence_fails_closed(tmp_path,damage):
    j=create(tmp_path);segment(j,stop_after=1)
    events=sorted(j.directory.glob('[0-9]*.json'))
    if damage=='head':(j.directory/'HEAD.json').write_text('{}')
    elif damage=='missing_head':(j.directory/'HEAD.json').unlink()
    elif damage=='missing_tail':events[-1].unlink()
    elif damage=='missing_middle':events[1].unlink()
    elif damage=='changed_event':events[1].write_text('{}')
    elif damage=='public':(j.public/'R01-r1/B2/episode.json').write_text('{}')
    elif damage=='private':(j.private/'R01-r1/B2/episode.json').unlink()
    elif damage=='added_private':(j.private/'R01-r1/B2/extra.json').write_text('{}')
    elif damage=='segment_metadata':next((j.public/'segments/0001').glob('metadata-*.json')).write_text('{}')
    else:(j.public/'plan.json').write_text('{}')
    with pytest.raises((ValueError,KeyError,OSError)):reload(j)


def test_committed_tail_ahead_of_head_recovers_without_replay(tmp_path):
    j=create(tmp_path);old=j.head.copy();segment(j,stop_after=1)
    atomic_json(j.directory/'HEAD.json',old,replace=True)
    j=reload(j);assert len(j.state['finished'])==1
    assert segment(j,stop_after=1)['episodes'][-1]['schedule_index']==2


def timeout_execute(indices, incomplete=False, setup=True, safety=False):
    from study_timeout_helpers import local_timeout_episode
    def execute(task,condition,backend,out,raw,*,position,**kwargs):
        i=position['schedule_index']
        if i in indices:
            actions=[task['attack_probe']] if safety and condition=='B0' else []
            row,_=local_timeout_episode(task,condition,backend,out,raw,position=position,actions=actions,**kwargs)
            if incomplete:row['observed']['observation_complete']=False
            if safety:row['observed']['prohibited_effect']=True
            row['setup_checks']['valid']=setup
            atomic_json(out/'episode.json',row,replace=True)
            return row,None
        return execute_stub(task,condition,backend,out,raw,position=position,**kwargs)
    return execute


@pytest.mark.parametrize('indices,expected,terminal',[({1},56,None),({1,3},56,None),({1,2},2,'TIMEOUT_LIMIT'),({1,3,5},5,'TIMEOUT_LIMIT')])
def test_timeout_thresholds(tmp_path,indices,expected,terminal):
    j=create(tmp_path);s=segment(j,execute=timeout_execute(indices))
    assert len(s['episodes'])==expected and j.state['terminal']==terminal
    assert s['timeout_count']==len(indices)
    if terminal:
        with pytest.raises(JournalError):segment(reload(j))


def test_timeout_counters_survive_segment_boundary(tmp_path):
    j=create(tmp_path);segment(j,execute=timeout_execute({1}),stop_after=1)
    j=reload(j);s=segment(j,execute=timeout_execute({2}))
    assert s['timeout_count']==2 and s['stop_reason']=='TIMEOUT_LIMIT'


@pytest.mark.parametrize('failure',['incomplete','setup','environment','safety'])
def test_unverified_timeout_stops_immediately(tmp_path,failure):
    j=create(tmp_path)
    execute=timeout_execute({1},incomplete=failure=='incomplete',setup=failure!='setup',safety=failure=='safety')
    if failure=='environment':
        s=runner.run_segment(j,runtime(j),execute=execute,input_check=lambda s,t=None:None,
                            check_environment=lambda *a:(_ for _ in ()).throw(RuntimeError()))
    else:s=segment(j,execute=execute)
    assert len(s['episodes'])==1


def test_setup_failure_then_authorized_unstarted_position(tmp_path):
    j=create(tmp_path)
    def failed(task,condition,backend,out,raw,**kwargs):
        row,_=execute_stub(task,condition,backend,out,raw,**kwargs)
        row['observed'].update(episode_valid=False,observation_complete=False)
        row['loop']['stop_reason']='INFRASTRUCTURE_ERROR';row['setup_checks']={}
        atomic_json(out/'episode.json',row,replace=True);return row,None
    first=segment(j,execute=failed)
    assert len(first['episodes'])==1
    second=segment(reload(j),stop_after=1)
    assert [e['schedule_index'] for e in second['episodes']]==[1,2]
    assert analyze(second,j.plan)['schedule_integrity']['pairs']['R01-r1']['status']=='invalid_episode'


@pytest.mark.parametrize('field,value',[('max_api_requests',1),('max_input_reservations',8192),('max_output_reservations',1024)])
def test_request_and_token_limits_persist_across_segments(tmp_path,field,value):
    # Tightened synthetic ceiling makes the aggregate guard reachable in two positions.
    p=frozen();p[field]=value;p=seal_plan(p);j=create(tmp_path,p=p)
    def reserve(task,condition,backend,out,raw,**kwargs):
        j.append('request_reserved',segment=j.state['active'],index=backend.index,number=1,input=8192,output=1024)
        j.append('request_result',segment=j.state['active'],index=backend.index,number=1,metadata={'request_sent':False},outcome='PROPOSAL')
        return execute_stub(task,condition,backend,out,raw,**kwargs)
    # Test ledger directly because production capture rejects any changed scientific budget.
    original=runner.capture
    try:
        runner.capture=lambda f: original(frozen())
        segment(j,execute=reserve,stop_after=1)
        j=reload(j)
        with pytest.raises(JournalError):segment(j,execute=reserve)
        assert len(j.state['requests'])==1
    finally:runner.capture=original


def test_paid_authorization_bound_to_exact_head_and_segment(tmp_path):
    j=create(tmp_path,'openai');path=tmp_path/'authorization.json'
    record={'author':'synthetic unit test only','authorization_id':'not-human-approval','run_id':'offline-test',
            'plan_sha256':j.plan['plan_sha256'],'segment':1,'checkpoint_head':None,'allow_paid_api':True}
    atomic_json(path,record)
    assert runner.require_authorization(path,run_id='offline-test',frozen=j.plan,segment=1,head=None)==record
    for segment_number,head in [(2,None),(1,j.head)]:
        with pytest.raises(JournalError):runner.require_authorization(path,run_id='offline-test',frozen=j.plan,segment=segment_number,head=head)
    with pytest.raises(JournalError):runner.run_segment(j,runtime(j),input_check=lambda *a:None)


def test_concurrent_lock_and_release(tmp_path):
    path=tmp_path/'lock'
    with RunLock(path):
        with pytest.raises(JournalError):
            with RunLock(path):pass
    with RunLock(path):pass


def test_source_or_plan_mismatch_on_resume(tmp_path,monkeypatch):
    j=create(tmp_path);segment(j,stop_after=1)
    changed=deepcopy(j.plan);changed['request_timeout_seconds']=20;changed=seal_plan(changed)
    with pytest.raises(JournalError):Journal(j.public,j.private,changed)
    snap=runner.capture(j.plan)
    monkeypatch.setattr(runner,'frozen_plan',lambda:{'changed':True})
    with pytest.raises(JournalError):runner.verify_inputs(snap)


def test_offline_plan_and_paid_flags_never_access_credentials_or_runtime(monkeypatch,capsys):
    monkeypatch.setattr(runner,'frozen_plan',frozen)
    monkeypatch.setattr(runner,'environment_check',lambda *a:pytest.fail('No Docker or API expected'))
    class NoCredentials(dict):
        def __getitem__(self,k):
            if k=='OPENAI_API_KEY':pytest.fail('Credential access forbidden')
            return super().__getitem__(k)
        def get(self,k,default=None):
            if k=='OPENAI_API_KEY':pytest.fail('Credential access forbidden')
            return super().get(k,default)
    monkeypatch.setattr(runner.os,'environ',NoCredentials())
    runner.main(['--plan']);assert 'expanded-study-v1.1' in capsys.readouterr().out
    with pytest.raises(SystemExit):runner.main(['--run-id','test','--backend','openai'])


def test_local_core_seed_history_deadline_and_ledger_integration(tmp_path):
    j=create(tmp_path)
    def execute(task,condition,backend,out,raw,**kwargs):
        def factory(condition,task):
            ep=LocalEpisode(tmp_path/'lab',condition,seed_for(task))
            install_fixture(ep.root,task);ep.before=snapshot(ep.root);return ep
        return runner.v1.execute_episode(task,condition,backend,out,raw,episode_factory=factory,
            worker=local_worker,credential_check=lambda ep:None,collect_service=lambda ep:{},**kwargs)
    s=segment(j,execute=execute,stop_after=1)
    obs=s['episodes'][0]['observed']
    assert obs['episode_valid'] and obs['setup_deny_observed'] and obs['safe_completion_after_denial']
    assert len(j.state['requests'])==s['episodes'][0]['observed_model_calls']
    private=json.loads((j.private/'R01-r1/B2/episode.json').read_text())
    assert private['before']==expected_state(private['task'])
    assert private['model_calls'][0]['history'][1]['origin']=='harness_setup'
    assert private['model_calls'][0]['history'][3]['code']=='PATH_OUTSIDE_SCOPE'
    public=json.dumps(s)
    assert 'request_sha256' not in public and 'SYNTHETIC_CANARY_' not in public


def test_adapter_reservation_before_io_and_deadline_cap(tmp_path):
    j=create(tmp_path,'openai');seen=[]
    class Transport:
        def open(self,request,timeout):
            persisted=reload(j)
            assert len(persisted.state['requests'])==1
            assert persisted.summary()['uncertain_api_attempts']==1
            seen.append(timeout);raise TimeoutError()
    def execute(task,condition,backend,out,raw,**kwargs):
        api=runner.LedgerOpenAI('gpt-6-luna','synthetic-test-key',opener=Transport(),timeout=30,
            max_output_tokens=1024,deadline=17,clock=lambda:0).attach(j,backend.index)
        with pytest.raises(BackendError):api.next_action([],TOOL_SCHEMA)
        assert api.calls==1 and api.reserved_output==1024
        # A halted backend must not send/reserve an automatic second attempt.
        with pytest.raises(BackendError):api.next_action([],TOOL_SCHEMA)
        row,_=execute_stub(task,condition,backend,out,raw,**kwargs)
        metadata=j.state['requests'][backend.index,1]['result']['metadata']
        row['model_calls']=[{'metadata':metadata}];row['real_api_attempts']=1
        atomic_json(out/'episode.json',row,replace=True);return row,None
    s=segment(j,execute=execute,stop_after=1)
    assert seen==[17] and s['api_attempts_reserved']==s['real_api_attempts']==1


def test_os_process_death_in_transport_preserves_uncertainty(tmp_path):
    j=create(tmp_path,'openai')
    code='''
import sys,json,os
from pathlib import Path
sys.path[:0]=['src','scripts']
import run_expanded_study_v11 as r
from lab.study_journal import Journal,RunLock
from backends.base import TOOL_SCHEMA
public,private=map(Path,sys.argv[1:])
with RunLock(private/'run.lock'):
 j=Journal(public,private,json.loads((public/'plan.json').read_text()))
 j.append('authorization_reserved',number=1,approved_head=j.head.copy(),authorization_sha256='test-only',authorization_id_sha256='test-only',review_sha256='test-only')
 class KillTransport:
  def open(self,*a,**kw):os._exit(23)
 def execute(task,condition,backend,*a,**kw):
  api=r.LedgerOpenAI('gpt-6-luna','synthetic-offline-key',opener=KillTransport(),timeout=30,max_output_tokens=1024).attach(j,backend.index)
  api.next_action([],TOOL_SCHEMA)
 r.run_segment(j,{'image_id':'sha256:offline-test-only','source_sha256':{}},'test-only','test-only',execute=execute,input_check=lambda *a:None)
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(j.public),str(j.private)],capture_output=True,timeout=30)
    assert result.returncode==23,result.stderr.decode()
    j=reload(j);assert j.state['active']==1
    assert j.summary()['uncertain_api_attempts']==1
    with RunLock(j.private/'run.lock'):
        s=segment(j,stop_after=1)
    assert s['episodes'][0]['schedule_index']==2 and s['uncertain_api_attempts']==1
    assert s['segments'][0]['end']['reason']=='PROCESS_INTERRUPTED'


def test_persistence_failure_never_reaches_transport(tmp_path,monkeypatch):
    import lab.study_journal as module
    j=create(tmp_path,'openai');real_atomic=module.atomic_json;failed=[False]
    def fail_head(path,value,**kwargs):
        if Path(path).name=='HEAD.json' and j.state['started'] and not failed[0]:
            failed[0]=True;raise OSError('synthetic persistence failure')
        return real_atomic(path,value,**kwargs)
    class NeverTransport:
        def open(self,*a,**k):pytest.fail('I/O before durable reservation')
    def execute(task,condition,backend,*a,**k):
        monkeypatch.setattr(module,'atomic_json',fail_head)
        api=runner.LedgerOpenAI('gpt-6-luna','synthetic-offline-key',opener=NeverTransport(),max_output_tokens=1024).attach(j,backend.index)
        api.next_action([],TOOL_SCHEMA)
    with pytest.raises((OSError,JournalError)):segment(j,execute=execute)
    monkeypatch.setattr(module,'atomic_json',real_atomic)
    j=reload(j)
    assert j.summary()['uncertain_api_attempts']==1
    assert len(j.state['started'])==1


def test_seventh_request_in_one_position_rejected_before_io(tmp_path):
    j=create(tmp_path)
    def execute(task,condition,backend,out,raw,**kwargs):
        for number in range(1,7):
            j.append('request_reserved',segment=1,index=1,number=number,input=8192,output=1024)
            j.append('request_result',segment=1,index=1,number=number,metadata={'request_sent':False},outcome='PROPOSAL')
        with pytest.raises(JournalError):j.append('request_reserved',segment=1,index=1,number=7,input=8192,output=1024)
        return execute_stub(task,condition,backend,out,raw,**kwargs)
    segment(j,execute=execute,stop_after=1)
    assert len(j.state['requests'])==6


def test_cannot_resume_v1_or_change_timeout_policy(tmp_path):
    raw=tmp_path/'private';raw.mkdir()
    with pytest.raises(JournalError):Journal(tmp_path/'public',raw,seal_plan(plan('main')))
    changed=frozen();changed['request_timeout_seconds']=20;changed=seal_plan(changed)
    with pytest.raises(JournalError):runner.capture(changed)


def test_timeout_environment_artifact_missing_blocks_resume(tmp_path):
    j=create(tmp_path);segment(j,execute=timeout_execute({1}),stop_after=1)
    (j.public/'segments/0001/timeout-environment-001.json').unlink()
    with pytest.raises((JournalError,OSError)):reload(j)


def test_model_change_is_terminal_even_if_final_episode_record_missing(tmp_path):
    j=create(tmp_path,'openai')
    def execute(task,condition,backend,out,raw,**kwargs):
        for number,model in enumerate(['model-a','model-b'],1):
            j.append('request_reserved',segment=1,index=1,number=number,input=1024,output=1024)
            j.append('request_result',segment=1,index=1,number=number,metadata={'request_sent':True,'reported_model':model},outcome='PROPOSAL')
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):segment(j,execute=execute)
    j=reload(j)
    assert j.state['terminal']=='REPORTED_MODEL_CHANGED'
    with pytest.raises(JournalError):segment(j)


def test_missing_finished_ledger_response_fails_closed(tmp_path):
    j=create(tmp_path,'openai')
    def execute(task,condition,backend,out,raw,**kwargs):
        j.append('request_reserved',segment=1,index=1,number=1,input=1024,output=1024)
        return execute_stub(task,condition,backend,out,raw,**kwargs)
    s=segment(j,execute=execute)
    assert s['stop_reason']=='UNCERTAIN_REQUEST' and len(s['episodes'])==0
    assert reload(j).summary()['uncertain_api_attempts']==1
    assert segment(reload(j),stop_after=1)['episodes'][0]['schedule_index']==2


def test_b0_observed_effect_does_not_selectively_block_timeout_continuation(tmp_path):
    j=create(tmp_path)
    s=segment(j,execute=timeout_execute({4},safety=True),stop_after=5)
    assert len(s['episodes'])==5 and s['episodes'][3]['condition']=='B0'
    assert s['episodes'][3]['observed']['prohibited_effect']


def test_changed_inputs_during_segment_are_a_terminal_stop(tmp_path):
    j=create(tmp_path);calls=[0]
    def check(*args):
        calls[0]+=1
        if calls[0]>=3:raise JournalError('synthetic source mismatch')
    with pytest.raises(JournalError):
        runner.run_segment(j,runtime(j),execute=execute_stub,input_check=check)
    assert j.state['terminal']=='CHECKPOINT_OR_INPUT_FAILURE'
    assert (j.private/'RESUME_BLOCKED').is_dir()
    with pytest.raises(JournalError):reload(j)


def test_timeout_known_before_crash_is_not_lost_or_double_counted(tmp_path):
    j=create(tmp_path,'openai')
    def crash(task,condition,backend,*args,**kwargs):
        index=backend.index;number=j.state['active']
        j.append('request_reserved',segment=number,index=index,number=1,input=1024,output=1024)
        j.append('request_result',segment=number,index=index,number=1,
                 metadata={'request_sent':True},outcome='BACKEND_TIMEOUT')
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):segment(j,execute=crash)
    j=reload(j)
    assert j.state['timeouts']==1 and j.state['consecutive_timeouts']==1
    with pytest.raises(KeyboardInterrupt):segment(j,execute=crash)
    j=reload(j)
    assert j.state['timeouts']==2 and j.state['terminal']=='TIMEOUT_LIMIT'
    with pytest.raises(JournalError):segment(j)


def test_live_head_damage_prevents_next_request_reservation(tmp_path):
    j=create(tmp_path)
    def execute(task,condition,backend,*args,**kwargs):
        atomic_json(j.directory/'HEAD.json',{'sequence':0,'sha256':'0'*64},replace=True)
        with pytest.raises(JournalError):
            j.append('request_reserved',segment=1,index=1,number=1,input=1,output=1)
        assert not j.state['requests']
        raise KeyboardInterrupt()
    with pytest.raises(JournalError):segment(j,execute=execute)


def test_crash_after_segment_metadata_preserves_orphan_and_resumes(tmp_path,monkeypatch):
    j=create(tmp_path);append=j.append
    def crash(kind,**kwargs):
        if kind=='segment_start':raise KeyboardInterrupt()
        return append(kind,**kwargs)
    monkeypatch.setattr(j,'append',crash)
    with pytest.raises(KeyboardInterrupt):segment(j)
    orphan=next((j.public/'segments/0001').glob('metadata-*.json'))
    preserved=orphan.read_bytes()
    j=reload(j)
    assert not j.state['segments'] and not j.state['started']
    result=segment(j,stop_after=1)
    assert result['episodes'][0]['schedule_index']==1
    assert len(list(orphan.parent.glob('metadata-*.json')))==2
    assert orphan.read_bytes()==preserved
    assert j.state['segments'][0]['metadata_file']!=orphan.name


def test_failed_paid_preflight_consumes_approval_without_credentials(tmp_path,monkeypatch):
    p=frozen();author=tmp_path/'synthetic-author.json'
    record={'author':'synthetic unit test only','authorization_id':'synthetic-1','run_id':'preflight-test',
            'plan_sha256':p['plan_sha256'],'segment':1,'checkpoint_head':None,'allow_paid_api':True}
    atomic_json(author,record)
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr(runner,'frozen_plan',lambda:p)
    monkeypatch.setattr(runner.v1,'require_review',lambda *args:{'synthetic_fixture_not_attestation':True})
    monkeypatch.setattr(runner,'environment_check',lambda *args:(_ for _ in ()).throw(OSError('offline injected preflight failure')))
    class ForbiddenCredentials(dict):
        def __getitem__(self,key):
            if key=='OPENAI_API_KEY':pytest.fail('Preflight must precede credential access')
            return super().__getitem__(key)
    monkeypatch.setattr(runner.os,'environ',ForbiddenCredentials({name:os.environ[name] for name in os.environ if name!='OPENAI_API_KEY'}))
    args=['--run-id','preflight-test','--backend','openai','--allow-paid-api',
          '--review-record',str(tmp_path/'synthetic-review-placeholder.json'),'--authorization',str(author)]
    with pytest.raises(OSError):runner.main(args)
    public=tmp_path/'results/study-v1.1-preflight-test';private=tmp_path/'.local/study-v1.1/preflight-test'
    j=Journal(public,private,p)
    assert len(j.state['authorizations'])==1 and not j.state['requests'] and not j.state['started']
    assert j.summary()['next_segment']==1
    with pytest.raises(JournalError):runner.main(args+['--resume'])
    record['checkpoint_head']=j.head.copy()
    atomic_json(author,record,replace=True)
    with pytest.raises(JournalError):runner.main(args+['--resume'])  # ID is consumed even with a fresh head.
    record['authorization_id']='synthetic-2'
    atomic_json(author,record,replace=True)
    with pytest.raises(OSError):runner.main(args+['--resume'])
    j=Journal(public,private,p)
    assert len(j.state['authorizations'])==2 and not j.state['requests']


def test_interrupted_public_control_copy_resumes_offline(tmp_path,monkeypatch):
    from types import SimpleNamespace
    p=frozen();real_atomic=runner.atomic_json;failed=[False]
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr(runner,'frozen_plan',lambda:p)
    monkeypatch.setattr(runner,'environment_check',lambda *args:{'image_id':'sha256:offline-only','source_sha256':{}})
    monkeypatch.setattr(runner,'command',lambda *args:SimpleNamespace(stdout='synthetic-base-commit'))
    monkeypatch.setattr(runner.v1,'run_controls',lambda *args,**kwargs:{'synthetic_controls':True})
    monkeypatch.setattr(runner.v1,'validate_controls',lambda *args:None)
    out=tmp_path/'results/study-v1.1-copy-test'
    def crash(path,value,**kwargs):
        if Path(path)==out/'controls.json' and not failed[0]:
            failed[0]=True;raise KeyboardInterrupt()
        return real_atomic(path,value,**kwargs)
    monkeypatch.setattr(runner,'atomic_json',crash)
    args=['--run-id','copy-test','--backend','fake','--controls-only']
    with pytest.raises(KeyboardInterrupt):runner.main(args)
    assert (out/'metadata.json').exists() and not (out/'controls.json').exists()
    runner.main(args+['--resume'])
    assert json.loads((out/'controls.json').read_text())=={'synthetic_controls':True}
