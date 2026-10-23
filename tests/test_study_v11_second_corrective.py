"""Second review's contradictions and process-death boundaries, entirely offline."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import test_study_v11 as t
from lab.study_journal import JournalError, atomic_json
from study_timeout_helpers import local_timeout_episode


@pytest.mark.parametrize('damage', ['healthy','request_sent','observation','study_observation',
    'receipts_missing','receipts_empty','receipt_fingerprint','prompt','history_prompt','history_extra','public_mode',
    'service_receipts','service_pending','service_missing','private_unreadable',
    'both_call_metadata','both_observation','public_snapshot','reservation_missing','reservation_outcome'])
def test_timeout_requires_semantic_consistency(tmp_path,damage):
    j=t.create(tmp_path);execute=t.timeout_execute({1})
    def changed(task,condition,backend,out,raw,**kwargs):
        row,baseline=execute(task,condition,backend,out,raw,**kwargs)
        if kwargs['position']['schedule_index']!=1:return row,baseline
        saved=json.loads((raw/'episode.json').read_text())
        if damage=='request_sent':saved['model_calls'][-1]['metadata']['request_sent']=False
        elif damage=='observation':saved['observed']['observation_complete']=False
        elif damage=='study_observation':saved['study_observed']['observation_complete']=False
        elif damage=='receipts_missing':saved.pop('operation_receipts')
        elif damage=='receipts_empty':saved['operation_receipts']=[]
        elif damage=='receipt_fingerprint':saved['operation_receipts'][0]['request_sha256']='0'*64
        elif damage=='prompt':saved['task']['prompt']='contradictory offline fixture'
        elif damage=='history_prompt':saved['model_calls'][0]['history'][0]['text']='wrong prompt'
        elif damage=='history_extra':saved['model_calls'][0]['history'].append({'kind':'task','text':'unrecorded instruction'})
        elif damage=='public_mode':row.update(backend='openai-responses',real_api_attempts=1,evidence_kind='real_model_pilot')
        elif damage in ('service_receipts','service_pending'):
            service=json.loads((raw/'service-evidence.json').read_text())
            service['/tmp/pilot-operation-receipts.jsonl']['text' if damage=='service_receipts' else 'pending']='' if damage=='service_receipts' else True
            atomic_json(raw/'service-evidence.json',service,replace=True)
            saved['service_evidence_sha256']=t.runner.file_hash(raw/'service-evidence.json')
        elif damage=='service_missing':(raw/'service-evidence.json').unlink()
        elif damage=='both_call_metadata':
            for call in (saved['model_calls'][-1],row['model_calls'][-1]):call['metadata']['injected_field']=True
        elif damage=='both_observation':
            for obs in (saved['observed'],saved['study_observed'],row['observed']):obs['task_completed']=True
        elif damage=='public_snapshot':next(v for v in row['before'].values() if v['type']=='file')['size']+=1
        elif damage=='reservation_missing':j.state['requests'].clear()
        elif damage=='reservation_outcome':j.state['requests'][1,1]['result']['outcome']='PROPOSAL'
        atomic_json(raw/'episode.json',saved,replace=True)
        if damage=='private_unreadable':
            (raw/'episode.json').rename(raw/'unreadable-retained.json');(raw/'episode.json').mkdir()
        atomic_json(out/'episode.json',row,replace=True)
        return row,baseline
    s=t.segment(j,execute=changed,stop_after=2)
    assert len(s['episodes'])==(2 if damage=='healthy' else 1)
    if damage!='healthy':assert j.state['last_finish']['timeout_environment_ok'] is False
    assert s['episodes'][0]['observed']['episode_valid'] is False
    assert (j.private/'R01-r1/B2').exists()


def test_timeout_after_real_local_read_write_recomputes_oracle(tmp_path):
    j=t.create(tmp_path)
    def execute(task,condition,backend,out,raw,**kwargs):
        if kwargs['position']['schedule_index']!=1:return t.execute_stub(task,condition,backend,out,raw,**kwargs)
        actions=[{'tool':'read_text','arguments':{'path':'/lab/'+p}} for p in task['required_reads']]
        actions += [{'tool':'write_new','arguments':{'path':'/lab/'+p,'content':v}} for p,v in task['outputs'].items()]
        return local_timeout_episode(task,condition,backend,out,raw,actions=actions,**kwargs)
    s=t.segment(j,execute=execute,stop_after=2)
    assert len(s['episodes'])==2 and s['episodes'][0]['observed']['task_completed']
    assert not s['episodes'][0]['observed']['episode_valid']
    assert j.timeout_isolated(s['episodes'][0],1)
    # Semantic checks also run on replay, not only in the runtime continuation gate.
    assert len(t.reload(j).state['finished'])==2


def test_mock_responses_timeout_matches_paid_reservation_ledger(tmp_path):
    from test_backends import HTTPDouble, KEY
    from study_timeout_helpers import service_copy
    from lab.controlled_recovery import API_BUDGET
    transport=HTTPDouble([TimeoutError()]);j=t.create(tmp_path,'openai')
    def backend(task):
        return t.runner.LedgerOpenAI('gpt-6-luna',KEY,opener=transport,timeout=30,
            max_output_tokens=1024,budget=API_BUDGET,clock=lambda:0)
    def execute(task,condition,backend,out,raw,**kwargs):
        if kwargs['position']['schedule_index']!=1:return t.execute_stub(task,condition,backend,out,raw,**kwargs)
        def factory(condition,task):
            ep=t.LocalEpisode(raw/'fixture',condition,t.seed_for(task))
            t.install_fixture(ep.root,task);ep.before=t.snapshot(ep.root);return ep
        return t.runner.v1.execute_episode(task,condition,backend,out,raw,
            episode_factory=factory,worker=t.local_worker,collect_service=service_copy,
            credential_check=lambda ep:None,clock=lambda:0,**kwargs)
    s=t.segment(j,execute=execute,backend_factory=backend,stop_after=2)
    assert len(s['episodes'])==2 and len(transport.requests)==1
    assert j.timeout_isolated(s['episodes'][0],1)
    request=j.state['requests'][1,1]
    assert request['input']>=1024 and request['output']==1024
    assert request['result']['metadata']==s['episodes'][0]['model_calls'][0]['metadata']
    assert len(t.reload(j).state['finished'])==2


@pytest.mark.parametrize('stage,blocked,authorizations',[
    ('before_arm',False,1),('arm_created',True,1),('during_check',True,1),
    ('detected_before_block',True,1),('block_creation_failure',True,1),
    ('before_clear',True,1),('after_clear',False,1),('before_event',False,1),
    ('committed_tail',False,2),('after_head',False,2),('complete',False,2),
    ('load_arm_created',True,1),('load_during_check',True,1),
    ('load_detected_before_block',True,1),('load_before_clear',True,1),('load_after_clear',False,1)])
def test_process_death_at_integrity_boundaries(tmp_path,stage,blocked,authorizations):
    child=subprocess.run([sys.executable,'-B','tests/study_integrity_crash.py',str(tmp_path),stage],
                         capture_output=True,timeout=30)
    assert child.returncode==37,child.stderr.decode()
    raw=tmp_path/'private';public=tmp_path/'public';frozen=json.loads((public/'plan.json').read_text())
    if blocked:
        assert (raw/'VERIFYING').exists() or (raw/'RESUME_BLOCKED').exists()
        with pytest.raises(JournalError):t.Journal(public,raw,frozen)
        # Even repaired HEAD cannot make interrupted verification disappear.
        atomic_json(raw/'journal/HEAD.json',json.loads((tmp_path/'head-before.json').read_text()),replace=True)
        with pytest.raises(JournalError):t.Journal(public,raw,frozen)
    else:
        j=t.Journal(public,raw,frozen)
        assert len(j.state['authorizations'])==authorizations and not j.state['terminal']
        assert not j.verifying.exists() and not j.blocker.exists()
        assert not j.state['requests']


@pytest.mark.parametrize('boundary',['arm_failure','sync_failure','clear_failure'])
def test_verification_storage_failures_stop_before_io(tmp_path,monkeypatch,boundary):
    j=t.create(tmp_path);called=[]
    if boundary=='sync_failure':
        monkeypatch.setattr(j,'_sync_private_directory',lambda:(_ for _ in ()).throw(OSError('injected sync failure')))
    else:
        method='mkdir' if boundary=='arm_failure' else 'rmdir';original=getattr(Path,method)
        def fail(path,*a,**k):
            if path==j.verifying:raise OSError('injected guard persistence failure')
            return original(path,*a,**k)
        monkeypatch.setattr(Path,method,fail)
    with pytest.raises(OSError):j.verify_integrity(lambda:called.append(True))
    assert bool(called)==(boundary=='clear_failure')
    if boundary!='arm_failure':
        with pytest.raises(JournalError):t.reload(j)
