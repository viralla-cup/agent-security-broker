"""Offline defect reproduction with the real local Core and synthetic transport."""
import sys
sys.path[:0]=['/app/src','/app/scripts','/app/tests']
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import hashlib
import test_study_v11 as t
from backends.base import BackendError
from lab.study_journal import JournalError, atomic_json
from lab.study import seed_for, install_fixture
from lab.oracle import snapshot

class Timeout:
    name='deterministic-fake';model='offline-timeout-injection'
    def __init__(self, task):pass
    def next_action(self,*args):
        self.last_call={'request_sent':True}  # Synthetic marker; no network code.
        raise BackendError('BACKEND_TIMEOUT')
class LedgerTimeout(t.runner.LedgerMixin,Timeout):pass

def execute_local(root, mutate=None):
    def execute(task,condition,backend,out,raw,**kwargs):
        if kwargs['position']['schedule_index']!=1:
            return t.execute_stub(task,condition,backend,out,raw,**kwargs)
        def factory(condition,task):
            ep=t.LocalEpisode(root/'lab',condition,seed_for(task))
            install_fixture(ep.root,task);ep.before=snapshot(ep.root);return ep
        def collect(ep):
            return {name:{'text':path.read_text(),'pending':False} for name,path in (
                ('/tmp/security-audit.jsonl',ep.audit_path),
                ('/tmp/pilot-operation-receipts.jsonl',ep.receipt_path))}
        row,baseline=t.runner.v1.execute_episode(task,condition,backend,out,raw,
            episode_factory=factory,worker=t.local_worker,credential_check=lambda ep:None,
            collect_service=collect,clock=lambda:0,**kwargs)
        if mutate:
            saved=json.loads((raw/'episode.json').read_text());mutate(saved)
            atomic_json(raw/'episode.json',saved,replace=True)
        return row,baseline
    return execute

def p2_child(root):
    j=t.create(root,'openai');old=j.head.copy()
    def execute(*a,**k):
        atomic_json(j.directory/'HEAD.json',old,replace=True)
        j.block_resume=lambda:os._exit(29)
        j.append('request_reserved',segment=1,index=1,number=1,input=1024,output=1024)
    t.segment(j,execute=execute)

if len(sys.argv)>1 and sys.argv[1]=='child':
    p2_child(Path(sys.argv[2]));raise AssertionError('Expected process death')

mode=sys.argv[1] if len(sys.argv)>1 else 'before'
with TemporaryDirectory() as name:
    root=Path(name);rows=[]
    changes={
        'healthy':None,
        'private_request_sent_false':lambda r:r['model_calls'][-1]['metadata'].update(request_sent=False),
        'private_observation_false':lambda r:r['observed'].update(observation_complete=False),
        'missing_receipts':lambda r:r.pop('operation_receipts'),
        'modified_task_prompt':lambda r:r['task'].update(prompt='offline injected contradiction')}
    for case,mutate in changes.items():
        folder=root/case;folder.mkdir();j=t.create(folder)
        summary=t.segment(j,execute=execute_local(folder,mutate),backend_factory=LedgerTimeout,stop_after=2)
        rows.append({'case':case,'continued':len(summary['episodes'])==2,
                     'position_1_retained':1 in j.state['finished']})
    folder=root/'crash';folder.mkdir()
    child=subprocess.run([sys.executable,'-B',__file__,'child',str(folder)],capture_output=True,timeout=30)
    assert child.returncode==29,child.stderr.decode()
    raw=folder/'private';public=folder/'public';frozen=json.loads((public/'plan.json').read_text())
    blocked=False;next_position=None
    try:
        j=t.Journal(public,raw,frozen);summary=t.segment(j,stop_after=1)
        next_position=summary['episodes'][-1]['schedule_index']
    except JournalError:blocked=True
    result={'kind':'offline_engineering','actual_provider_calls':0,'P1':rows,
        'P2':{'child_exit_code':child.returncode,'resume_blocked':blocked,'next_position':next_position},
        'source_sha256':{n:hashlib.sha256(Path('/app',n).read_bytes()).hexdigest() for n in
            ('src/lab/study_journal.py','scripts/run_expanded_study_v11.py')}}
    if mode=='before':assert all(r['continued'] for r in rows) and not blocked and next_position==2
    else:assert [r['continued'] for r in rows]==[True,False,False,False,False] and blocked
    print(json.dumps(result,indent=2))
