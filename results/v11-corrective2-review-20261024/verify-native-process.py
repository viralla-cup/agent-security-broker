"""Native Windows process-death checks; synthetic ledger and no transport."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import os
import sys
sys.path.insert(0,str(Path.cwd()/'src'))
from lab.study import plan, seal_plan
import lab.study_journal as module

def child(root,stage):
    frozen=seal_plan({**plan('main'),'version':'expanded-study-v1.1','request_timeout_seconds':30,
        'source_sha256':{},'protocol_sha256':'synthetic-native-check'})
    raw=root/'private';raw.mkdir()
    j=module.Journal.create(root/'public',raw,frozen,'native-offline-check','openai');old=j.head.copy()
    def reserve(label):
        j.append('authorization_reserved',number=1,approved_head=j.head.copy(),
            authorization_sha256=label,authorization_id_sha256=label,review_sha256='synthetic-not-attestation')
    reserve('synthetic-1')
    def die():os._exit(37)
    if stage=='detected_before_block':
        module.atomic_json(j.directory/'HEAD.json',old,replace=True)
        j.block_resume=die
    elif stage=='during_check':
        j.verify_integrity(die)
    elif stage=='before_clear':
        original=Path.rmdir
        def rmdir(path,*a,**k):
            if path.name=='VERIFYING':die()
            return original(path,*a,**k)
        Path.rmdir=rmdir
    elif stage=='committed_tail':
        original=module.atomic_json
        def atomic(path,*a,**k):
            result=original(path,*a,**k)
            if Path(path).stem.isdigit():die()
            return result
        module.atomic_json=atomic
    reserve('synthetic-2');die()

if len(sys.argv)>1:
    child(Path(sys.argv[1]),sys.argv[2]);raise AssertionError('Expected termination')
with TemporaryDirectory(prefix='v11-second-native-') as folder:
    rows=[]
    for stage in ('detected_before_block','during_check','before_clear','committed_tail'):
        root=Path(folder)/stage;root.mkdir()
        result=subprocess.run([sys.executable,'-B',__file__,str(root),stage],capture_output=True,timeout=30)
        assert result.returncode==37,result.stderr.decode()
        raw=root/'private';public=root/'public';frozen=json.loads((public/'plan.json').read_text())
        blocked=False;authorizations=None
        try:
            j=module.Journal(public,raw,frozen);authorizations=len(j.state['authorizations'])
        except module.JournalError:blocked=True
        assert blocked==(stage!='committed_tail')
        if not blocked:assert authorizations==2
        rows.append({'stage':stage,'exit_code':37,'resume_blocked':blocked,'authorizations':authorizations})
    print(json.dumps({'kind':'offline_engineering','platform':sys.platform,'actual_provider_calls':0,'cases':rows},indent=2))
